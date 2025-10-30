from __future__ import annotations
import asyncio, os, signal, multiprocessing as mp
from datetime import datetime
from typing import Dict, Set
from sqlalchemy import select, func
from dataclasses import dataclass

from app.db.session import async_session as AppSession
from app.models.warehouse import Warehouse
from app.models.robot import Robot

from config import (
    MP_START_METHOD, TICK_INTERVAL, MAX_WAREHOUSE_PROCS, ROBOTS_PER_PROC,
    COORDINATOR_SHARD_INDEX
)
from watcher_service import _run_warehouse  
from redis_coord_service import close_redis

@dataclass
class _WhProc:
    proc: mp.Process
    stop_evt: mp.Event # type: ignore

async def _list_active_warehouses() -> Set[str]:
    async with AppSession() as session:
        rows = await session.execute(
            select(Warehouse.id).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
        )
        return set(rows.scalars().all())

async def _graceful_wait(condition_fn, timeout: float, poll: float = 0.1) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition_fn():
            return True
        await asyncio.sleep(poll)
    return condition_fn()

def _warehouse_process_entry(warehouse_id: str, shard_idx: int, shard_count: int, stop_evt: mp.Event) -> None: # type: ignore
    try:
        asyncio.run(_run_warehouse_until_event(warehouse_id, shard_idx, shard_count, stop_evt))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"⚠️ worker({warehouse_id}) crashed: {e}", flush=True)
    finally:
        try:
            asyncio.run(close_redis())
        except Exception:
            pass
        print(f"🧹 worker({warehouse_id}) stopped", flush=True)

async def _run_warehouse_until_event(warehouse_id: str, shard_idx: int, shard_count: int, stop_evt: mp.Event) -> None: # type: ignore
    print(f"🏭 worker({warehouse_id}) shard={shard_idx+1}/{max(1, shard_count)} started pid={os.getpid()} interval={TICK_INTERVAL}s", flush=True)
    task = asyncio.create_task(_run_warehouse(warehouse_id, shard_idx, shard_count))
    try:
        while not stop_evt.is_set():
            await asyncio.sleep(TICK_INTERVAL)
    finally:
        task.cancel()
        try:
            await task
        except Exception:
            pass

async def run_robot_watcher_mproc() -> None:
    mp.set_start_method(MP_START_METHOD, force=True)
    print(f"🚀 MP watcher started pid={os.getpid()} method={MP_START_METHOD} interval={TICK_INTERVAL}s", flush=True)

    procs: Dict[str, _WhProc] = {}
    stop = asyncio.Event()

    def _on_signal(sig, _frame=None):
        print(f"🛑 MP watcher got signal {sig}", flush=True)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _on_signal)
        except Exception:
            pass

    try:
        while not stop.is_set():
            try:
                wh_ids = await _list_active_warehouses()
                # рассчёт числа шардов
                wh_robot_counts: Dict[str, int] = {}
                async with AppSession() as session:
                    rows = await session.execute(
                        select(Warehouse.id, func.count(Robot.id))
                        .join(Robot, Robot.warehouse_id == Warehouse.id)
                        .group_by(Warehouse.id)
                    )
                    for wid, cnt in rows.all():
                        wh_robot_counts[wid] = int(cnt)

                # запуск недостающих
                for wid in sorted(wh_ids):
                    total = wh_robot_counts.get(wid, 0)
                    shard_count = max(1, (total + ROBOTS_PER_PROC - 1) // ROBOTS_PER_PROC) if total > 0 else 0
                    alive_global = len([p for p in procs.values() if p.proc.is_alive()])

                    for shard_idx in range(shard_count):
                        key = f"{wid}:{shard_idx}/{shard_count}"
                        if key in procs and procs[key].proc.is_alive():
                            continue
                        if MAX_WAREHOUSE_PROCS > 0 and alive_global >= MAX_WAREHOUSE_PROCS:
                            break
                        stop_evt = mp.Event()
                        p = mp.Process(
                            target=_warehouse_process_entry,
                            args=(wid, shard_idx, shard_count, stop_evt),
                            name=f"wh-{wid[:6]}-s{shard_idx+1}of{shard_count}",
                            daemon=False,
                        )
                        p.start()
                        procs[key] = _WhProc(proc=p, stop_evt=stop_evt)
                        alive_global += 1
                        print(f"▶️ started worker for wh={wid} shard={shard_idx+1}/{shard_count} pid={p.pid}", flush=True)

                # останов лишних
                active_keys = set()
                for wid in sorted(wh_ids):
                    total = wh_robot_counts.get(wid, 0)
                    shard_count = max(1, (total + ROBOTS_PER_PROC - 1) // ROBOTS_PER_PROC) if total > 0 else 0
                    for shard_idx in range(shard_count):
                        active_keys.add(f"{wid}:{shard_idx}/{shard_count}")

                for key in list(procs.keys()):
                    wid = key.split(":", 1)[0]
                    if (wid not in wh_ids) or (key not in active_keys):
                        wp = procs.pop(key, None)
                        if not wp:
                            continue
                        print(f"⏹ stopping worker {key}", flush=True)
                        try:
                            wp.stop_evt.set()
                        except Exception:
                            pass
                        wp.proc.join(timeout=10)
                        if wp.proc.is_alive():
                            print(f"⛔ force terminate {key}", flush=True)
                            wp.proc.terminate()
                            wp.proc.join(timeout=5)

                # чистим мёртвые
                for key, wp in list(procs.items()):
                    if not wp.proc.is_alive():
                        procs.pop(key, None)

                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ MP watcher loop error: {e}", flush=True)
                await asyncio.sleep(0.5)
    finally:
        print("🧹 MP watcher shutting down...", flush=True)
        for key, wp in list(procs.items()):
            try:
                wp.stop_evt.set()
            except Exception:
                pass
        await _graceful_wait(lambda: all(not wp.proc.is_alive() for wp in procs.values()), timeout=12.0, poll=0.2)
        for key, wp in list(procs.items()):
            if wp.proc.is_alive():
                print(f"⛔ force terminate {key}", flush=True)
                wp.proc.terminate()
        for key, wp in list(procs.items()):
            try:
                wp.proc.join(timeout=3)
            except Exception:
                pass
        await close_redis()
        print("✅ MP watcher stopped", flush=True)
