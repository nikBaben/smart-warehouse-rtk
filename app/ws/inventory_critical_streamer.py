from __future__ import annotations
import asyncio
import queue
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# ⚠️ Импортируем разделённые очереди и менеджер комнат
from app.ws.ws_manager import EVENTS_COMMON, manager
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_put_common(event: Dict[str, Any]) -> None:
    """
    Кладём событие в 'общую' janus-очередь (не роботную) без блокировок.
    При переполнении вытесняем самый старый элемент этой же очереди.
    """
    q = EVENTS_COMMON.sync_q  # синхронная сторона janus.Queue
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

async def publish_critical_unique_articles_snapshot(
    session: AsyncSession,
    warehouse_id: str,
) -> None:
    """
    Публикует событие с количеством уникальных товаров (по article)
    в InventoryHistory для склада, где status='critical'.
    Событие идёт в ОБЩУЮ очередь (COMMON), чтобы не конкурировать с телеметрией роботов.
    """
    try:
        stmt = (
            select(func.count(func.distinct(InventoryHistory.article)))
            .where(InventoryHistory.warehouse_id == warehouse_id)
            .where(func.lower(InventoryHistory.status) == "critical")
        )
        count = await session.scalar(stmt)

        _safe_put_common({
            "type": "inventory.critical_unique",
            "warehouse_id": warehouse_id,
            "unique_articles": int(count or 0),
            "ts": _now_iso(),
        })
    except Exception as e:
        # не роняем поток — просто лог
        print(f"❌ publish_critical_unique_articles_snapshot({warehouse_id}) error: {e}")


async def publish_inventory_history_changed(session: AsyncSession, history_id: str) -> None:
    """
    Вызывайте после создания/обновления InventoryHistory.
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

        await publish_critical_unique_articles_snapshot(session, warehouse_id)
    except Exception as e:
        print(f"❌ publish_inventory_history_changed({history_id}) error: {e}")


# ===== ПЕРИОДИЧЕСКИЙ СТРИМЕР (ТОЛЬКО ДЛЯ АКТИВНЫХ КОМНАТ) =====

async def continuous_inventory_critical_streamer(interval: float = 30.0) -> None:
    """
    Каждые `interval` секунд пересчитывает количество уникальных critical-товаров
    и публикует событие для КАЖДОГО склада, на который есть хотя бы один WS-подписчик.
    Все события идут в ОБЩУЮ очередь (COMMON).
    """
    try:
        while True:
            try:
                rooms = await manager.list_rooms()  # список warehouse_id с активными подписчиками
                if rooms:
                    async with async_session() as session:
                        for warehouse_id in rooms:
                            await publish_critical_unique_articles_snapshot(session, warehouse_id)
            except Exception as inner_err:
                print(f"❌ continuous_inventory_critical_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # штатная остановка фоновой задачи
        pass
    except Exception as e:
        print(f"🔥 continuous_inventory_critical_streamer fatal error: {e}")
