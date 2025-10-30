from __future__ import annotations
import os, json
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from uuid import uuid4

from sqlalchemy import insert, update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session as AppSession
from app.models.inventory_history import InventoryHistory
from app.models.robot_history import RobotHistory
from app.models.robot import Robot
from app.models.product import Product

from config import (
    LAST_SCANS_LIMIT, RESCAN_COOLDOWN, SCAN_DURATION, SCAN_MAX_DURATION_MS
)
from coords_service import shelf_num_to_str
from state_service import (
    SCANNING_CELL, SCANNING_UNTIL, SCANNING_STARTED_AT, update_wh_snapshot_from_robot,
    TARGETS, scan_lock, SCANNING_FINISHING
)
from redis_coord_service import get_redis, last_scans_key, claim_global, free_claim_global
from events_service import emit

# ===== Кеш последних сканов (в памяти процесса)
_LAST_SCANS_CACHE: Dict[str, deque] = {}

def _last_scans_deque(wid: str) -> deque:
    dq = _LAST_SCANS_CACHE.get(wid)
    if dq is None or dq.maxlen != LAST_SCANS_LIMIT:
        dq = _LAST_SCANS_CACHE[wid] = deque(maxlen=LAST_SCANS_LIMIT)
    return dq

def _ih_row_to_payload(row: dict) -> dict:
    out = {
        "id": row["id"],
        "product_id": row["product_id"],
        "robot_id": row["robot_id"],
        "warehouse_id": row["warehouse_id"],
        "current_zone": row.get("current_zone"),
        "current_row": row.get("current_row"),
        "current_shelf": row.get("current_shelf"),
        "name": row.get("name"),
        "category": row.get("category"),
        "article": row.get("article"),
        "stock": row.get("stock"),
        "min_stock": row.get("min_stock"),
        "optimal_stock": row.get("optimal_stock"),
        "status": row.get("status"),
    }
    if "created_at" in row and row["created_at"] is not None:
        out["scanned_at"] = row["created_at"] if isinstance(row["created_at"], str) else row["created_at"].isoformat()
    return out

async def _append_last_scans(wid: str, items: List[dict]) -> None:
    if not items:
        return
    dq = _last_scans_deque(wid)
    for it in items:
        dq.append(it)
    # Redis (newest слева)
    try:
        r = await get_redis()
        if r is not None:
            key = last_scans_key(wid)
            pipe = r.pipeline()
            for it in reversed(items):
                pipe.lpush(key, json.dumps(it, ensure_ascii=False))
            pipe.ltrim(key, 0, LAST_SCANS_LIMIT - 1)
            await pipe.execute()
    except Exception:
        pass

async def _get_last_scans(wid: str, session: Optional[AsyncSession] = None) -> List[dict]:
    # 1) Redis
    try:
        r = await get_redis()
        if r is not None:
            raw = await r.lrange(last_scans_key(wid), 0, LAST_SCANS_LIMIT - 1)
            scans = []
            for s in raw:
                try:
                    scans.append(json.loads(s))
                except Exception:
                    pass
            if scans:
                dq = _last_scans_deque(wid)
                dq.clear()
                for it in reversed(scans):
                    dq.append(it)
                return scans
    except Exception:
        pass

    dq = _last_scans_deque(wid)
    if dq:
        return list(dq)[-LAST_SCANS_LIMIT:][::-1]

    if session is not None:
        try:
            try:
                res = await session.execute(
                    select(InventoryHistory)
                    .where(InventoryHistory.warehouse_id == wid)
                    .order_by(InventoryHistory.created_at.desc())
                    .limit(LAST_SCANS_LIMIT)
                )
            except Exception:
                res = await session.execute(
                    select(InventoryHistory)
                    .where(InventoryHistory.warehouse_id == wid)
                    .order_by(InventoryHistory.id.desc())
                    .limit(LAST_SCANS_LIMIT)
                )
            rows = res.scalars().all()
            scans = []
            for ih in rows:
                scans.append(_ih_row_to_payload({
                    "id": ih.id, "product_id": ih.product_id,
                    "robot_id": ih.robot_id, "warehouse_id": ih.warehouse_id,
                    "current_zone": ih.current_zone, "current_row": ih.current_row,
                    "current_shelf": ih.current_shelf, "name": ih.name,
                    "category": ih.category, "article": ih.article,
                    "stock": ih.stock, "min_stock": ih.min_stock,
                    "optimal_stock": ih.optimal_stock, "status": ih.status,
                    **({"created_at": getattr(ih, "created_at")} if hasattr(ih, "created_at") else {}),
                }))
            await _append_last_scans(wid, list(reversed(scans)))
            return scans
        except Exception:
            pass
    return []

