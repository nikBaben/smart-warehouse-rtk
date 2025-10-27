# app/stream/robot_activity_history_streamer.py
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.ws_manager import EVENTS, manager
from app.db.session import async_session
from app.models.robot import Robot
from app.models.robot_history import RobotHistory

# --- какие статусы считаются активными ---
ACTIVE_STATUSES = ("idle", "scanning")

# --- параметры вывода ---
POINTS_COUNT = 7                 # ровно 7 точек
BUCKET_SEC = 600                 # 10 минут
WINDOW_MIN = POINTS_COUNT * (BUCKET_SEC // 60)  # 70 минут

# === служебные утилиты ===
def _ensure_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

def _floor(ts: datetime, bucket_sec: int) -> datetime:
    ts = _ensure_utc(ts)
    s = int(ts.timestamp())
    return datetime.fromtimestamp(s - s % bucket_sec, tz=timezone.utc)

def _axis_from_last(now_like: datetime, buckets: int, bucket_sec: int) -> List[datetime]:
    """
    Формируем ось времени из 'buckets' точек, заканчивающуюся бакетом, содержащим now_like.
    """
    end = _floor(now_like, bucket_sec)
    start = end - timedelta(seconds=bucket_sec * (buckets - 1))
    t = start
    out: List[datetime] = []
    while t <= end:
        out.append(t)
        t += timedelta(seconds=bucket_sec)
    return out[-buckets:]

# === запросы в БД ===
async def _total_robots(session: AsyncSession, wh: str) -> int:
    val = await session.scalar(select(func.count(Robot.id)).where(Robot.warehouse_id == wh))
    return int(val or 0)

async def _latest_history_timestamp(session: AsyncSession, wh: str) -> Optional[datetime]:
    ts = await session.scalar(
        select(func.max(RobotHistory.created_at)).where(RobotHistory.warehouse_id == wh)
    )
    return _ensure_utc(ts) if ts else None

async def _baseline_statuses_before(
    session: AsyncSession, wh: str, before_ts: datetime
) -> Dict[str, str]:
    """
    Находим ПОСЛЕДНИЙ статус каждого робота на складе ДО начала окна (strictly < before_ts).
    Нужен для корректного переноса состояния в первый бакет.
    """
    # субзапрос: (robot_id, max(created_at)) для событий до before_ts
    subq = (
        select(
            RobotHistory.robot_id.label("rid"),
            func.max(RobotHistory.created_at).label("mx"),
        )
        .where(
            and_(
                RobotHistory.warehouse_id == wh,
                RobotHistory.created_at < before_ts,
            )
        )
        .group_by(RobotHistory.robot_id)
        .subquery()
    )

    # вытаскиваем статус на найденных mx
    q = (
        select(RobotHistory.robot_id, RobotHistory.status)
        .join(subq, and_(
            RobotHistory.robot_id == subq.c.rid,
            RobotHistory.created_at == subq.c.mx
        ))
    )
    rows = await session.execute(q)
    out: Dict[str, str] = {}
    for rid, status in rows.all():
        out[str(rid)] = str(status).lower() if status else ""
    return out

async def _events_in_window(
    session: AsyncSession, wh: str, start_inclusive: datetime, end_inclusive: datetime
) -> List[Tuple[str, str, datetime]]:
    """
    Возвращает список событий (robot_id, status, created_at) внутри окна [start, end], упорядоченный по времени.
    """
    q = (
        select(RobotHistory.robot_id, RobotHistory.status, RobotHistory.created_at)
        .where(RobotHistory.warehouse_id == wh)
        .where(RobotHistory.created_at >= start_inclusive)
        .where(RobotHistory.created_at <= end_inclusive)
        .order_by(RobotHistory.created_at.asc())
    )
    rows = await session.execute(q)
    out: List[Tuple[str, str, datetime]] = []
    for rid, status, ts in rows.all():
        out.append((str(rid), (status or "").lower(), _ensure_utc(ts)))
    return out

def _carry_forward_active_counts(
    axis: List[datetime],
    baseline: Dict[str, str],
    events: List[Tuple[str, str, datetime]],
    total_robots: int,
) -> List[Tuple[str, float]]:
    """
    Строим значения для каждого бакета:
    - берём baseline (последний статус < начала окна),
    - применяем события по времени, обновляя текущий статус робота,
    - для конца каждого бакета смотрим, сколько роботов в ACTIVE_STATUSES.
    """
    # Текущие статусы роботов к "течению времени"
    state: Dict[str, str] = dict(baseline)

    # Индекс событий, будем «прокручивать» их по оси
    idx = 0
    n = len(events)

    out: List[Tuple[str, float]] = []
    if total_robots <= 0:
        # 0 роботов — просто нули
        return [(t.isoformat(), 0.0) for t in axis]

    # Для каждого бакета применяем все события с ts <= конца бакета
    for bucket_end in axis:
        while idx < n and events[idx][2] <= bucket_end:
            rid, status, _ts = events[idx]
            state[rid] = status
            idx += 1

        # считаем активных по текущему состоянию
        active = sum(1 for s in state.values() if s in ACTIVE_STATUSES)
        pct = round((active / total_robots) * 100.0, 2)
        out.append((bucket_end.isoformat(), pct))

    return out

# === основная публикация ===
async def publish_robot_activity_series_from_history(
    session: AsyncSession, warehouse_id: str
) -> None:
    """
    Публикуем РОВНО 7 точек по 10 минут, считая активность как состояние на конец каждого бакета.
    Ось времени привязывается к последнему событию из RobotHistory для склада.
    При отсутствии истории — 7 нулей, выровненных по серверному времени.
    """
    last_ts = await _latest_history_timestamp(session, warehouse_id)

    if last_ts is None:
        # нет истории — отдаём 7 нулей
        now_srv = datetime.now(timezone.utc)
        axis = _axis_from_last(now_srv, POINTS_COUNT, BUCKET_SEC)
        series = [(t.isoformat(), 0.0) for t in axis]
        EVENTS.sync_q.put({
            "type": "robot.activity_series",
            "warehouse_id": warehouse_id,
            "window_min": WINDOW_MIN,
            "bucket_sec": BUCKET_SEC,
            "series": series,
            "ts": now_srv.isoformat(),
            "total_robots": 0,
        })
        return

    # строим ось из 7 бакетов, заканчивающихся на бакете last_ts
    axis = _axis_from_last(last_ts, POINTS_COUNT, BUCKET_SEC)
    start, end = axis[0], axis[-1]

    total = await _total_robots(session, warehouse_id)

    # baseline до начала окна + события внутри окна
    baseline = await _baseline_statuses_before(session, warehouse_id, start)
    events = await _events_in_window(session, warehouse_id, start, end)

    # переносим состояния вперёд и считаем % активных
    series = _carry_forward_active_counts(axis, baseline, events, total)

    EVENTS.sync_q.put({
        "type": "robot.activity_series",
        "warehouse_id": warehouse_id,
        "window_min": WINDOW_MIN,
        "bucket_sec": BUCKET_SEC,
        "series": series,                 # длина = 7
        "ts": last_ts.isoformat(),        # «текущее» время — последняя запись в истории
        "total_robots": total,
    })

# === фоновая задача ===
async def continuous_robot_activity_history_streamer(interval: float = 600) -> None:
    """
    Каждые interval секунд публикует 7 последних 10-минутных точек активности
    для всех складов, на которые есть WS-подписчики.
    """
    try:
        while True:
            rooms = await manager.list_rooms()
            if rooms:
                async with async_session() as session:
                    for wh in rooms:
                        await publish_robot_activity_series_from_history(session, wh)
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
