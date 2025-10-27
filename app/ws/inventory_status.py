from __future__ import annotations
import asyncio
import queue
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ используем разделённые очереди
from app.ws.ws_manager import EVENTS_COMMON, manager
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_put_common(event: Dict[str, Any]) -> None:
    """
    Кладём событие в 'общую' janus-очередь без блокировок.
    При переполнении вытесняем самый старый элемент этой же очереди.
    """
    q = EVENTS_COMMON.sync_q
    try:
        q.put_nowait(event)
    except queue.Full:
        try:
            q.get_nowait()  # drop-oldest
        except Exception:
            pass
        try:
            q.put_nowait(event)
        except Exception:
            pass


# ===== ПУБЛИКАЦИИ СОБЫТИЙ =====

async def publish_status_avg_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    """
    Публикует событие с картой:
    { "status": среднее значение stock } для заданного склада.
    Пустые/NULL статусы и NULL stock не учитываются.
    В OBSHCHUYU очередь (COMMON), чтобы не конкурировать с телеметрией роботов.
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
            status, max_avg = max(avgs.items(), key=lambda item: item[1])
        else:
            status, max_avg = None, 0.0

        _safe_put_common({
            "type": "inventory.status_avg",
            "warehouse_id": warehouse_id,
            "status": status,
            "max_avg": max_avg,
            "avgs": avgs,          # 👉 можно отдать всю карту, если клиенту нужно
            "ts": _now_iso(),
        })
    except Exception as e:
        print(f"❌ publish_status_avg_snapshot({warehouse_id}) error: {e}")


async def publish_inventory_history_changed(session: AsyncSession, history_id: str) -> None:
    """
    Вызывайте после создания/обновления записи InventoryHistory.
    Быстро находим склад и публикуем обновлённый снэпшот (в COMMON).
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


# ===== ПЕРИОДИЧЕСКИЙ СТРИМЕР (ТОЛЬКО ДЛЯ АКТИВНЫХ КОМНАТ) =====

async def continuous_inventory_status_avg_streamer(interval: float = 30.0) -> None:
    """
    Каждые `interval` секунд считает средние stock по status для каждого склада,
    на который есть хотя бы один WS-подписчик, и публикует событие (в COMMON).
    """
    try:
        while True:
            try:
                rooms = await manager.list_rooms()
                if rooms:
                    async with async_session() as session:
                        for warehouse_id in rooms:
                            await publish_status_avg_snapshot(session, warehouse_id)
            except Exception as inner_err:
                print(f"❌ continuous_inventory_status_avg_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"🔥 continuous_inventory_status_avg_streamer fatal error: {e}")