async def _emit_last_scans(session: AsyncSession, warehouse_id: str, robot_id: Optional[str], reason: Optional[str] = None, scans_override: Optional[List[dict]] = None) -> None:
    scans = scans_override if scans_override is not None else await _get_last_scans(warehouse_id, session=session)
    payload = {
        "type": "product.scan",
        "warehouse_id": warehouse_id,
        "robot_id": robot_id,
        "scans": scans,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        payload["reason"] = reason
    await emit(payload)

# Публичный хук (ws connect)
async def emit_product_scan_on_connect(warehouse_id: str, robot_id: Optional[str] = None) -> None:
    async with AppSession() as s:
        async with s.begin():
            await _emit_last_scans(s, warehouse_id, robot_id, reason="ws_connect_init")

async def _log_robot_status(session: AsyncSession, robot: Robot, status: str) -> None:
    try:
        await session.execute(
            insert(RobotHistory).values(
                id=str(uuid4()),
                robot_id=robot.id,
                warehouse_id=robot.warehouse_id,
                status=status,
                created_at=datetime.now(timezone.utc),
            )
        )
    except Exception as e:
        print(f"⚠️ robot status log failed rid={robot.id} status={status}: {e}", flush=True)

async def start_scan(robot: Robot, x: int, y: int) -> None:
    robot.status = "scanning"
    SCANNING_CELL[robot.id] = (x, y)
    now = datetime.now(timezone.utc)
    SCANNING_STARTED_AT[robot.id] = now
    SCANNING_UNTIL[robot.id] = now + SCAN_DURATION
    update_wh_snapshot_from_robot(robot)

async def _finish_scan(session: AsyncSession, robot: Robot) -> None:
    rx, ry = SCANNING_CELL.pop(robot.id, (int(robot.current_shelf or 0), int(robot.current_row or 0)))
    SCANNING_UNTIL.pop(robot.id, None)
    SCANNING_STARTED_AT.pop(robot.id, None)

    shelf = shelf_num_to_str(rx)
    if shelf == "0":
        await free_claim_global(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        update_wh_snapshot_from_robot(robot)
        await _log_robot_status(session, robot, "idle")
        await _emit_last_scans(session, robot.warehouse_id, robot.id, reason="no_valid_shelf")
        return

    cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
    # выборка продуктов
    res = await session.execute(
        select(Product)
        .where(
            Product.warehouse_id == robot.warehouse_id,
            Product.current_row == ry,
            (Product.current_shelf == shelf) | (Product.current_shelf.ilike(shelf)),
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
    )
    products = list(res.scalars().all())
    now_dt = datetime.now(timezone.utc); now_iso = now_dt.isoformat()

    if not products:
        await free_claim_global(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        update_wh_snapshot_from_robot(robot)
        await _log_robot_status(session, robot, "idle")
        await _emit_last_scans(session, robot.warehouse_id, robot.id, reason="under_cooldown")
        return

    rows: List[dict] = []
    payload_for_cache: List[dict] = []
    for p in products:
        stock = int(p.stock or 0)
        status = "ok"
        if p.min_stock is not None and stock < p.min_stock:
            status = "critical"
        elif p.optimal_stock is not None and stock < p.optimal_stock:
            status = "low"
        row_dict = {
            "id": f"ih_{os.urandom(6).hex()}",
            "product_id": p.id,
            "robot_id": robot.id,
            "warehouse_id": robot.warehouse_id,
            "current_zone": getattr(p, "current_zone", "Хранение"),
            "current_row": ry,
            "current_shelf": shelf,
            "name": p.name,
            "category": p.category,
            "article": getattr(p, "article", None) or "unknown",
            "stock": stock,
            "min_stock": p.min_stock,
            "optimal_stock": p.optimal_stock,
            "status": status,
        }
        rows.append(row_dict)
        payload_for_cache.append(_ih_row_to_payload({**row_dict, "created_at": now_iso}))

    await session.execute(insert(InventoryHistory), rows)
    await session.execute(
        update(Product)
        .where(Product.id.in_([r["product_id"] for r in rows]))
        .values(last_scanned_at=now_dt)
    )
    await _append_last_scans(robot.warehouse_id, payload_for_cache)
    scans20 = await _get_last_scans(robot.warehouse_id)
    await _emit_last_scans(session, robot.warehouse_id, robot.id, scans_override=scans20)

    await free_claim_global(robot.warehouse_id, (rx, ry))
    robot.status = "idle"
    update_wh_snapshot_from_robot(robot)
    await _log_robot_status(session, robot, "idle")

async def safe_finish_scan(session: AsyncSession, robot: Robot) -> None:
    async with scan_lock(robot.id):
        if SCANNING_FINISHING.get(robot.id):
            return
        if (robot.id not in SCANNING_UNTIL) and (robot.status or "").lower() != "scanning":
            return
        SCANNING_FINISHING[robot.id] = True
    try:
        await _finish_scan(session, robot)
    except Exception as e:
        rx, ry = int(robot.current_shelf or 0), int(robot.current_row or 0)
        SCANNING_CELL.pop(robot.id, None)
        SCANNING_UNTIL.pop(robot.id, None)
        SCANNING_STARTED_AT.pop(robot.id, None)
        await free_claim_global(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        await session.flush()
        update_wh_snapshot_from_robot(robot)
        await _log_robot_status(session, robot, "idle")
        try:
            await _emit_last_scans(session, robot.warehouse_id, robot.id, reason="scan_error")
        except Exception:
            pass
        print(f"⚠️ safe_finish_scan: error rid={robot.id}: {e}", flush=True)
    finally:
        async with scan_lock(robot.id):
            SCANNING_FINISHING.pop(robot.id, None)
