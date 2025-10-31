# app/workers/runner.py
from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
import traceback
from contextlib import suppress
from typing import List

# ──────────────────────────────────────────────────────────────────────────────
# КРИТИЧЕСКО: отключаем C-расширения SQLAlchemy ДО любых импортов sqlalchemy
# Это устраняет segfault в связке uvloop/greenlet/sqlalchemy.cyextension
# ──────────────────────────────────────────────────────────────────────────────
os.environ.setdefault("SQLALCHEMY_DISABLE_CEXT", "1")  # <-- ключевая строка

# Диагностика/логи
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("PYTHONFAULTHANDLER", "1")

# uvloop: ОТКЛЮЧЕНО по умолчанию из-за бага. Можете включить позже (USE_UVLOOP=1)
USE_UVLOOP = os.getenv("USE_UVLOOP", "0") == "1"
if USE_UVLOOP:
    try:
        import uvloop  # type: ignore
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("✅ uvloop enabled", flush=True)
    except Exception as e:
        print(f"⚠️ uvloop not available: {e}", flush=True)
else:
    print("ℹ️ uvloop disabled (USE_UVLOOP=0)", flush=True)

# faulthandler — печатает стеки при фатальных падениях интерпретатора
try:
    import faulthandler  # type: ignore
    faulthandler.enable(all_threads=True)
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Импорты приложения (после env)
# ──────────────────────────────────────────────────────────────────────────────
from app.events.bus import EventBus
import app.events.bus as bus_module

from app.robot_emulator.emulator import run_robot_watcher_mproc

from app.ws.products_events import continuous_product_snapshot_streamer
from app.ws.battery_events import continuous_robot_avg_streamer
from app.ws.inventory_scans_streamer import continuous_inventory_scans_streamer
from app.ws.inventory_critical_streamer import continuous_inventory_critical_streamer
from app.ws.inventory_status import continuous_inventory_status_avg_streamer
from app.ws.robot_status_count_streamer import continuous_robot_status_count_streamer
from app.ws.robot_activity_streamer import continuous_robot_activity_history_streamer

# ──────────────────────────────────────────────────────────────────────────────
# Конфиг
# ──────────────────────────────────────────────────────────────────────────────
REDIS_DSN = os.getenv("REDIS_DSN", "redis://myapp-redis:6379/0")
WATCHER_INTERVAL = float(os.getenv("WATCHER_INTERVAL", "2"))

_SHUTDOWN = False


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _graceful(signame: str) -> None:
        global _SHUTDOWN
        if _SHUTDOWN:
            return
        _SHUTDOWN = True
        print(f"🛑 worker: got {signame}, initiating shutdown…", flush=True)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _graceful, sig.name)


def _loop_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    msg = context.get("message") or "Unhandled exception in event loop"
    exc = context.get("exception")
    print(f"💥 {msg}", flush=True)
    if exc:
        traceback.print_exception(exc, file=sys.stderr)
        sys.stderr.flush()


async def _run_task_group_once() -> None:
    # 1) EventBus
    bus = EventBus(REDIS_DSN)
    await bus.connect()
    bus_module.bus = bus  # type: ignore[attr-defined]
    print("🔌 EventBus connected", flush=True)

    # 2) Задачи
    tasks: List[asyncio.Task] = []
    try:
        tasks.append(asyncio.create_task(run_robot_watcher_mproc()))
        tasks.append(asyncio.create_task(continuous_product_snapshot_streamer(interval=10, use_ws_rooms=False), name="products_snapshot"))
        tasks.append(asyncio.create_task(continuous_robot_avg_streamer(interval=60, use_ws_rooms=False), name="robot_avg"))
        tasks.append(asyncio.create_task(continuous_inventory_scans_streamer(interval=60, hours=24, use_ws_rooms=False), name="inventory_scans"))
        tasks.append(asyncio.create_task(continuous_inventory_critical_streamer(interval=60, use_ws_rooms=False), name="inventory_critical"))
        tasks.append(asyncio.create_task(continuous_inventory_status_avg_streamer(interval=60, use_ws_rooms=False), name="inventory_status_avg"))
        tasks.append(asyncio.create_task(continuous_robot_status_count_streamer(interval=60, use_ws_rooms=False), name="robot_status_count"))
        tasks.append(asyncio.create_task(continuous_robot_activity_history_streamer(interval=600, use_ws_rooms=False), name="robot_activity_history"))

        print("🚀 worker: task group started", flush=True)

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

        errors = []
        for t in done:
            if t.cancelled():
                continue
            exc = t.exception()
            if exc:
                errors.append((t.get_name(), exc))
            else:
                print(f"⚠️ worker: task {t.get_name()} returned unexpectedly", flush=True)

        if errors:
            for name, exc in errors:
                print(f"💥 worker: task {name} crashed: {exc}", flush=True)
                traceback.print_exception(exc, file=sys.stderr)
                sys.stderr.flush()
            raise RuntimeError("one or more worker tasks crashed")

    except asyncio.CancelledError:
        print("🛑 worker: task group cancelled", flush=True)
        raise
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        for t in tasks:
            with suppress(asyncio.CancelledError):
                await t

        try:
            await bus.close()
            print("🔌 EventBus closed", flush=True)
        except Exception as e:
            print(f"⚠️ bus.close() error: {e}", flush=True)


async def _supervisor() -> None:
    backoff = 1.0
    backoff_max = 30.0
    print("🧭 worker supervisor started", flush=True)

    while not _SHUTDOWN:
        started = time.time()
        try:
            await _run_task_group_once()
            if _SHUTDOWN:
                break
            print("⚠️ task group returned without shutdown flag; restarting…", flush=True)
        except asyncio.CancelledError:
            print("🛑 supervisor cancelled by signal", flush=True)
            break
        except Exception as e:
            print(f"💥 worker: task group crashed: {e}", flush=True)

        elapsed = time.time() - started
        if elapsed > 10:
            backoff = 1.0
        else:
            backoff = min(backoff * 2.0, backoff_max)

        if _SHUTDOWN:
            break

        print(f"⏳ restarting task group in {backoff:.1f}s …", flush=True)
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            break

    print("✅ worker supervisor stopped", flush=True)


async def main() -> None:
    loop = asyncio.get_running_loop()
    _install_signal_handlers(loop)
    loop.set_exception_handler(_loop_exception_handler)
    await _supervisor()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"💥 fatal in runner: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
