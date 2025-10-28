from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== ПУБЛИКАЦИИ СОБЫТИЙ =====

async def publish_critical_unique_articles_snapshot(
    session: AsyncSession,
    warehouse_id: str,
) -> None:
    """
    Публикует в очередь событие с количеством уникальных товаров (по article)
    в таблице InventoryHistory для данного склада, где status='critical'.
    """
    stmt = (
        select(func.count(func.distinct(InventoryHistory.article)))
        .where(InventoryHistory.warehouse_id == warehouse_id)
        .where(func.lower(InventoryHistory.status) == "critical")
    )
    count = await session.scalar(stmt)

    EVENTS.sync_q.put({
        "type": "inventory.critical_unique",
        "warehouse_id": warehouse_id,
        "unique_articles": int(count or 0),
    })


async def publish_inventory_history_changed(session: AsyncSession, history_id: str) -> None:
    """
    Вызывайте это после создания/обновления записи InventoryHistory.
    Мы быстро находим склад и публикуем обновлённый снэпшот.
    """
    row = await session.execute(
        select(InventoryHistory.warehouse_id)
        .where(InventoryHistory.id == history_id)
    )
    warehouse_id: Optional[str] = row.scalar_one_or_none()
    if not warehouse_id:
        return
    await publish_critical_unique_articles_snapshot(session, warehouse_id)


# ===== ПЕРИОДИЧЕСКИЙ СТРИМЕР (ТОЛЬКО ДЛЯ АКТИВНЫХ КОМНАТ) =====

async def continuous_inventory_critical_streamer(interval: float = 30.0) -> None:
    """
    Каждые `interval` секунд пересчитывает количество уникальных critical-товаров
    и публикует событие для КАЖДОГО склада, на который есть хотя бы один WS-подписчик.
    """
    try:
        while True:
            rooms = await manager.list_rooms()  # список warehouse_id с активными подписчиками
            if rooms:
                async with async_session() as session:
                    for warehouse_id in rooms:
                        await publish_critical_unique_articles_snapshot(session, warehouse_id)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
