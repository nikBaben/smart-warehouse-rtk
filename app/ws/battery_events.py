from __future__ import annotations
from typing import Optional
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.models.robot import Robot
from app.db.session import async_session  # такой же паттерн, как у продуктов


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== Публикации событий по средней зарядке роботов =====

# Полный «снимок» средней зарядки по складу — можно слать при подключении клиента И/ИЛИ периодически
async def publish_robot_avg_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    row = await session.execute(
        select(
            func.avg(Robot.battery_level),
            func.count(Robot.id),
        ).where(Robot.warehouse_id == warehouse_id)
    )
    avg, cnt = row.one_or_none() or (None, 0)
    EVENTS.sync_q.put({
        "type": "robot.avg_battery",
        "warehouse_id": warehouse_id,
        "avg_battery": round(float(avg or 0.0), 2),
        "robot_count": int(cnt or 0),
        "ts": _now_iso(),
    })


# Дельта-событие: заряд какого-то робота изменился → пересчитаем среднее по его складу и отправим
async def publish_robot_battery_changed(session: AsyncSession, robot_id: str) -> None:
    wh_row = await session.execute(
        select(Robot.warehouse_id).where(Robot.id == robot_id)
    )
    warehouse_id: Optional[str] = wh_row.scalar_one_or_none()
    if not warehouse_id:
        return
    await publish_robot_avg_snapshot(session, warehouse_id)


# Удаление робота влияет на среднее → пересчитываем и отправляем новое значение
async def publish_robot_deleted(session: AsyncSession, robot_id: str, warehouse_id: str) -> None:
    # robot_id тут не обязателен для пересчёта, но оставлен для симметрии сигнатуры
    await publish_robot_avg_snapshot(session, warehouse_id)


# ===== Периодическая рассылка «снимка» только для подписанных складов =====

# Периодически (каждые `interval` секунд) отправляет событие со средней зарядкой
# для КАЖДОГО склада, на который сейчас есть хотя бы один подписчик (WS-клиент).
# Запускайте это как фон-таск наряду с robot_events_broadcaster().
async def continuous_robot_avg_streamer(interval: float = 2.0) -> None:
    try:
        while True:
            rooms = await manager.list_rooms()  # список warehouse_id с активными подписчиками
            if rooms:
                async with async_session() as session:
                    for warehouse_id in rooms:
                        await publish_robot_avg_snapshot(session, warehouse_id)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
