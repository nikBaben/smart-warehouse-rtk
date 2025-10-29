from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ публикуем через фабрику шины под ТЕКУЩИЙ event loop
from app.events.bus import get_bus_for_current_loop, COMMON_CH
from app.db.session import async_session
from app.models.robot import Robot
from app.models.robot_history import RobotHistory

# менеджер комнат есть только в API-процессе — пробуем подтянуть опционально
try:
    from app.ws.ws_manager import manager  # type: ignore
except Exception:
    manager = None  # type: ignore

# --- какие статусы считаются активными ---
ACTIVE_STATUSES = ("idle", "scanning")

# --- параметры вывода ---
POINTS_COUNT = 7  # ровно 7 точек
BUCKET_SEC = 600  # 10 минут
WINDOW_MIN = POINTS_COUNT * (BUCKET_SEC // 60)  # 70 минут

# --- внутреннее состояние ---
_last_bucket_sent: Dict[str, datetime] = {}  # warehouse_id -> last emitted bucket_end (UTC)
_next_allowed_emit: Dict[str, datetime] = {}  # warehouse_id -> next allowed publish (UTC)

# === служебные утилиты ===
def _ensure_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

def _floor(ts: datetime, bucket_sec: int) -> datetime:
    ts = _ensure_utc(ts)
    s = int(ts.timestamp())
    return datetime.fromtimestamp(s - s % bucket_sec, tz=timezone.utc)

def _axis_from_last(now_like: datetime, buckets: int, bucket_sec: int) -> List[datetime]:
    """Формируем ось времени из 'buckets' точек, заканчивающуюся бакетом, содержащим now_like."""
    end = _floor(now_like, bucket_sec)
    start = end - timedelta(seconds=bucket_sec * (buckets - 1))
    t = start
    out: List[datetime] = []
    while t <= end:
        out.append(t)
        t += timedelta(seconds=bucket_sec)
    return out[-buckets:]

def _bucket_end_of(ts: datetime, bucket_sec: int) -> datetime:
    return _floor(ts, bucket_sec)

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
    """Последний статус каждого робота ДО начала окна (strictly < before_ts)."""
    subq = (
        select(
            RobotHistory.robot_id.label("rid"),
            func.max(RobotHistory.created_at).label("mx"),
        )
        .where(and_(RobotHistory.warehouse_id == wh, RobotHistory.created_at < before_ts))
        .group_by(RobotHistory.robot_id)
        .subquery()
    )
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
    session: AsyncSession,
    wh: str,
    start_inclusive: datetime,
    end_inclusive: datetime
) -> List[Tuple[str, str, datetime]]:
    """Возвращает (robot_id, status, created_at) внутри окна [start, end], по времени."""
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
    """На конец каждого бакета считаем % активных (ACTIVE_STATUSES)."""
    state: Dict[str, str] = dict(baseline)
    idx = 0
    n = len(events)
    out: List[Tuple[str, float]] = []

    if total_robots <= 0:
        return [(t.isoformat(), 0.0) for t in axis]

    for bucket_end in axis:
        while idx < n and events[idx][2] <= bucket_end:
            rid, status, _ts = events[idx]
            state[rid] = status
            idx += 1
        active = sum(1 for s in state.values() if s in ACTIVE_STATUSES)
        pct = round((active / total_robots) * 100.0, 2)
        out.append((bucket_end.isoformat(), pct))
    return out

