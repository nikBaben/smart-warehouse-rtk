# app/ws/products_events.py
from __future__ import annotations
from typing import Optional, List, Dict, Any

import asyncio
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ вместо синглтона bus используем фабрику под текущий event loop
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.db.session import async_session
from app.models.product import Product

# Менеджер комнат (есть только в API-процессе)
try:
    from app.ws.ws_manager import manager
except Exception:
    manager = None  # type: ignore


from datetime import datetime

def _pack_product(p: Product) -> dict:
    scanned_at = getattr(p, "scanned_at", None)
    shelf_value = getattr(p, "current_shelf", None)
    last_update = getattr(p, "last_update", None)

    # 🔤 Преобразуем букву в номер по алфавиту
    if isinstance(shelf_value, str) and len(shelf_value) == 1 and shelf_value.isalpha():
        current_shelf = ord(shelf_value.upper()) - ord("A") + 1
    else:
        try:
            current_shelf = int(shelf_value)
        except (TypeError, ValueError):
            current_shelf = 0

    # 🕒 Разница во времени в минутах с последнего обновления
    if isinstance(last_update, datetime):
        minutes_since_update = int((datetime.now() - last_update).total_seconds() / 60)
    else:
        minutes_since_update = None  # если даты нет

    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "warehouse_id": p.warehouse_id,
        "current_zone": getattr(p, "current_zone", None),
        "status": p.status,
        "current_row": getattr(p, "current_row", 0),
        "current_shelf": current_shelf,
        "stock": getattr(p, "stock", None),
        "min_stock": getattr(p, "min_stock", None),
        "optimal_stock": getattr(p, "optimal_stock", None),
        "created_at": minutes_since_update,  # ⏱ минуты с момента последнего сканирования
    }




# ---------- публикации ----------

async def publish_product_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    rows = await session.execute(select(Product).where(Product.warehouse_id == warehouse_id))
    items = [_pack_product(p) for p in rows.scalars().all()]
    bus = await get_bus_for_current_loop()
    await bus.publish(COMMON_CH, {
        "type": "product.snapshot",
        "warehouse_id": warehouse_id,
        "items": items,
    })


async def publish_product_change(session: AsyncSession, product_id: str) -> None:
    row = await session.execute(select(Product).where(Product.id == product_id))
    p: Optional[Product] = row.scalar_one_or_none()
    if not p:
        return
    bus = await get_bus_for_current_loop()
    await bus.publish(COMMON_CH, {
        "type": "product.changed",
        "warehouse_id": p.warehouse_id,
        "item": _pack_product(p),
    })


async def publish_product_deleted(product_id: str, warehouse_id: str) -> None:
    bus = await get_bus_for_current_loop()
    await bus.publish(COMMON_CH, {
        "type": "product.deleted",
        "warehouse_id": warehouse_id,
        "product_id": product_id,
    })


# ---------- выбор активных складов ----------

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
    """Список складов, по которым есть товары (worker-режим)."""
    rows = await session.execute(select(distinct(Product.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]


# ---------- периодический стример ----------

async def continuous_product_snapshot_streamer(
    interval: float = 10.0,
    use_ws_rooms: bool = False,
) -> None:
    """
    Каждые `interval` секунд публикует актуальный snapshot товаров.
    use_ws_rooms=True  → брать только комнаты с активными WS-подписчиками (API-процесс).
    use_ws_rooms=False → брать склады из БД (worker-процесс).
    """
    print(f"🚀 continuous_product_snapshot_streamer(interval={interval}, use_ws_rooms={use_ws_rooms})")
    try:
        while True:
            try:
                if use_ws_rooms:
                    wh_ids = await _get_active_warehouses_by_ws()
                    if not wh_ids:
                        await asyncio.sleep(interval)
                        continue
                    async with async_session() as session:
                        for warehouse_id in wh_ids:
                            await publish_product_snapshot(session, warehouse_id)
                else:
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for warehouse_id in wh_ids:
                            await publish_product_snapshot(session, warehouse_id)
            except Exception as inner_err:
                print(f"❌ continuous_product_snapshot_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("🛑 continuous_product_snapshot_streamer cancelled")
    except Exception as e:
        print(f"🔥 continuous_product_snapshot_streamer fatal error: {e}")
