from __future__ import annotations
from typing import Optional, List
from sqlalchemy import select
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.ws.ws_manager import EVENTS, manager
from app.models.product import Product
from app.db.session import async_session  # для стримера (фоновой задачи)


def _pack_product(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "warehouse_id": p.warehouse_id,
        "current_zone": getattr(p, "current_zone", None),
        "current_row": getattr(p, "current_row", 0),
        "current_shelf": getattr(p, "current_shelf", "A"),
        "stock": getattr(p, "stock", None),
        "min_stock": getattr(p, "min_stock", None),
        "optimal_stock": getattr(p, "optimal_stock", None),
        "created_at": getattr(p, "created_at", None).isoformat() if getattr(p, "created_at", None) else None,
    }

#Полный снимок товаров склада — отправляем при подключении клиента И/ИЛИ периодически.
async def publish_product_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    rows = await session.execute(select(Product).where(Product.warehouse_id == warehouse_id))
    items = [_pack_product(p) for p in rows.scalars().all()]
    EVENTS.sync_q.put({
        "type": "product.snapshot",
        "warehouse_id": warehouse_id,
        "items": items,
    })

#Дельта-событие об изменении товара (create/update/move/stock-change).
async def publish_product_change(session: AsyncSession, product_id: str) -> None:
    row = await session.execute(select(Product).where(Product.id == product_id))
    p: Optional[Product] = row.scalar_one_or_none()
    if not p:
        return
    EVENTS.sync_q.put({
        "type": "product.changed",
        "warehouse_id": p.warehouse_id,
        "item": _pack_product(p),
    })

#Удаление товара.
def publish_product_deleted(product_id: str, warehouse_id: str) -> None:
    EVENTS.sync_q.put({
        "type": "product.deleted",
        "warehouse_id": warehouse_id,
        "product_id": product_id,
    })

# “Постоянная” отправка снапшота
#Периодически (каждые `interval` секунд) рассылает актуальный snapshot товаров
# для КАЖДОГО склада, на который сейчас есть хотя бы один подписчик (WS-клиент).
# Запусти это как фон-таск наряду с robot_events_broadcaster().
async def continuous_product_snapshot_streamer(interval: float = 2.0) -> None:
    
    try:
        while True:
            # берём текущий список складов, на которые есть подписчики
            rooms = await manager.list_rooms()
            if rooms:
                async with async_session() as session:
                    for warehouse_id in rooms:
                        # отправляем snapshot в очередь — бродкастер доставит всем подписчикам этого склада
                        await publish_product_snapshot(session, warehouse_id)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