# === публикации ===
async def publish_robot_activity_series_from_history(
    session: AsyncSession,
    warehouse_id: str,
    *,
    force: bool = False,
) -> None:
    """
    Публикуем 7 точек по 10 минут, считая активность на конец текущего бакета.
    Правило: не чаще 1 раза в 10 минут от последней публикации (но можно force=True).
    """
    bus = await get_bus_for_current_loop()
    now_srv = datetime.now(timezone.utc)

    # проверяем throttle по времени
    next_allowed = _next_allowed_emit.get(warehouse_id)
    if not force and next_allowed is not None and now_srv < next_allowed:
        return

    bucket_end = _bucket_end_of(now_srv, BUCKET_SEC)
    if not force and _last_bucket_sent.get(warehouse_id) == bucket_end:
        return

    axis = _axis_from_last(now_srv, POINTS_COUNT, BUCKET_SEC)
    start, end = axis[0], axis[-1]

    last_ts = await _latest_history_timestamp(session, warehouse_id)
    if last_ts is None:
        series = [(t.isoformat(), 0.0) for t in axis]
        await bus.publish(COMMON_CH, {
            "type": "robot.activity_series",
            "warehouse_id": warehouse_id,
            "window_min": WINDOW_MIN,
            "bucket_sec": BUCKET_SEC,
            "series": series,
            "ts": end.isoformat(),
            "total_robots": 0,
        })
        _last_bucket_sent[warehouse_id] = bucket_end
        _next_allowed_emit[warehouse_id] = now_srv + timedelta(seconds=BUCKET_SEC)
        return

    total = await _total_robots(session, warehouse_id)
    baseline = await _baseline_statuses_before(session, warehouse_id, start)
    events = await _events_in_window(session, warehouse_id, start, end)
    series = _carry_forward_active_counts(axis, baseline, events, total)

    await bus.publish(COMMON_CH, {
        "type": "robot.activity_series",
        "warehouse_id": warehouse_id,
        "window_min": WINDOW_MIN,
        "bucket_sec": BUCKET_SEC,
        "series": series,
        "ts": end.isoformat(),
        "total_robots": total,
    })
    _last_bucket_sent[warehouse_id] = bucket_end
    _next_allowed_emit[warehouse_id] = now_srv + timedelta(seconds=BUCKET_SEC)

# === выбор активных складов ===
async def _get_active_warehouses_by_ws() -> List[str]:
    if manager is None:
        return []
    try:
        rooms = await manager.list_rooms()
        return rooms or []
    except Exception:
        return []

async def _get_active_warehouses_by_db(session: AsyncSession) -> List[str]:
    rows = await session.execute(select(distinct(RobotHistory.warehouse_id)))
    return [wid for (wid,) in rows.all() if wid]

# === вспомогательная задержка ===
async def _sleep_until_next_bucket() -> None:
    now = datetime.now(timezone.utc)
    next_edge = _floor(now, BUCKET_SEC) + timedelta(seconds=BUCKET_SEC)
    await asyncio.sleep((next_edge - now).total_seconds())

# === фоновая задача ===
async def continuous_robot_activity_history_streamer(
    interval: float = 600,
    use_ws_rooms: bool = False,
) -> None:
    """Каждые interval секунд публикует 7 последних 10-минутных точек активности."""
    print(f"🚀 continuous_robot_activity_history_streamer(interval={interval}, use_ws_rooms={use_ws_rooms})")
    try:
        await _sleep_until_next_bucket()
        while True:
            try:
                if use_ws_rooms:
                    wh_ids = await _get_active_warehouses_by_ws()
                    if not wh_ids:
                        await _sleep_until_next_bucket()
                        continue
                    async with async_session() as session:
                        for wh in wh_ids:
                            await publish_robot_activity_series_from_history(session, wh)
                else:
                    async with async_session() as session:
                        wh_ids = await _get_active_warehouses_by_db(session)
                        for wh in wh_ids:
                            await publish_robot_activity_series_from_history(session, wh)
            except Exception as inner_err:
                print(f"❌ continuous_robot_activity_history_streamer inner error: {inner_err}")
            await _sleep_until_next_bucket()
    except asyncio.CancelledError:
        print("🛑 continuous_robot_activity_history_streamer cancelled")
    except Exception as e:
        print(f"🔥 continuous_robot_activity_history_streamer fatal error: {e}")

# === точечное обновление после записи в RobotHistory ===
async def publish_robot_activity_on_history_event(session: AsyncSession, history_id: str) -> None:
    row = await session.execute(
        select(RobotHistory.warehouse_id).where(RobotHistory.id == history_id)
    )
    wh: Optional[str] = row.scalar_one_or_none()
    if wh:
        await publish_robot_activity_series_from_history(session, wh, force=True)
