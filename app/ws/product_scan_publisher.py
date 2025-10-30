# app/ws/initial_product_scan_publisher.py
from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.models.inventory_history import InventoryHistory

LAST_SCANS_LIMIT = int(os.getenv("LAST_SCANS_LIMIT", "20"))
REDIS_DSN = os.getenv("REDIS_DSN", "redis://myapp-redis:6379/0")

try:
    import redis.asyncio as aioredis  # redis>=4.2
except Exception:
    import aioredis  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ih_row_to_payload(row: dict) -> dict:
    out = {k: row.get(k) for k in (
        "id","product_id","robot_id","warehouse_id","current_zone",
        "current_row","current_shelf","name","category","article",
        "stock","min_stock","optimal_stock","status"
    )}
    ca = row.get("created_at")
    if ca is not None:
        out["scanned_at"] = ca if isinstance(ca, str) else ca.isoformat()
    return out

def _last_scans_key(wid: str) -> str:
    return f"wh:{wid}:lastscans"

async def _read_last_scans_from_redis(warehouse_id: str, limit: int) -> List[dict]:
    try:
        r = aioredis.from_url(REDIS_DSN, encoding="utf-8", decode_responses=True,
                              health_check_interval=30, retry_on_timeout=True)
        raw = await r.lrange(_last_scans_key(warehouse_id), 0, max(0, limit-1))
        await r.aclose()
    except Exception:
        raw = []
    scans: List[dict] = []
    for s in raw:
        try:
            scans.append(json.loads(s))
        except Exception:
            pass
    return scans[:limit]  # newest-first

async def _read_last_scans_from_db(session: AsyncSession, warehouse_id: str, limit: int) -> List[dict]:
    # сначала пробуем по created_at DESC, если поля/индекса нет — по id DESC
    try:
        res = await session.execute(
            select(InventoryHistory)
            .where(InventoryHistory.warehouse_id == warehouse_id)
            .order_by(InventoryHistory.created_at.desc())
            .limit(limit)
        )
    except Exception:
        res = await session.execute(
            select(InventoryHistory)
            .where(InventoryHistory.warehouse_id == warehouse_id)
            .order_by(InventoryHistory.id.desc())
            .limit(limit)
        )
    rows = list(res.scalars().all())
    return [
        _ih_row_to_payload({
            "id": ih.id,
            "product_id": ih.product_id,
            "robot_id": ih.robot_id,
            "warehouse_id": ih.warehouse_id,
            "current_zone": ih.current_zone,
            "current_row": ih.current_row,
            "current_shelf": ih.current_shelf,
            "name": ih.name,
            "category": ih.category,
            "article": getattr(ih, "article", None) or "unknown",
            "stock": ih.stock,
            "min_stock": ih.min_stock,
            "optimal_stock": ih.optimal_stock,
            "status": ih.status,
            "created_at": getattr(ih, "created_at", None),
        })
        for ih in rows
    ]

async def fetch_last_scans_snapshot(session: AsyncSession, warehouse_id: str) -> List[dict]:
    scans = await _read_last_scans_from_redis(warehouse_id, LAST_SCANS_LIMIT)
    if scans:
        return scans
    return await _read_last_scans_from_db(session, warehouse_id, LAST_SCANS_LIMIT)

async def publish_initial_product_scan_unicast(session: AsyncSession, warehouse_id: str, session_id: str) -> None:
    """
    Публикует адресный (только для данной WS-сессии) начальный product.scan через Pub/Sub.
    """
    scans = await fetch_last_scans_snapshot(session, warehouse_id)
    payload: Dict[str, Any] = {
        "type": "product.scan",
        "warehouse_id": warehouse_id,
        "robot_id": None,                    # init-снимок
        "scans": scans,                      # newest-first
        "reason": "ws_connect_init",
        "unicast_session_id": session_id,    # ✨ ключ для redis_forwarder
        "ts": _now_iso(),
    }
    bus = await get_bus_for_current_loop()
    await bus.publish(COMMON_CH, payload)
