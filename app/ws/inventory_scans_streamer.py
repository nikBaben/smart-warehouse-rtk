from __future__ import annotations
from typing import Optional
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.models.inventory_history import InventoryHistory
from app.db.session import async_session  # тот же паттерн, что и у продуктов


# ——— Вспомогательное ———
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _cutoff_utc(hours: int = 24) -> datetime:
    return _now_utc() - timedelta(hours=hours)


# ——— Паблишеры ———

async def publish_inventory_scanned_24h_snapshot(
    session: AsyncSession,
    warehouse_id: str,
    hours: int = 24,
) -> None:
    """
    Считает количество записей InventoryHistory за последние `hours` часов
    по складу и кладёт событие в очередь WS-брокастера.
    """
    cutoff = _cutoff_utc(hours)
    # «просканированный товар» трактуем как наличие записи в истории для продукта
    stmt = (
        select(func.count(InventoryHistory.id))
        .where(InventoryHistory.warehouse_id == warehouse_id)
        .where(InventoryHistory.created_at >= cutoff)
        .where(InventoryHistory.product_id.is_not(None))
    )
    count = await session.scalar(stmt)
    EVENTS.sync_q.put({
        "type": "inventory.scanned_24h",
        "warehouse_id": warehouse_id,
        "hours": hours,
        "count": int(count or 0),
        "ts": _now_utc().isoformat(),
    })


async def publish_inventory_new_scan(session: AsyncSession, history_id: str, hours: int = 24) -> None:
    """
    Вызывайте при создании новой записи InventoryHistory:
    быстро находим её склад и публикуем обновлённый снэпшот.
    """
    row = await session.execute(
        select(InventoryHistory.warehouse_id)
        .where(InventoryHistory.id == history_id)
    )
    warehouse_id: Optional[str] = row.scalar_one_or_none()
    if not warehouse_id:
        return
    await publish_inventory_scanned_24h_snapshot(session, warehouse_id, hours=hours)


# ——— Периодический стример только для активных комнат ———

async def continuous_inventory_scans_streamer(interval: float = 30.0, hours: int = 24) -> None:
    """
    Каждые `interval` секунд пересчитывает количество просканированных товаров
    за последние `hours` часов и публикует событие для КАЖДОГО склада,
    на который есть хотя бы один WS-подписчик.
    """
    try:
        while True:
            rooms = await manager.list_rooms()
            if rooms:
                async with async_session() as session:
                    for warehouse_id in rooms:
                        await publish_inventory_scanned_24h_snapshot(session, warehouse_id, hours=hours)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
