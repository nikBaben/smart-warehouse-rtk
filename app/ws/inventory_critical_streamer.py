# app/ws/inventory_critical_streamer.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ берём фабрику bus, а не синглтон
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory

# Опционально: менеджер WS (есть только в API-процессе)
try:
    from app.ws.ws_manager import manager
except Exception:
    manager = None  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== ПУБЛИКАЦИЯ СОБЫТИЯ В REDIS =====
async def publish_critical_unique_articles_snapshot(
    session: AsyncSession,
    warehouse_id: str,
) -> None:
    """
    Публикует событие с количеством уникальных товаров (по article)
    в InventoryHistory для склада, где status='critical'.
    Событие уходит в Redis (COMMON_CH).
    """
    try:
        stmt = (
            select(func.count(func.distinct(InventoryHistory.article)))
            .where(InventoryHistory.warehouse_id == warehouse_id)
            .where(func.lower(InventoryHistory.status) == "critical")
        )
        count = await session.scalar(stmt)

        event: Dict[str, Any] = {
            "type": "inventory.critical_unique",
            "warehouse_id": warehouse_id,
            "unique_articles": int(count or 0),
            "ts": _now_iso(),
        }

        # ✅ получаем bus под текущий event loop
        bus = await get_bus_for_current_loop()
        await bus.publish(COMMON_CH, event)
    except Exception as e:
        # не роняем поток — просто лог
        print(f"❌ publish_critical_unique_articles_snapshot({warehouse_id}) error: {e}")


async def publish_inventory_history_changed(session: AsyncSession, history_id: str) -> None:
    """
    Вызывайте после создания/обновления InventoryHistory.
    Быстро находим склад и публикуем обновлённый снэпшот (в COMMON_CH).
    """
    try:
        row = await session.execute(
            select(InventoryHistory.warehouse_id)
            .where(InventoryHistory.id == history_id)
        )
        warehouse_id: Optional[str] = row.scalar_one_or_none()
        if not warehouse_id:
            return

        await publish_critical_unique_articles_snapshot(session, warehouse_id)
    except Exception as e:
        print(f"❌ publish_inventory_history_changed({history_id}) error: {e}")


# ===== Вспомогательные выборки активных складов =====
async def _get_active_warehouses_by_ws() -> List[str]:
    """
    Список складов, на которые есть WS-подписчики (API-режим).
    """
    if manager is None:
        return []
    try:
        rooms = await manager.list_rooms()
        return rooms or []
    except Exception:
        return []


async def _get_active_warehouses_by_db(session: AsyncSession) -> List[str]:
    """
    Список складов, для которых вообще есть записи в InventoryHistory (worker-режим).
    При желании можно ограничить по времени (например, за последние 24ч).
    """
    rows = await session.execute(select(distinct(InventoryHistory.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]


# ===== ПЕРИОДИЧЕСКИЙ СТРИМЕР =====
async def continuous_inventory_critical_streamer(
    interval: float = 30.0,
    use_ws_rooms: bool = False,
) -> None:
    """
    Каждые `interval` секунд пересчитывает количество уникальных critical-товаров
    и публикует событие для складов.

    Режимы:
      - use_ws_rooms=True  → брать только склады с активными WS-подписчиками (логично для API-процесса).
      - use_ws_rooms=False → брать активные склады из БД (логично для worker-процесса).

    Все события публикуются в Redis канал COMMON_CH.
    """
    print(f"🚀 continuous_inventory_critical_streamer(interval={interval}, use_ws_rooms={use_ws_rooms})")
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
                            await publish_critical_unique_articles_snapshot(session, wid)
                else:
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for wid in wh_ids:
                            await publish_critical_unique_articles_snapshot(session, wid)
            except Exception as inner_err:
                print(f"❌ continuous_inventory_critical_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # штатная остановка фоновой задачи
        print("🛑 continuous_inventory_critical_streamer cancelled")
    except Exception as e:
        print(f"🔥 continuous_inventory_critical_streamer fatal error: {e}")
