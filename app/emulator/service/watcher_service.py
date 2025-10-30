from __future__ import annotations
import asyncio, os, signal
from datetime import datetime
from typing import Dict, Set, List
from sqlalchemy import select, func

from app.db.session import async_session as AppSession
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from scheduler_service import select_robot_batch
from config import (
    TICK_INTERVAL, EMIT_AUTOSEND_INIT, ROBOTS_CONCURRENCY,
)
from state_service import (
    wh_snapshot, WH_SNAPSHOT, WH_SNAPSHOT_VER, WH_LAST_SENT_VER, WH_LAST_SENT_MAP,
    LAST_POS_BROADCAST_AT, LAST_ANY_SENT_AT, ELIGIBLE_CACHE, WH_TICK_COUNTER,
    WH_ROBOT_OFFSET, wh_lock
)
from fast_scan_service import fast_scan_loop
from broadcaster_service import ensure_positions_broadcaster_started, stop_positions_broadcaster
from warmup_service import warmup_or_sync_snapshot
from positions_service import emit_positions_snapshot_force
from events_service import emit, emit_position_if_needed
from scanning_service import emit_product_scan_on_connect
from tick_service import robot_tick

_FAST_TASKS = {}

def _ensure_fast_scan_task_started(warehouse_id: str) -> None:
    if warehouse_id in _FAST_TASKS and not _FAST_TASKS[warehouse_id].done():
        return
    _FAST_TASKS[warehouse_id] = asyncio.create_task(fast_scan_loop(warehouse_id))

async def _stop_fast_scan_task(warehouse_id: str) -> None:
    t = _FAST_TASKS.pop(warehouse_id, None)
    if t:
        t.cancel()
        try:
            await t
        except Exception:
            pass

async def _run_warehouse(warehouse_id: str, shard_idx: int, shard_count: int) -> None:
    sema = asyncio.Semaphore(ROBOTS_CONCURRENCY)
    tick = 0
    _ensure_fast_scan_task_started(warehouse_id)
    ensure_positions_broadcaster_started(warehouse_id, shard_idx, shard_count)
    try:
        while True:
            try:
                async with AppSession() as session:
                    r = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
                    all_robot_ids = list(r.scalars().all())
                if not all_robot_ids:
                    await asyncio.sleep(TICK_INTERVAL)
                    continue

                if all_robot_ids and not wh_snapshot(warehouse_id):
                    async with AppSession() as s:
                        await warmup_or_sync_snapshot(s, warehouse_id, all_robot_ids)
                        await emit_positions_snapshot_force(warehouse_id)
                        if EMIT_AUTOSEND_INIT:
                            await emit_product_scan_on_connect(warehouse_id)

                async with AppSession() as s:
                    await warmup_or_sync_snapshot(s, warehouse_id, all_robot_ids)

                robot_ids = select_robot_batch(warehouse_id, all_robot_ids)
                tid = tick + 1

                async def run_one(rid: str):
                    async with sema:
                        async with AppSession() as s:
                            async with s.begin():
                                await robot_tick(s, rid, tick_id=tid)

                await asyncio.gather(*[run_one(rid) for rid in robot_ids])

                tick += 1
                if tick % 20 == 0:
                    print(f"[{datetime.now().isoformat()}] wh={warehouse_id} tick={tick} robots_tick={len(robot_ids)}/{len(all_robot_ids)}", flush=True)
                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ warehouse loop error (wh={warehouse_id}): {e}", flush=True)
                await asyncio.sleep(0.5)
    finally:
        await _stop_fast_scan_task(warehouse_id)
        await stop_positions_broadcaster(warehouse_id)

async def run_robot_watcher() -> None:
    print(f"🚀 watcher started pid={os.getpid()} interval={TICK_INTERVAL}s", flush=True)
    tasks: Dict[str, asyncio.Task] = {}
    try:
        while True:
            try:
                async with AppSession() as session:
                    rows = await session.execute(
                        select(Warehouse.id).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
                    )
                    wh_ids = set(rows.scalars().all())

                for wid in wh_ids:
                    if wid not in tasks or tasks[wid].done():
                        tasks[wid] = asyncio.create_task(_run_warehouse(wid, shard_idx=0, shard_count=1))

                for wid in list(tasks.keys()):
                    if wid not in wh_ids:
                        tasks[wid].cancel()
                        try:
                            await tasks[wid]
                        except Exception:
                            pass
                        tasks.pop(wid, None)
                        # очистка состояния
                        for d in (WH_SNAPSHOT, WH_SNAPSHOT_VER, WH_LAST_SENT_VER, WH_LAST_SENT_MAP,
                                  LAST_POS_BROADCAST_AT, LAST_ANY_SENT_AT, ELIGIBLE_CACHE,
                                  WH_TICK_COUNTER, WH_ROBOT_OFFSET):
                            d.pop(wid, None)
                        await _stop_fast_scan_task(wid)
                        await stop_positions_broadcaster(wid)

                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ watcher loop error: {e}", flush=True)
                await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        print("🛑 watcher cancelled", flush=True)
    finally:
        for wid, t in list(tasks.items()):
            t.cancel()
            try:
                await t
            except Exception:
                pass
            await _stop_fast_scan_task(wid)
            await stop_positions_broadcaster(wid)
        print("✅ watcher stopped", flush=True)
