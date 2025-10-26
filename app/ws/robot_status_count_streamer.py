from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.db.session import async_session
from app.models.robot import Robot


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Публикации событий ----------

async def publish_robot_status_count_snapshot(
    session: AsyncSession,
    warehouse_id: str,
) -> None:
    """
    Публикует событие с количеством роботов на складе со статусом idle или scan.
    Также отдаёт разбивку по каждому статусу (на всякий случай).
    """
    statuses = ["idle", "scan"]

    # сгруппированный подсчёт по каждому статусу
    stmt = (
        select(
            func.lower(Robot.status).label("status"),
            func.count(Robot.id).label("cnt"),
        )
        .where(Robot.warehouse_id == warehouse_id)
        .where(func.lower(Robot.status).in_(statuses))
        .group_by(func.lower(Robot.status))
    )
    rows = (await session.execute(stmt)).all()
    per_status: Dict[str, int] = {status: int(cnt) for status, cnt in rows}
    total = sum(per_status.values())

    EVENTS.sync_q.put({
        "type": "robot.status_count",
        "warehouse_id": warehouse_id,
        "statuses": statuses,         # ['idle','scan']
        "total": total,               # суммарно idle+scan
        "per_status": per_status,     # например {'idle': 3, 'scan': 2}
        "ts": _now_iso(),
    })


async def publish_robot_status_changed(session: AsyncSession, robot_id: str) -> None:
    """
    Вызывайте после изменения статуса робота.
    Находим его склад и публикуем новый снэпшот.
    """
    row = await session.execute(
        select(Robot.warehouse_id).where(Robot.id == robot_id)
    )
    warehouse_id: Optional[str] = row.scalar_one_or_none()
    if not warehouse_id:
        return
    await publish_robot_status_count_snapshot(session, warehouse_id)


async def publish_robot_deleted(session: AsyncSession, robot_id: str, warehouse_id: str) -> None:
    """
    Если робота удалили — пересчитаем счётчик по складу.
    """
    await publish_robot_status_count_snapshot(session, warehouse_id)


# ---------- Периодический стример (только при активных подписках) ----------

async def continuous_robot_status_count_streamer(interval: float = 5.0) -> None:
    """
    Каждые `interval` секунд публикует количество роботов со статусами
    idle/scan для каждого склада, на который есть хотя бы один WS-подписчик.
    """
    try:
        while True:
            rooms = await manager.list_rooms()  # список warehouse_id с подписчиками
            if rooms:
                async with async_session() as session:
                    for warehouse_id in rooms:
                        await publish_robot_status_count_snapshot(session, warehouse_id)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass
