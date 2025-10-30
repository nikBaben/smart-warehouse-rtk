from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import load_only
from app.db.session import async_session as AppSession
from app.models.robot import Robot
from state_service import wh_snapshot, SCANNING_UNTIL, SCANNING_STARTED_AT, SCANNING_CELL, SCANNING_FINISHING, update_wh_snapshot_from_robot
from config import FAST_SCAN_INTERVAL_MS, FAST_SCAN_LOOP, SCAN_MAX_DURATION_MS
from scanning_service import safe_finish_scan
from positions_service import maybe_emit_positions_snapshot_inmem

async def fast_scan_loop(warehouse_id: str) -> None:
    if not FAST_SCAN_LOOP:
        return
    interval = max(5, FAST_SCAN_INTERVAL_MS) / 1000.0
    try:
        while True:
            now = datetime.now(timezone.utc)
            scan_rids = [item["robot_id"] for item in wh_snapshot(warehouse_id).values()
                         if (item.get("status") or "").lower() == "scanning"]
            for rid in scan_rids:
                if SCANNING_FINISHING.get(rid):
                    continue
                if rid not in SCANNING_UNTIL:
                    SCANNING_STARTED_AT[rid] = now
                    SCANNING_UNTIL[rid] = now
                    snap = wh_snapshot(warehouse_id).get(rid) or {}
                    SCANNING_CELL.setdefault(rid, (int(snap.get("x") or 0), int(snap.get("y") or 0)))

                until = SCANNING_UNTIL.get(rid)
                start_at = SCANNING_STARTED_AT.get(rid)

                if start_at and (now - start_at).total_seconds() * 1000.0 > SCAN_MAX_DURATION_MS:
                    try:
                        async with AppSession() as s:
                            async with s.begin():
                                rres = await s.execute(
                                    select(Robot).options(load_only(
                                        Robot.id, Robot.warehouse_id, Robot.status,
                                        Robot.battery_level, Robot.current_row, Robot.current_shelf,
                                    )).where(Robot.id == rid)
                                )
                                robot = rres.scalar_one_or_none()
                                if robot:
                                    await safe_finish_scan(s, robot)
                                    await s.flush()
                                    update_wh_snapshot_from_robot(robot)
                                    await maybe_emit_positions_snapshot_inmem(robot.warehouse_id)
                    except Exception as e:
                        print(f"⚠️ fast-scan watchdog error (wh={warehouse_id}, rid={rid}): {e}", flush=True)
                    continue

                if until and now >= until:
                    try:
                        async with AppSession() as s:
                            async with s.begin():
                                rres = await s.execute(
                                    select(Robot).options(load_only(
                                        Robot.id, Robot.warehouse_id, Robot.status,
                                        Robot.battery_level, Robot.current_row, Robot.current_shelf,
                                    )).where(Robot.id == rid)
                                )
                                robot = rres.scalar_one_or_none()
                                if robot:
                                    await safe_finish_scan(s, robot)
                                    await s.flush()
                                    update_wh_snapshot_from_robot(robot)
                                    await maybe_emit_positions_snapshot_inmem(robot.warehouse_id)
                    except Exception as e:
                        print(f"⚠️ fast-scan error (wh={warehouse_id}, rid={rid}): {e}", flush=True)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
