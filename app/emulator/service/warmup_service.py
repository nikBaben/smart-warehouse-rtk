from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Dict
from sqlalchemy import select
from sqlalchemy.orm import load_only
from app.models.robot import Robot
from coords_service import shelf_num_to_str
from state_service import wh_snapshot, WH_SNAPSHOT_VER, ROBOT_WH

async def warmup_or_sync_snapshot(session, warehouse_id: str, robot_ids: List[str] | None = None) -> None:
    if robot_ids is None:
        r = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
        robot_ids = list(r.scalars().all())
    if robot_ids:
        res = await session.execute(
            select(Robot.id, Robot.current_row, Robot.current_shelf, Robot.battery_level, Robot.status)
            .where(Robot.warehouse_id == warehouse_id, Robot.id.in_(robot_ids))
        )
        db_rows = {rid: (shelf, row, battery, status) for rid, row, shelf, battery, status in res.all()}
    else:
        db_rows = {}
    changed = False
    snap = wh_snapshot(warehouse_id)

    if robot_ids is not None:
        for rid in list(snap.keys()):
            if rid not in robot_ids:
                snap.pop(rid, None)
                changed = True

    for rid in robot_ids:
        x, y, battery, status = db_rows.get(rid, (0, 0, 0.0, "idle"))
        ROBOT_WH[rid] = warehouse_id
        x_int, y_int = int(x or 0), int(y or 0)
        now_iso = datetime.now(timezone.utc).isoformat()
        new_item = {
            "robot_id": rid,
            "x": x_int, "y": y_int,
            "shelf": shelf_num_to_str(x_int),
            "battery_level": round(float(battery or 0.0), 1),
            "status": status or "idle",
            "updated_at": (snap.get(rid) or {}).get("updated_at") or now_iso,
        }
        if snap.get(rid) != new_item:
            snap[rid] = new_item
            changed = True
    if changed:
        WH_SNAPSHOT_VER[warehouse_id] = WH_SNAPSHOT_VER.get(warehouse_id, 0) + 1
