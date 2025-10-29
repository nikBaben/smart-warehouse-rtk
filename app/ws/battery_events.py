# app/ws/battery_events.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ берём фабрику bus, а не синглтон
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.models.robot import Robot
from app.db.session import async_session

# Опционально: менеджер WS (используется ТОЛЬКО если стример крутится в API)
try:
    from app.ws.ws_manager import manager
except Exception:  # в воркере модуля может не быть
    manager = None  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== Публикация события в Redis =====
async def publish_robot_avg_snapshot(session: AsyncSession, warehouse_id: str) -> None:
    """
    Считает средний заряд роботов по складу и публикует событие в Redis (COMMON_CH).
    """
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

        # ✅ получаем bus, привязанный к текущему event loop
        bus = await get_bus_for_current_loop()
        await bus.publish(COMMON_CH, event)
    except Exception as e:
        print(f"❌ Ошибка в publish_robot_avg_snapshot для склада {warehouse_id}: {e}")


async def publish_robot_battery_changed(session: AsyncSession, robot_id: str) -> None:
    """
    Вызвать при изменении заряда конкретного робота — пересчитывает среднее по его складу.
    """
    try:
        wh_row = await session.execute(select(Robot.warehouse_id).where(Robot.id == robot_id))
        warehouse_id: Optional[str] = wh_row.scalar_one_or_none()
        if not warehouse_id:
            return
        await publish_robot_avg_snapshot(session, warehouse_id)
    except Exception as e:
        print(f"❌ Ошибка в publish_robot_battery_changed для {robot_id}: {e}")


async def publish_robot_deleted(session: AsyncSession, robot_id: str, warehouse_id: str) -> None:
    """
    При удалении робота также обновляем среднее значение по складу.
    """
    try:
        await publish_robot_avg_snapshot(session, warehouse_id)
    except Exception as e:
        print(f"❌ Ошибка в publish_robot_deleted для {robot_id}: {e}")


# ===== Вспомогательное: выбор активных складов =====

async def _get_active_warehouses_by_ws() -> List[str]:
    """
    Список складов, на которые есть WS-подписчики (только если этот код крутится в API).
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
    Список складов, где есть хотя бы один робот (подходит для воркера).
    """
    rows = await session.execute(select(distinct(Robot.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]


# ===== Периодический стример =====
async def continuous_robot_avg_streamer(interval: float = 60.0, use_ws_rooms: bool = False) -> None:
    """
    Каждые `interval` секунд публикует средний заряд по складам.

    Режимы:
      - use_ws_rooms=True  → берём только склады с активными WS-подписчиками (логично для API-процесса).
      - use_ws_rooms=False → берём активные склады из БД (логично для worker-процесса).

    Все события публикуются в Redis канал COMMON_CH.
    """
    print(f"🚀 continuous_robot_avg_streamer запущен (interval={interval}s, use_ws_rooms={use_ws_rooms}).")
    try:
        while True:
            try:
                if use_ws_rooms:
                    # API-режим: только подписанные склады
                    wh_ids = await _get_active_warehouses_by_ws()
                    if not wh_ids:
                        await asyncio.sleep(interval)
                        continue
                    async with async_session() as session:
                        for wid in wh_ids:
                            await publish_robot_avg_snapshot(session, wid)
                else:
                    # Worker-режим: активные склады по БД
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for wid in wh_ids:
                            await publish_robot_avg_snapshot(session, wid)

            except Exception as inner_err:
                print(f"❌ Ошибка внутри цикла стримера: {inner_err}")

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        print("🛑 continuous_robot_avg_streamer остановлен (CancelledError).")
    except Exception as e:
        print(f"🔥 Фатальная ошибка в continuous_robot_avg_streamer: {e}")
