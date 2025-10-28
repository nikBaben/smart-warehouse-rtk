from __future__ import annotations
from typing import Optional
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.models.robot import Robot
from app.db.session import async_session


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== Публикации событий по средней зарядке роботов =====
async def publish_robot_avg_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    """Отправляет в очередь событие со средней зарядкой роботов по складу."""
    try:
        result = await session.execute(
            select(func.avg(Robot.battery_level)).where(Robot.warehouse_id == warehouse_id)
        )
        avg = result.scalar_one_or_none() or 0.0
        avg = round(float(avg), 2)

        event = {
            "type": "robot.avg_battery",
            "warehouse_id": warehouse_id,
            "avg_battery": avg,
            "ts": _now_iso(),
        }

        EVENTS.sync_q.put(event)
        print(f"⚡ [publish_robot_avg_snapshot] Склад {warehouse_id}: средняя зарядка = {avg}%")
    except Exception as e:
        print(f"❌ Ошибка в publish_robot_avg_snapshot для склада {warehouse_id}: {e}")


async def publish_robot_battery_changed(session: AsyncSession, robot_id: str) -> None:
    """Когда изменился заряд конкретного робота — пересчитать среднее по складу."""
    try:
        wh_row = await session.execute(select(Robot.warehouse_id).where(Robot.id == robot_id))
        warehouse_id: Optional[str] = wh_row.scalar_one_or_none()
        if not warehouse_id:
            print(f"⚠️ [publish_robot_battery_changed] robot_id={robot_id}: склад не найден")
            return

        await publish_robot_avg_snapshot(session, warehouse_id)
    except Exception as e:
        print(f"❌ Ошибка в publish_robot_battery_changed для {robot_id}: {e}")


async def publish_robot_deleted(session: AsyncSession, robot_id: str, warehouse_id: str) -> None:
    """При удалении робота также обновляем среднее значение."""
    try:
        await publish_robot_avg_snapshot(session, warehouse_id)
        print(f"🗑️ [publish_robot_deleted] Робот {robot_id} удалён, пересчитана средняя зарядка.")
    except Exception as e:
        print(f"❌ Ошибка в publish_robot_deleted для {robot_id}: {e}")


# ===== Периодическая рассылка только подписанным клиентам =====
async def continuous_robot_avg_streamer(interval: float = 2.0) -> None:
    """
    Каждые `interval` секунд отправляет среднюю зарядку для всех складов,
    на которые подписаны активные WS-клиенты.
    """
    print("🚀 continuous_robot_avg_streamer запущен.")
    try:
        while True:
            try:
                rooms = await manager.list_rooms()  # Список складов с активными WS-клиентами
                print("📡 [continuous_robot_avg_streamer] Активные склады:", rooms)

                if rooms:
                    async with async_session() as session:
                        for warehouse_id in rooms:
                            await publish_robot_avg_snapshot(session, warehouse_id)
                else:
                    print("ℹ️ Нет активных подписчиков на WebSocket.")

            except Exception as inner_err:
                print(f"❌ Ошибка внутри цикла стримера: {inner_err}")

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        print("🛑 continuous_robot_avg_streamer остановлен (CancelledError).")
    except Exception as e:
        print(f"🔥 Фатальная ошибка в continuous_robot_avg_streamer: {e}")
