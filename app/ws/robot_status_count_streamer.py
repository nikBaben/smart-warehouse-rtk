# app/stream/robot_active_count_streamer.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ публикуем через фабрику шины под ТЕКУЩИЙ event loop
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.db.session import async_session
from app.models.robot import Robot

# менеджер комнат есть только в API-процессе — пробуем подтянуть опционально
try:
    from app.ws.ws_manager import manager  # type: ignore
except Exception:
    manager = None  # type: ignore

# --- какие статусы считаются активными ---
ACTIVE_STATUSES = ("idle", "scanning")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# === публикации ===
async def publish_robot_status_count_snapshot(
    session: AsyncSession,
    warehouse_id: str,
) -> None:
    """
    Публикует событие с количеством роботов на складе со статусами из ACTIVE_STATUSES.
    Также отдаёт общую численность и разбивку по статусам.
    """
    total_all_val = await session.scalar(
        select(func.count(Robot.id)).where(Robot.warehouse_id == warehouse_id)
    )
    total_robots = int(total_all_val or 0)

    stmt = (
        select(
            func.lower(Robot.status).label("status"),
            func.count(Robot.id).label("cnt"),
        )
        .where(Robot.warehouse_id == warehouse_id)
        .where(func.lower(Robot.status).in_(ACTIVE_STATUSES))
        .group_by(func.lower(Robot.status))
    )
    rows = (await session.execute(stmt)).all()
    per_status: Dict[str, int] = {str(status): int(cnt) for status, cnt in rows}
    active_total = sum(per_status.values())

    bus = await get_bus_for_current_loop()
    await bus.publish(COMMON_CH, {
        "type": "robot.active_robots",
        "warehouse_id": warehouse_id,
        "active_robots": active_total,
        "robots": total_robots,
        "per_status": per_status,
        "ts": _now_iso(),
    })


async def publish_robot_status_changed(session: AsyncSession, robot_id: str) -> None:
    """
    Вызывайте после изменения статуса робота — пересчитывает счётчик по складу.
    """
    row = await session.execute(select(Robot.warehouse_id).where(Robot.id == robot_id))
    warehouse_id: Optional[str] = row.scalar_one_or_none()
    if not warehouse_id:
        return
    await publish_robot_status_count_snapshot(session, warehouse_id)


async def publish_robot_deleted(session: AsyncSession, robot_id: str, warehouse_id: str) -> None:
    """
    Если робота удалили — пересчитаем счётчик по складу.
    """
    await publish_robot_status_count_snapshot(session, warehouse_id)


# === выбор активных складов ===
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
    """Список всех складов, где есть хотя бы один робот (worker-режим)."""
    rows = await session.execute(select(distinct(Robot.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]


# === фоновая задача ===
async def continuous_robot_status_count_streamer(
    interval: float = 5.0,
    use_ws_rooms: bool = False,
) -> None:
    """
    Каждые `interval` секунд публикует количество роботов со статусами ACTIVE_STATUSES по складам.

    use_ws_rooms=True  → брать только склады с активными WS-подписчиками (API-процесс).
    use_ws_rooms=False → брать склады из БД (worker-процесс).
    """
    print(f"🚀 continuous_robot_status_count_streamer(interval={interval}, use_ws_rooms={use_ws_rooms})")
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
                            await publish_robot_status_count_snapshot(session, warehouse_id)
                else:
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for warehouse_id in wh_ids:
                            await publish_robot_status_count_snapshot(session, warehouse_id)
            except Exception as inner_err:
                print(f"❌ continuous_robot_status_count_streamer inner error: {inner_err}")

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("🛑 continuous_robot_status_count_streamer cancelled")
    except Exception as e:
        print(f"🔥 continuous_robot_status_count_streamer fatal error: {e}")
