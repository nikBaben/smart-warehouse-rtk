# app/stream/robot_activity_history_streamer.py
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.db.session import async_session
from app.models.robot import Robot
from app.models.robot_history import RobotHistory


# --- какие статусы считаются активными ---
ACTIVE_STATUSES = ("idle", "scanning")


# === служебные утилиты ===
def _now() -> datetime:
    return datetime.now(timezone.utc)

def _floor(ts: datetime, bucket_sec: int) -> datetime:
    """Округляем время вниз до размера бакета."""
    s = int(ts.timestamp())
    return datetime.fromtimestamp(s - s % bucket_sec, tz=timezone.utc)

def _axis(now: datetime, window_min: int, bucket_sec: int) -> List[datetime]:
    """Формируем ось времени от now - window_min до now."""
    start = now - timedelta(minutes=window_min)
    t = _floor(start, bucket_sec)
    end = _floor(now, bucket_sec)
    out = []
    while t <= end:
        out.append(t)
        t += timedelta(seconds=bucket_sec)
    return out


# === запросы в БД ===
async def _total_robots(session: AsyncSession, wh: str) -> int:
    """Количество роботов на складе (всего)."""
    val = await session.scalar(select(func.count(Robot.id)).where(Robot.warehouse_id == wh))
    return int(val or 0)


async def _active_unique_by_bucket(
    session: AsyncSession, wh: str, start: datetime, end: datetime, bucket_sec: int
) -> Dict[datetime, Set[str]]:
    """
    Для каждого бакета считаем множество уникальных robot_id,
    у которых был статус ACTIVE_STATUSES в это время.
    """
    q = (
        select(RobotHistory.robot_id, RobotHistory.created_at)
        .where(RobotHistory.warehouse_id == wh)
        .where(RobotHistory.created_at >= start)
        .where(RobotHistory.created_at <= end)
        .where(func.lower(RobotHistory.status).in_(ACTIVE_STATUSES))
    )
    rows = (await session.execute(q)).all()

    buckets: Dict[datetime, Set[str]] = defaultdict(set)
    for rid, ts in rows:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        b = _floor(ts, bucket_sec)
        buckets[b].add(rid)
    return buckets


def _series(axis: List[datetime], buckets: Dict[datetime, Set[str]], total: int) -> List[Tuple[str, float]]:
    """Формирует список (timestamp, % активных) для всех бакетов оси."""
    if total <= 0:
        return [(t.isoformat(), 0.0) for t in axis]

    out: List[Tuple[str, float]] = []
    for t in axis:
        pct = len(buckets.get(t, set())) / total * 100.0
        out.append((t.isoformat(), round(pct, 2)))
    return out


# === основная публикация ===
async def publish_robot_activity_series_from_history(
    session: AsyncSession, warehouse_id: str, window_min: int = 60, bucket_sec: int = 60
) -> None:
    """
    Собирает ряд активности роботов за последние `window_min` минут
    с шагом `bucket_sec` секунд и публикует его в очередь WS.
    """
    now = _now()
    axis = _axis(now, window_min, bucket_sec)
    if not axis:
        return

    total = await _total_robots(session, warehouse_id)
    start, end = axis[0], axis[-1]
    buckets = await _active_unique_by_bucket(session, warehouse_id, start, end, bucket_sec)
    series = _series(axis, buckets, total)

    EVENTS.sync_q.put({
        "type": "robot.activity_series",
        "warehouse_id": warehouse_id,
        "window_min": window_min,
        "bucket_sec": bucket_sec,
        "series": series,
        "ts": now.isoformat(),
        "total_robots": total,
    })


# === фоновая задача ===
async def continuous_robot_activity_history_streamer(
    interval: float = 30.0, window_min: int = 60, bucket_sec: int = 600
) -> None:
    """
    Фоновая задача, каждые `interval` секунд публикует
    обновлённые ряды активности для всех складов, на которые есть WS-подписчики.
    """
    try:
        while True:
            rooms = await manager.list_rooms()
            if rooms:
                async with async_session() as session:
                    for wh in rooms:
                        await publish_robot_activity_series_from_history(
                            session, wh, window_min=window_min, bucket_sec=bucket_sec
                        )
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass


# === точечное обновление после записи в RobotHistory ===
async def publish_robot_activity_on_history_event(session: AsyncSession, history_id: str) -> None:
    """
    Вызывается при записи нового события RobotHistory.
    Позволяет мгновенно обновить ряд для склада, где изменился статус робота.
    """
    row = await session.execute(
        select(RobotHistory.warehouse_id).where(RobotHistory.id == history_id)
    )
    wh: Optional[str] = row.scalar_one_or_none()
    if wh:
        await publish_robot_activity_series_from_history(session, wh)
