# app/ws/inventory_scans_streamer.py
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ берём фабрику bus под текущий event loop
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory

# пробуем подтянуть менеджер WS-комнат (есть только в API-процессе)
try:
    from app.ws.ws_manager import manager
except Exception:
    manager = None  # type: ignore


# ——— Вспомогательное ———
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _now_iso() -> str:
    return _now_utc().isoformat()

def _cutoff_utc(hours: int = 24) -> datetime:
    return _now_utc() - timedelta(hours=hours)


# ——— Паблишер в Redis ———
async def publish_inventory_scanned_24h_snapshot(
    session: AsyncSession,
    warehouse_id: str,
    hours: int = 24,
) -> None:
    """
    Считает количество записей InventoryHistory за последние `hours` часов
    по складу и публикует событие в Redis канал COMMON_CH.
    """
    try:
        cutoff = _cutoff_utc(hours)
        stmt = (
            select(func.count(InventoryHistory.id))
            .where(InventoryHistory.warehouse_id == warehouse_id)
            .where(InventoryHistory.created_at >= cutoff)
            .where(InventoryHistory.product_id.is_not(None))
        )
        count = await session.scalar(stmt)

        event: Dict[str, Any] = {
            "type": "inventory.scanned_24h",
            "warehouse_id": warehouse_id,
            "count": int(count or 0),
            "hours": hours,
            "ts": _now_iso(),
        }

        bus = await get_bus_for_current_loop()
        await bus.publish(COMMON_CH, event)
    except Exception as e:
        print(f"❌ publish_inventory_scanned_24h_snapshot({warehouse_id}) error: {e}")


async def publish_inventory_new_scan(session: AsyncSession, history_id: str, hours: int = 24) -> None:
    """
    Вызывайте при создании новой записи InventoryHistory:
    быстро находим её склад и публикуем обновлённый снэпшот в COMMON_CH.
    """
    try:
        row = await session.execute(
            select(InventoryHistory.warehouse_id).where(InventoryHistory.id == history_id)
        )
        warehouse_id: Optional[str] = row.scalar_one_or_none()
        if not warehouse_id:
            return
        await publish_inventory_scanned_24h_snapshot(session, warehouse_id, hours=hours)
    except Exception as e:
        print(f"❌ publish_inventory_new_scan({history_id}) error: {e}")


# ——— Способы получить список «активных» складов ———
async def _get_active_warehouses_by_ws() -> List[str]:
    """Список складов с активными WS-подписчиками (API-режим)."""
    if manager is None:
        return []
    try:
        rooms = await manager.list_rooms()
        return rooms or []
    except Exception:
        return []

async def _get_active_warehouses_by_db(session: AsyncSession) -> List[str]:
    """Список складов, для которых вообще есть записи в InventoryHistory (worker-режим)."""
    rows = await session.execute(select(distinct(InventoryHistory.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]


# ——— Периодический стример ———
async def continuous_inventory_scans_streamer(
    interval: float = 30.0,
    hours: int = 24,
    use_ws_rooms: bool = False,
) -> None:
    """
    Каждые `interval` секунд пересчитывает количество просканированных товаров за последние `hours` часов
    и публикует событие для выбранных складов в Redis (COMMON_CH).

    use_ws_rooms=True  → брать только комнаты с активными WS-подписчиками (API-процесс).
    use_ws_rooms=False → брать склады из БД (worker-процесс).
    """
    print(f"🚀 continuous_inventory_scans_streamer(interval={interval}, hours={hours}, use_ws_rooms={use_ws_rooms})")
    try:
        while True:
            try:
                if use_ws_rooms:
                    wh_ids = await _get_active_warehouses_by_ws()
                    if not wh_ids:
                        await asyncio.sleep(interval)
                        continue
                    async with async_session() as session:
                        for wid in wh_ids:
                            await publish_inventory_scanned_24h_snapshot(session, wid, hours=hours)
                else:
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for wid in wh_ids:
                            await publish_inventory_scanned_24h_snapshot(session, wid, hours=hours)

            except Exception as inner_err:
                print(f"❌ continuous_inventory_scans_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("🛑 continuous_inventory_scans_streamer cancelled")
    except Exception as e:
        print(f"🔥 continuous_inventory_scans_streamer fatal error: {e}")
