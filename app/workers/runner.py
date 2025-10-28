# app/workers/runner.py
from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress

# 1) единый экземпляр EventBus и «проброс» его в модуль app.events.bus,
#    чтобы другие модули могли делать: `from app.events.bus import bus`
from app.events.bus import EventBus
import app.events.bus as bus_module

# 2) ваши фоновые задачи (эмулятор и, при желании, все continuous_* стримеры)
from app.robot_emulator.emulator import run_robot_watcher
# Пример: раскомментируйте по мере переноса стримеров в воркер
from app.ws.products_events import continuous_product_snapshot_streamer
from app.ws.battery_events import continuous_robot_avg_streamer
from app.ws.inventory_scans_streamer import continuous_inventory_scans_streamer
from app.ws.inventory_critical_streamer import continuous_inventory_critical_streamer
from app.ws.inventory_status import continuous_inventory_status_avg_streamer
from app.ws.robot_status_count_streamer import continuous_robot_status_count_streamer
from app.ws.robot_activity_streamer import continuous_robot_activity_history_streamer


REDIS_DSN = os.getenv("REDIS_DSN", "redis://myapp-redis:6379/0")
WATCHER_INTERVAL = float(os.getenv("WATCHER_INTERVAL", "2"))


async def main() -> None:
    # создаём и подключаем EventBus
    bus = EventBus(REDIS_DSN)
    await bus.connect()

    # делаем его доступным как app.events.bus.bus
    # (важно: эмулятор/стримеры импортируют именно глобальный bus)
    bus_module.bus = bus  # type: ignore[attr-defined]

    stop = asyncio.Event()

    def _handle_stop() -> None:
        print("🛑 worker: stopping...")
        stop.set()

    loop = asyncio.get_running_loop()
    # корректная обработка SIGINT/SIGTERM в контейнере/локально
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):  # Windows
            loop.add_signal_handler(sig, _handle_stop)

    # стартуем задачи воркера (каждую как отдельную таску)
    tasks: list[asyncio.Task] = []

    # эмулятор/симулятор роботов
    tasks.append(asyncio.create_task(run_robot_watcher(interval=WATCHER_INTERVAL)))
    tasks.append(asyncio.create_task(continuous_product_snapshot_streamer(interval=10, use_ws_rooms=False)))
    tasks.append(asyncio.create_task(continuous_robot_avg_streamer(interval=60, use_ws_rooms=False)))
    tasks.append(asyncio.create_task(continuous_inventory_scans_streamer(interval=60, hours=24, use_ws_rooms=False)))
    tasks.append(asyncio.create_task(continuous_inventory_critical_streamer(interval=60, use_ws_rooms=False)))
    tasks.append(asyncio.create_task(continuous_inventory_status_avg_streamer(interval=60, use_ws_rooms=False)))
    tasks.append(asyncio.create_task(continuous_robot_status_count_streamer(interval=60, use_ws_rooms=False)))
    tasks.append(asyncio.create_task(continuous_robot_activity_history_streamer(interval=600, use_ws_rooms=False)))

    # ждём сигнала остановки
    await stop.wait()

    # отменяем все фоновые задачи и дожидаемся их завершения
    for t in tasks:
        t.cancel()
    for t in tasks:
        with suppress(asyncio.CancelledError):
            await t

    # закрываем подключение к Redis
    await bus.close()
    print("✅ worker: stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
