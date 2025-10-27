from __future__ import annotations
from typing import Optional, Dict, Any
import asyncio
import queue
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# ⚠️ используем разделённые очереди
from app.ws.ws_manager import EVENTS_COMMON, manager
from app.models.inventory_history import InventoryHistory
from app.db.session import async_session  # тот же паттерн, что и у продуктов


# ——— Вспомогательное ———
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _now_iso() -> str:
    return _now_utc().isoformat()

def _cutoff_utc(hours: int = 24) -> datetime:
    return _now_utc() - timedelta(hours=hours)

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
            q.get_nowait()
        except Exception:
            pass
        try:
            q.put_nowait(event)
        except Exception:
            pass


# ——— Паблишеры ———

async def publish_inventory_scanned_24h_snapshot(
    session: AsyncSession,
    warehouse_id: str,
    hours: int = 24,
) -> None:
    """
    Считает количество записей InventoryHistory за последние `hours` часов
    по складу и кладёт событие в ОБЩУЮ очередь WS-брокастера.
    """
    try:
        cutoff = _cutoff_utc(hours)
        # «просканированный товар» трактуем как наличие записи в истории для продукта
        stmt = (
            select(func.count(InventoryHistory.id))
            .where(InventoryHistory.warehouse_id == warehouse_id)
            .where(InventoryHistory.created_at >= cutoff)
            .where(InventoryHistory.product_id.is_not(None))
        )
        count = await session.scalar(stmt)
        _safe_put_common({
            "type": "inventory.scanned_24h",
            "warehouse_id": warehouse_id,
            "count": int(count or 0),
            "hours": hours,
            "ts": _now_iso(),
        })
    except Exception as e:
        print(f"❌ publish_inventory_scanned_24h_snapshot({warehouse_id}) error: {e}")


async def publish_inventory_new_scan(session: AsyncSession, history_id: str, hours: int = 24) -> None:
    """
    Вызывайте при создании новой записи InventoryHistory:
    быстро находим её склад и публикуем обновлённый снэпшот.
    """
    try:
        row = await session.execute(
            select(InventoryHistory.warehouse_id)
            .where(InventoryHistory.id == history_id)
        )
        warehouse_id: Optional[str] = row.scalar_one_or_none()
        if not warehouse_id:
            return
        await publish_inventory_scanned_24h_snapshot(session, warehouse_id, hours=hours)
    except Exception as e:
        print(f"❌ publish_inventory_new_scan({history_id}) error: {e}")


# ——— Периодический стример только для активных комнат ———

async def continuous_inventory_scans_streamer(interval: float = 30.0, hours: int = 24) -> None:
    """
    Каждые `interval` секунд пересчитывает количество просканированных товаров
    за последние `hours` часов и публикует событие для КАЖДОГО склада,
    на который есть хотя бы один WS-подписчик (в ОБЩУЮ очередь).
    """
    try:
        while True:
            try:
                rooms = await manager.list_rooms()
                if rooms:
                    async with async_session() as session:
                        for warehouse_id in rooms:
                            await publish_inventory_scanned_24h_snapshot(session, warehouse_id, hours=hours)
            except Exception as inner_err:
                print(f"❌ continuous_inventory_scans_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"🔥 continuous_inventory_scans_streamer fatal error: {e}")
