from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== ПУБЛИКАЦИИ СОБЫТИЙ =====

async def publish_status_avg_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    """
    Публикует в очередь событие с картой:
    { "status": среднее значение stock } для заданного склада.
    Пустые/NULL статусы и NULL stock не учитываются.
    """
    stmt = (
        select(
            func.lower(InventoryHistory.status).label("status"),
            func.avg(InventoryHistory.stock).label("avg_stock"),
        )
        .where(InventoryHistory.warehouse_id == warehouse_id)
        .where(InventoryHistory.status.is_not(None))
        .where(func.length(func.trim(InventoryHistory.status)) > 0)
        .where(InventoryHistory.stock.is_not(None))
        .group_by(func.lower(InventoryHistory.status))
    )

    rows = (await session.execute(stmt)).all()
    avgs: Dict[str, float] = {status: round(float(avg or 0.0), 2) for status, avg in rows}

    EVENTS.sync_q.put({
        "type": "inventory.status_avg",
        "warehouse_id": warehouse_id,
        "avgs": avgs,                  # пример: {"critical": 3.5, "ok": 42.0}
        "metric": "avg(stock)",        # чтобы на клиенте было понятно, что усредняли
        "ts": _now_iso(),
    })


async def publish_inventory_history_changed(session: AsyncSession, history_id: str) -> None:
    """
    Вызывайте после создания/обновления записи InventoryHistory.
    Быстро находим склад и публикуем обновлённый снэпшот.
    """
    row = await session.execute(
        select(InventoryHistory.warehouse_id)
        .where(InventoryHistory.id == history_id)
    )
    warehouse_id: Optional[str] = row.scalar_one_or_none()
    if not warehouse_id:
        return
    await publish_status_avg_snapshot(session, warehouse_id)


# ===== ПЕРИОДИЧЕСКИЙ СТРИМЕР (ТОЛЬКО ДЛЯ АКТИВНЫХ КОМНАТ) =====

async def continuous_inventory_status_avg_streamer(interval: float = 30.0) -> None:
    """
    Каждые `interval` секунд считает средние stock по status для каждого склада,
    на который есть хотя бы один WS-подписчик, и публикует событие.
    """
    try:
        while True:
            rooms = await manager.list_rooms()
            if rooms:
                async with async_session() as session:
                    for warehouse_id in rooms:
                        await publish_status_avg_snapshot(session, warehouse_id)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
