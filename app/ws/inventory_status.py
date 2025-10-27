# app/ws/inventory_status.py
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ вместо синглтона bus — фабрика под текущий event loop
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory

# пробуем подтянуть менеджер WS-комнат (есть только в API-процессе)
try:
    from app.ws.ws_manager import manager
except Exception:
    manager = None  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== ПУБЛИКАЦИЯ СОБЫТИЙ =====
async def publish_status_avg_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    """
    Публикует событие:
      {
        type: 'inventory.status_avg',
        warehouse_id,
        status,        # статус с максимальным средним stock
        max_avg,       # его значение
        avgs: {...},   # карта {status -> avg(stock)}
        ts
      }
    Пустые/NULL статусы и NULL stock не учитываются.
    """
    try:
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
        if avgs:
            top_status, max_avg = max(avgs.items(), key=lambda item: item[1])
        else:
            top_status, max_avg = None, 0.0

        payload: Dict[str, Any] = {
            "type": "inventory.status_avg",
            "warehouse_id": warehouse_id,
            "status": top_status,
            "max_avg": max_avg,
            "avgs": avgs,
            "ts": _now_iso(),
        }

        # ✅ получаем bus под текущий event loop
        bus = await get_bus_for_current_loop()
        await bus.publish(COMMON_CH, payload)
    except Exception as e:
        print(f"❌ publish_status_avg_snapshot({warehouse_id}) error: {e}")


async def publish_inventory_history_changed(session: AsyncSession, history_id: str) -> None:
    """
    Вызывайте после создания/обновления записи InventoryHistory — публикуем обновлённый снапшот.
    """
    try:
        row = await session.execute(
            select(InventoryHistory.warehouse_id)
            .where(InventoryHistory.id == history_id)
        )
        warehouse_id: Optional[str] = row.scalar_one_or_none()
        if not warehouse_id:
            return
        await publish_status_avg_snapshot(session, warehouse_id)
    except Exception as e:
        print(f"❌ publish_inventory_history_changed({history_id}) error: {e}")


# ---- выбор активных складов ----
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
    """Список складов, для которых есть записи в InventoryHistory (worker-режим)."""
    rows = await session.execute(select(distinct(InventoryHistory.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]


# ===== ПЕРИОДИЧЕСКИЙ СТРИМЕР =====
async def continuous_inventory_status_avg_streamer(
    interval: float = 30.0,
    use_ws_rooms: bool = False,
) -> None:
    """
    Каждые `interval` секунд считает средние stock по status и публикует событие в Redis (COMMON_CH).
    use_ws_rooms=True  → брать только комнаты с активными WS-подписчиками (API-процесс).
    use_ws_rooms=False → брать склады из БД (worker-процесс).
    """
    print(f"🚀 continuous_inventory_status_avg_streamer(interval={interval}, use_ws_rooms={use_ws_rooms})")
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
                            await publish_status_avg_snapshot(session, wid)
                else:
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for wid in wh_ids:
                            await publish_status_avg_snapshot(session, wid)
            except Exception as inner_err:
                print(f"❌ continuous_inventory_status_avg_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("🛑 continuous_inventory_status_avg_streamer cancelled")
    except Exception as e:
        print(f"🔥 continuous_inventory_status_avg_streamer fatal error: {e}")
