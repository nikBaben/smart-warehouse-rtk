# app/robot_watcher.py
from __future__ import annotations

import asyncio
import random
import uuid
import threading
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Set, Callable, Awaitable

# POSIX file-lock для синглтона
try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None  # на Windows просто не используем файловый лок

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from app.models.product import Product
from app.models.inventory_history import InventoryHistory
from app.service.robot_history import write_robot_status_event  # лог статусов

# Шина событий (Redis) — фабрики bus на текущем loop
from app.events.bus import (
    get_bus_for_current_loop,
    close_bus_for_current_loop,
    ROBOT_CH,
    COMMON_CH,
)

# =========================
# Управление форматом событий позиции
# =========================
EMIT_POSITION_PER_ROBOT = False  # одиночные события для каждого робота (выключено)
EMIT_POSITION_BATCH = True       # один батч на склад за тик (включено)

# =========================
# Параметры поля / зарядки / сканирования
# =========================
DOCK_X, DOCK_Y = 0, 0
SCAN_DURATION = timedelta(seconds=10)
CHARGE_DURATION = timedelta(seconds=45)
MIN_BATT_DROP_PER_STEP = 0.2
RESCAN_COOLDOWN = timedelta(seconds=30)   # 15 секунд
# Предохранитель от залипания скана
SCAN_STUCK_FACTOR = 3  # не более 3 * SCAN_DURATION

# =========================
# Конфигурация логирования истории робота
# =========================
LOG_EVERY_TICK = False
TICK_LOG_MIN_INTERVAL = timedelta(seconds=15)

# =========================
# Память процесса + блокировки
# =========================
_TARGETS: Dict[str, Tuple[int, int]] = {}
_CLAIMED_TARGETS: Dict[str, Set[Tuple[int, int]]] = {}
_SCANNING_UNTIL: Dict[str, datetime] = {}
_SCANNING_TARGET: Dict[str, Tuple[int, int]] = {}
_CHARGE_ACCUM: Dict[str, float] = {}
_LAST_EMITTED_STATE: Dict[str, Tuple[int, int, str, int]] = {}
_LAST_LOGGED_STATE: Dict[str, Tuple[int, int, str, int]] = {}
_LAST_HISTORY_AT: Dict[str, datetime] = {}

_LOCK_TARGETS = threading.RLock()
_LOCK_SCAN = threading.RLock()

# Кэш последних сканов по складу: product_id -> max(created_at) (TTL)
_LAST_SCAN_CACHE: Dict[str, Tuple[datetime, Dict[str, datetime]]] = {}
LAST_SCAN_TTL = timedelta(seconds=30)

# Ограничитель конкурентных роботов на склад
_MAX_CONCURRENT_ROBOTS_PER_WAREHOUSE = 8

# =========================
# Антизасор: ретеншн и клининг
# =========================
EVENT_QUEUE_MAXSIZE = 10000
# Отключаем чистку истории инвентаризации: None = никогда не удалять
INVENTORY_HISTORY_RETENTION: Optional[timedelta] = None
INVENTORY_HISTORY_CLEAN_CHUNK = 1000
WAREHOUSE_JANITOR_EVERY = timedelta(minutes=5)

# =========================
# Типы «роботных» событий + rate-limit позиций
# =========================
ROBOT_EVENT_TYPES = {"robot.position", "product.scan"}
POSITION_RATE_LIMIT = timedelta(seconds=2)
_LAST_POSITION_SENT_AT: Dict[str, datetime] = {}

# Разрешаем служебные пустые product.scan только для диагностики
# (no_valid_shelf и under_cooldown). reason="no_products_at_cell" НЕ отправляем.
EMIT_EMPTY_SCAN_EVENTS = True

# =========================
# Синглтон-гарды для вотчера
# =========================
_WATCHER_RUNNING = False
_LOCK_FILE_HANDLE = None  # type: ignore
DEFAULT_WATCHER_LOCK_PATH = os.environ.get("ROBOT_WATCHER_LOCK", "/tmp/robot_watcher.lock")

# расписание уборки per warehouse
_WAREHOUSE_NEXT_JANITOR_AT: Dict[str, datetime] = {}

# =========================
# Параллелизм (НОВОЕ)
# =========================
ENABLE_ROBOT_THREADS = True  # >>> ADDED: поток + loop на каждого робота

# =========================
# Утилиты координат/полок
# =========================

def shelf_str_to_num(s: Optional[str]) -> int:
    """
    Преобразует строковую полку в номер.
    None/""/"0" -> 0 (нет валидной полки)
    """
    if s is None:
        return 0
    s = s.strip()
    if not s or s == "0":
        return 0
    c = s.upper()[:1]
    return (ord(c) - ord("A")) + 1 if "A" <= c <= "Z" else 0


def shelf_num_to_str(n: int) -> str:
    if n <= 0:
        return "0"
    n = min(26, int(n))
    return chr(ord("A") + (n - 1))


def _bounded(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _next_step_towards(start: Tuple[int, int], goal: Tuple[int, int]) -> Tuple[int, int]:
    if start == goal:
        return start
    sx, sy = start
    gx, gy = goal
    dx, dy = gx - sx, gy - sy
    choices: List[Tuple[int, int]] = []
    if dx != 0:
        choices.append((sx + (1 if dx > 0 else -1), sy))
    if dy != 0:
        choices.append((sx, sy + (1 if dy > 0 else -1)))
    return random.choice(choices) if choices else start


def _neighbors(start: Tuple[int, int], max_x: int, max_y: int) -> List[Tuple[int, int]]:
    sx, sy = start
    cand = [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
    return [(x, y) for x, y in cand if 0 <= x <= max_x and 1 <= y <= max_y]


def _random_wander_target(start: Tuple[int, int], max_x: int, max_y: int) -> Tuple[int, int]:
    opts = [p for p in _neighbors(start, max_x, max_y) if p != start]
    return random.choice(opts) if opts else start


def _to_aware_utc(ts: Optional[datetime]) -> Optional[datetime]:
    """
    Делает datetime «aware UTC».
    Если ts naive — считаем, что это UTC, и проставляем tzinfo=UTC.
    """
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)

# =========================
# Сессии БД
# =========================

def _session_factory_main() -> async_sessionmaker[AsyncSession]:
    from app.db.session import async_session as app_sessionmaker
    return app_sessionmaker


def _resolve_db_url() -> str:
    try:
        main_maker = _session_factory_main()
        eng = getattr(main_maker, "bind", None)
        if eng is None:
            eng = getattr(main_maker, "kw", {}).get("bind")
        if eng is not None:
            try:
                return eng.url.render_as_string(hide_password=False)
            except Exception:
                return str(eng.url)
    except Exception:
        pass
    for key in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "DB_DSN"):
        v = os.getenv(key)
        if v:
            return v
    for attr in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "DB_DSN"):
        if hasattr(settings, attr):
            return getattr(settings, attr)  # type: ignore
    raise RuntimeError("Не удалось определить URL базы данных.")


def _session_factory_for_current_loop() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    db_url = _resolve_db_url()
    try:
        # >>> CHANGED: настраиваемый пул для множества потоков
        pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        engine = create_async_engine(
            db_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        print(
            f"🔗 WarehouseRunner engine created for DB: {db_url} "
            f"(pool_size={pool_size}, max_overflow={max_overflow})",
            flush=True
        )
    except Exception as e:
        print(f"🔥 Failed to create AsyncEngine for DB URL={db_url}: {e}", flush=True)
        raise
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return maker, engine

# =========================
# Логирование статуса — оптимизированное
# =========================
async def _log_status_every_tick(session: AsyncSession, robot: Robot) -> None:
    if LOG_EVERY_TICK:
        with session.no_autoflush:
            await write_robot_status_event(session, robot.id)
        return

    now = datetime.now(timezone.utc)
    batt_int = int(round(float(robot.battery_level or 0.0)))
    key = (int(robot.current_row or 0), int(robot.current_shelf or 0), (robot.status or "idle"), batt_int)
    last_key = _LAST_LOGGED_STATE.get(robot.id)
    last_ts = _LAST_HISTORY_AT.get(robot.id, datetime.fromtimestamp(0, tz=timezone.utc))

    if (key == last_key) and (now - last_ts < TICK_LOG_MIN_INTERVAL):
        return

    with session.no_autoflush:
        await write_robot_status_event(session, robot.id)

    _LAST_LOGGED_STATE[robot.id] = key
    _LAST_HISTORY_AT[robot.id] = now


def _touch_robot(robot: Robot) -> None:
    robot.last_update = datetime.now(timezone.utc)

# =========================
# Работа с товарами / сканирование
# =========================

async def _last_scans_map(session: AsyncSession, warehouse_id: str) -> Dict[str, datetime]:
    """
    Кэш: product_id -> последний created_at (UTC-aware).
    """
    now = datetime.now(timezone.utc)
    cached = _LAST_SCAN_CACHE.get(warehouse_id)
    if cached and (now - cached[0]) < LAST_SCAN_TTL:
        return cached[1]

    q = (
        select(InventoryHistory.product_id, func.max(InventoryHistory.created_at))
        .where(InventoryHistory.warehouse_id == warehouse_id)
        .group_by(InventoryHistory.product_id)
    )
    rows = await session.execute(q)
    raw = rows.all()

    mp: Dict[str, datetime] = {}
    for pid, ts in raw:
        ts_aware = _to_aware_utc(ts)
        if ts_aware is not None:
            mp[pid] = ts_aware

    _LAST_SCAN_CACHE[warehouse_id] = (now, mp)
    return mp


async def _eligible_products_for_scan(
    session: AsyncSession,
    warehouse_id: str,
    x: int,
    y: int,
    cutoff: datetime,
) -> List[Product]:
    """
    Товары на клетке (x,y), которые можно сканировать сейчас (учтён RESCAN_COOLDOWN).
    """
    shelf_letter = shelf_num_to_str(y)
    if shelf_letter == "0":
        return []

    q = (
        select(Product)
        .where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            func.upper(func.trim(Product.current_shelf)) == shelf_letter,
        )
    )
    rows = await session.execute(q)
    products: List[Product] = list(rows.scalars().all())
    if not products:
        return []

    last_map = await _last_scans_map(session, warehouse_id)
    return [p for p in products if (last_map.get(p.id) is None) or (last_map[p.id] < cutoff)]


async def _eligible_scan_cells(session: AsyncSession, warehouse_id: str, cutoff: datetime) -> List[Tuple[int, int]]:
    """
    Список клеток (x,y), где есть ХОТЬ ОДИН товар, допустимый к сканированию (не под cooldown).
    """
    q = (
        select(Product.id, Product.current_row, func.upper(func.trim(Product.current_shelf)).label("shelf"))
        .where(Product.warehouse_id == warehouse_id)
    )
    rows = await session.execute(q)
    by_cell: Dict[Tuple[int, int], List[str]] = {}
    for pid, row_x, shelf_norm in rows.all():
        y = shelf_str_to_num(shelf_norm)
        if y <= 0:
            continue
        cell = (int(row_x or 0), y)
        by_cell.setdefault(cell, []).append(pid)

    if not by_cell:
        return []

    last_map = await _last_scans_map(session, warehouse_id)
    cells: List[Tuple[int, int]] = []
    for cell, pids in by_cell.items():
        for pid in pids:
            ts = last_map.get(pid)
            if ts is None or ts < cutoff:
                cells.append(cell)
                break  # в эту клетку уже есть смысл идти
    return cells


async def _begin_scan(session: AsyncSession, robot: Robot, x: int, y: int) -> None:
    robot.status = "scanning"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)
    with _LOCK_SCAN:
        _SCANNING_TARGET[robot.id] = (x, y)
        _SCANNING_UNTIL[robot.id] = datetime.now(timezone.utc) + SCAN_DURATION

    # отладочный лог
    print(f"🔍 begin_scan: wh={robot.warehouse_id} robot={robot.id} at ({x},{y})", flush=True)


async def _finish_scan(session: AsyncSession, robot: Robot) -> None:
    with _LOCK_SCAN:
        rx, ry = _SCANNING_TARGET.pop(robot.id, (int(robot.current_row or 0), int(robot.current_shelf or 0)))
        _SCANNING_UNTIL.pop(robot.id, None)

    print(f"✅ finish_scan: wh={robot.warehouse_id} robot={robot.id} at ({rx},{ry})", flush=True)

    shelf_letter = shelf_num_to_str(ry)
    # Если полка нулевая — отправим пустой продуктовый эвент (для наблюдаемости)
    if shelf_letter == "0":
        if EMIT_EMPTY_SCAN_EVENTS:
            await _emit({
                "type": "product.scan",
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": rx,
                "y": ry,
                "shelf": shelf_letter,
                "products": [],
                "reason": "no_valid_shelf",
            })
        _free_claim(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)
        return

    result = await session.execute(
        select(Product).where(
            Product.warehouse_id == robot.warehouse_id,
            Product.current_row == rx,
            func.upper(func.trim(Product.current_shelf)) == shelf_letter,
        )
    )
    products = list(result.scalars().all())

    # Применяем cooldown к payload; событие отправляем ТОЛЬКО если именно cooldown
    under_cooldown = False
    if products:
        cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
        last_map = await _last_scans_map(session, robot.warehouse_id)
        fresh: List[Product] = []
        for p in products:
            ts = last_map.get(p.id)
            if (ts is None) or (ts < cutoff):
                fresh.append(p)
        under_cooldown = (len(fresh) == 0)
        products = fresh

    if not products:
        if under_cooldown and EMIT_EMPTY_SCAN_EVENTS:
            await _emit({
                "type": "product.scan",
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": rx,
                "y": ry,
                "shelf": shelf_letter,
                "products": [],
                "reason": "under_cooldown",
            })
        _free_claim(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)
        return

    payload_products: List[dict] = []
    history_rows: List[InventoryHistory] = []
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    for p in products:
        stock = int(p.stock or 0)
        status = "ok"
        if p.min_stock is not None and stock < p.min_stock:
            status = "critical"
        elif p.optimal_stock is not None and stock < p.optimal_stock:
            status = "low"

        history_rows.append(
            InventoryHistory(
                id=f"ih_{uuid.uuid4().hex[:10]}",
                product_id=p.id,
                robot_id=robot.id,
                warehouse_id=robot.warehouse_id,
                current_zone=getattr(p, "current_zone", "Хранение"),
                current_row=rx,
                current_shelf=shelf_letter,
                name=p.name,
                category=p.category,
                article=getattr(p, "article", None) or "unknown",
                stock=stock,
                min_stock=p.min_stock,
                optimal_stock=p.optimal_stock,
                status=status,
            )
        )
        payload_products.append({
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "article": getattr(p, "article", None),
            "current_row": rx,
            "current_shelf": shelf_letter,
            "shelf_num": ry,
            "stock": stock,
            "status": status,
            "scanned_at": now_iso,
        })

    with session.no_autoflush:
        session.add_all(history_rows)
    await session.flush()

    await _emit({
        "type": "product.scan",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": rx,
        "y": ry,
        "shelf": shelf_letter,
        "products": payload_products,
    })

    cached = _LAST_SCAN_CACHE.get(robot.warehouse_id)
    if cached:
        mp = dict(cached[1])
        for p in products:
            mp[p.id] = now_dt
        _LAST_SCAN_CACHE[robot.warehouse_id] = (now_dt, mp)

    _free_claim(robot.warehouse_id, (rx, ry))

    robot.status = "idle"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)

# =========================
# Энергия
# =========================

def _drop_per_step_for_field(max_x: int, max_y: int) -> float:
    steps_for_pass = max(1, max_x + max_y)
    drop = 100.0 / (steps_for_pass * 2.0)
    return max(MIN_BATT_DROP_PER_STEP, drop)


def _consume_battery(robot: Robot, drop_per_step: float) -> None:
    lvl = float(robot.battery_level or 0.0)
    robot.battery_level = max(0.0, lvl - drop_per_step)

# =========================
# Цели (без конфликтов) + потокобезопасность
# =========================

def _claimed_set(warehouse_id: str) -> Set[Tuple[int, int]]:
    return _CLAIMED_TARGETS.setdefault(warehouse_id, set())


def _free_claim(warehouse_id: str, target: Tuple[int, int]) -> None:
    with _LOCK_TARGETS:
        _claimed_set(warehouse_id).discard(target)


def _claim(warehouse_id: str, target: Tuple[int, int]) -> None:
    with _LOCK_TARGETS:
        _claimed_set(warehouse_id).add(target)


def _is_claimed(warehouse_id: str, target: Tuple[int, int]) -> bool:
    with _LOCK_TARGETS:
        return target in _CLAIMED_TARGETS.get(warehouse_id, set())


def _pick_goal(
    warehouse_id: str,
    start: Tuple[int, int],
    candidates: List[Tuple[int, int]],
    max_x: int,
    max_y: int,
) -> Tuple[int, int]:
    """
    Выбор следующей цели среди кандидатов:
      - исключаем текущую клетку и вне поля;
      - предпочитаем ближайшие свободные (не заклейменные) клетки;
      - если все кандидаты заняты/недоступны — БРОДИМ (случайный сосед).
    """
    valid_candidates = [
        (cx, cy)
        for (cx, cy) in candidates
        if (cx, cy) != start and 0 <= cx <= max_x and 1 <= cy <= max_y
    ]

    if valid_candidates:
        best_d: Optional[int] = None
        bucket: List[Tuple[int, int]] = []
        with _LOCK_TARGETS:
            claimed = _CLAIMED_TARGETS.setdefault(warehouse_id, set())
            for c in valid_candidates:
                if c in claimed:
                    continue
                d = _manhattan(start, c)
                if best_d is None or d < best_d:
                    best_d, bucket = d, [c]
                elif d == best_d:
                    bucket.append(c)
            if bucket:
                goal = random.choice(bucket)
                claimed.add(goal)  # клеймим, чтобы другие не выбрали ту же клетку
                return goal

    # сюда попадаем, если кандидатов нет ИЛИ все заклеймлены — бродим
    return _random_wander_target(start, max_x, max_y)

# =========================
# Отправка событий (через Redis шину)
# =========================

async def _emit(evt: dict) -> None:
    """
    Публикуем событие в Redis-канал:
    - 'ws:robot' для частой телеметрии (position/scan),
    - 'ws:common' для остального.
    """
    evt_type = (evt.get("type") or "").lower()
    channel = ROBOT_CH if evt_type in ROBOT_EVENT_TYPES else COMMON_CH
    bus = await get_bus_for_current_loop()
    await bus.publish(channel, evt)


async def _emit_position(warehouse_id: str, robot_id: str, x: int, y: int, status: str, battery_level: float) -> None:
    # коалесинг по состоянию
    batt_int = int(round(battery_level))
    key = (x, y, status or "idle", batt_int)
    last = _LAST_EMITTED_STATE.get(robot_id)
    if last == key:
        return

    # rate-limit per-warehouse
    now = datetime.now(timezone.utc)
    last_ts = _LAST_POSITION_SENT_AT.get(warehouse_id, datetime.fromtimestamp(0, tz=timezone.utc))
    if (now - last_ts) < POSITION_RATE_LIMIT:
        return
    _LAST_POSITION_SENT_AT[warehouse_id] = now

    _LAST_EMITTED_STATE[robot_id] = key
    bus = await get_bus_for_current_loop()
    await bus.publish(ROBOT_CH, {
        "type": "robot.position",
        "warehouse_id": warehouse_id,
        "robot_id": robot_id,
        "x": x,
        "y": y,
        "shelf": shelf_num_to_str(y),
        "battery_level": round(float(battery_level or 0.0), 1),
        "status": status or "idle",
    })

# =========================
# Один тик робота
# =========================

async def _move_robot_once_impl(session: AsyncSession, robot_id: str, interval: float) -> None:
    try:
        result = await session.execute(
            select(Robot).where(Robot.id == robot_id).options(selectinload(Robot.warehouse))
        )
    except Exception as e:
        print(f"⚠️ _move_robot_once_impl: DB error fetching robot {robot_id}: {e}", flush=True)
        return

    robot = result.scalar_one_or_none()
    if not robot:
        return

    if (robot.status or "").lower() == "charging" and robot.id not in _CHARGE_ACCUM:
        _CHARGE_ACCUM[robot.id] = 0.0

    wh = robot.warehouse
    max_x = max(0, (wh.row_x or 1) - 1)
    max_y = max(1, min((wh.row_y or 1), 26))
    drop_per_step = _drop_per_step_for_field(max_x, max_y)

    # сканирование
    with _LOCK_SCAN:
        scanning_until = _SCANNING_UNTIL.get(robot.id)
        scanning_target = _SCANNING_TARGET.get(
            robot.id,
            (int(robot.current_row or 0), int(robot.current_shelf or 0)),
        )
    if (robot.status or "").lower() == "scanning":
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)
        now_utc = datetime.now(timezone.utc)

        # восстановление таймеров после рестартов
        if scanning_until is None:
            with _LOCK_SCAN:
                _SCANNING_TARGET[robot.id] = scanning_target
                _SCANNING_UNTIL[robot.id] = now_utc + SCAN_DURATION
                scanning_until = _SCANNING_UNTIL[robot.id]

        if scanning_until and now_utc >= scanning_until:
            await _finish_scan(session, robot)
            return

        if scanning_until:
            try:
                started_at = scanning_until - SCAN_DURATION
                if now_utc - started_at > (SCAN_DURATION * SCAN_STUCK_FACTOR):
                    print(f"⚠️ scan stuck: forcing finish (robot={robot.id})", flush=True)
                    await _finish_scan(session, robot)
                    return
            except Exception:
                await _finish_scan(session, robot)
                return
        return

    # зарядка
    if (robot.status or "").lower() == "charging":
        robot.current_row, robot.current_shelf = DOCK_X, DOCK_Y
        charge_step = 100.0 * interval / CHARGE_DURATION.total_seconds()
        acc = _CHARGE_ACCUM.get(robot.id, 0.0) + charge_step
        inc = int(acc // 1.0)
        if inc > 0:
            acc -= inc
            current_lvl = float(robot.battery_level or 0.0)
            robot.battery_level = min(100.0, current_lvl + inc)
        _CHARGE_ACCUM[robot.id] = acc

        _touch_robot(robot)
        await _log_status_every_tick(session, robot)
        if float(robot.battery_level or 0.0) >= 100.0:
            robot.status = "idle"
            _touch_robot(robot)
            await _log_status_every_tick(session, robot)
            _CHARGE_ACCUM.pop(robot.id, None)
        return

    # цель
    cur = (int(robot.current_row or 0), int(robot.current_shelf or 0))
    with _LOCK_TARGETS:
        goal = _TARGETS.get(robot.id)

    if goal is None or goal == cur:
        if goal:
            _free_claim(robot.warehouse_id, goal)

        try:
            cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
            # кандидаты = клетки, где есть хотя бы один товар, доступный к скану
            cells = await _eligible_scan_cells(session, robot.warehouse_id, cutoff)
        except Exception as e:
            print(f"⚠️ eligible cells fetch error (wh={robot.warehouse_id}): {e}", flush=True)
            cells = []

        if cells:
            goal = _pick_goal(robot.warehouse_id, cur, cells, max_x, max_y)
        else:
            # если прямо сейчас нет доступных товаров — бродим
            goal = _random_wander_target(cur, max_x, max_y)

        with _LOCK_TARGETS:
            _TARGETS[robot.id] = goal

    # шаг
    step = _next_step_towards(cur, goal)
    nx = _bounded(step[0], 0, max_x)
    ny = _bounded(step[1], 0, max_y)

    moved = (nx, ny) != cur
    if moved:
        _consume_battery(robot, drop_per_step)

    if float(robot.battery_level or 0.0) <= 0.0:
        robot.current_row, robot.current_shelf = DOCK_X, DOCK_Y
        robot.status = "charging"
        _CHARGE_ACCUM[robot.id] = 0.0
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)
        _free_claim(robot.warehouse_id, goal)
        with _LOCK_TARGETS:
            _TARGETS.pop(robot.id, None)
        return

    # обновляем состояние
    robot.current_row, robot.current_shelf, robot.status = nx, ny, "idle"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)

    # если пришли в цель — запускаем скан или сбрасываем цель
    if (nx, ny) == goal:
        cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
        try:
            eligible = await _eligible_products_for_scan(session, robot.warehouse_id, nx, ny, cutoff)
        except Exception as e:
            print(f"⚠️ eligible_products DB error (wh={robot.warehouse_id} at {nx},{ny}): {e}", flush=True)
            eligible = []

        if not eligible:
            # клетка стала недоступной (кто-то успел отсканировать) — снимаем клейм
            _free_claim(robot.warehouse_id, goal)
            with _LOCK_TARGETS:
                _TARGETS.pop(robot.id, None)
        else:
            await _begin_scan(session, robot, nx, ny)
            with _LOCK_TARGETS:
                _TARGETS.pop(robot.id, None)

# =====================================================================
#              ПОТОК НА КАЖДОГО РОБОТА (НОВОЕ)
# =====================================================================

class RobotRunner:
    """
    Отдельный поток + свой event loop под конкретного робота.
    Внутри — свой AsyncEngine/SessionMaker и свой Redis-bus, привязанные к loop.
    """
    def __init__(self, warehouse_id: str, robot_id: str):
        self.warehouse_id = warehouse_id
        self.robot_id = robot_id
        self._thread = threading.Thread(
            target=self._thread_main, name=f"robot-runner-{robot_id[:6]}", daemon=True
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue[Optional[Callable[[], Awaitable[None]]]]] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._engine: Optional[AsyncEngine] = None
        self._started = threading.Event()
        self._stopped = False

    def start(self) -> None:
        self._thread.start()
        self._started.wait()

    def stop(self) -> None:
        if not self._loop:
            return
        self._stopped = True
        fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        fut.result(timeout=10)
        self._thread.join(timeout=10)

    async def _shutdown(self):
        assert self._queue is not None
        await self._queue.put(None)

    def submit_tick(self, interval: float) -> None:
        if not self._loop or not self._queue:
            return

        async def job():
            assert self._session_factory is not None
            async with self._session_factory() as s:
                async with s.begin():
                    await _move_robot_once_impl(s, self.robot_id, interval)

        asyncio.run_coroutine_threadsafe(self._queue.put(job), self._loop)

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.Queue()

        try:
            self._session_factory, self._engine = _session_factory_for_current_loop()
        except Exception:
            self._started.set()
            return

        self._started.set()

        async def runner():
            try:
                while not self._stopped:
                    maker = await self._queue.get()
                    if maker is None:
                        break
                    try:
                        await maker()
                    except Exception as e:
                        print(f"⚠️ RobotRunner({self.robot_id}) job error: {e}", flush=True)
            except asyncio.CancelledError:
                pass

        try:
            loop.create_task(runner())
            loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for t in pending:
                    t.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                if self._engine is not None:
                    loop.run_until_complete(self._engine.dispose())
                loop.run_until_complete(close_bus_for_current_loop())
            finally:
                loop.close()

# =====================================================================
#              ПОСТОЯННЫЙ ВОРКЕР-ПОТОК НА СКЛАД
# =====================================================================

class WarehouseRunner:
    """Постоянный поток на склад: свой loop, свой AsyncEngine/sessionmaker под этот loop."""

    def __init__(self, warehouse_id: str):
        self.warehouse_id = warehouse_id
        self._thread = threading.Thread(target=self._thread_main, name=f"wh-runner-{warehouse_id[:6]}", daemon=True)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._engine: Optional[AsyncEngine] = None
        self._queue: Optional[asyncio.Queue[Optional[Callable[[], Awaitable[None]]]]] = None
        self._started = threading.Event()
        self._stopped = False
        self._sema: Optional[asyncio.Semaphore] = None
        self._robot_runners: Dict[str, RobotRunner] = {}  # >>> ADDED

    def start(self) -> None:
        self._thread.start()
        self._started.wait()

    def stop(self) -> None:
        # >>> ADDED: сначала останавливаем роботов
        for rid, rr in list(self._robot_runners.items()):
            try:
                rr.stop()
            except Exception as e:
                print(f"⚠️ Stop RobotRunner {rid} error: {e}", flush=True)
            finally:
                self._robot_runners.pop(rid, None)

        if not self._loop:
            return
        self._stopped = True
        fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        fut.result(timeout=10)
        self._thread.join(timeout=10)

    async def _shutdown(self):
        assert self._queue is not None
        await self._queue.put(None)

    def submit_tick(self, interval: float) -> None:
        if not self._loop or not self._queue:
            return

        async def job():
            await self._run_one_tick(interval)

        asyncio.run_coroutine_threadsafe(self._queue.put(job), self._loop)

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.Queue()

        # свой engine/sessionmaker для этого event loop
        try:
            self._session_factory, self._engine = _session_factory_for_current_loop()
        except Exception:
            # не смогли создать движок — петля бессмысленна
            self._started.set()
            return

        self._sema = asyncio.Semaphore(_MAX_CONCURRENT_ROBOTS_PER_WAREHOUSE)
        self._started.set()

        async def runner():
            try:
                while not self._stopped:
                    maker = await self._queue.get()
                    if maker is None:
                        break
                    try:
                        await maker()
                    except Exception as e:
                        print(f"⚠️ WarehouseRunner({self.warehouse_id}) job error: {e}", flush=True)
            except asyncio.CancelledError:
                pass

        try:
            loop.create_task(runner())
            loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for t in pending:
                    t.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                if self._engine is not None:
                    loop.run_until_complete(self._engine.dispose())
                # аккуратно закрыть Redis-клиента, привязанного к этому loop
                loop.run_until_complete(close_bus_for_current_loop())
            finally:
                loop.close()

    async def _janitor(self) -> None:
        now = datetime.now(timezone.utc)
        next_at = _WAREHOUSE_NEXT_JANITOR_AT.get(self.warehouse_id, datetime.fromtimestamp(0, tz=timezone.utc))
        if now < next_at:
            return
        _WAREHOUSE_NEXT_JANITOR_AT[self.warehouse_id] = now + WAREHOUSE_JANITOR_EVERY

        assert self._session_factory is not None
        async with self._session_factory() as session:
            result = await session.execute(select(Robot.id).where(Robot.warehouse_id == self.warehouse_id))
            active_robot_ids = set(result.scalars().all())

        def _prune(mapping: Dict[str, object]):
            dead = [rid for rid in list(mapping.keys()) if rid not in active_robot_ids]
            for rid in dead:
                try:
                    mapping.pop(rid, None)
                except Exception:
                    pass

        _prune(_TARGETS)
        _prune(_SCANNING_UNTIL)      # type: ignore[arg-type]
        _prune(_SCANNING_TARGET)     # type: ignore[arg-type]
        _prune(_CHARGE_ACCUM)        # type: ignore[arg-type]
        _prune(_LAST_EMITTED_STATE)  # type: ignore[arg-type]
        _prune(_LAST_LOGGED_STATE)   # type: ignore[arg-type]
        _prune(_LAST_HISTORY_AT)     # type: ignore[arg-type]

        # Чистку InventoryHistory полностью отключаем,
        # если INVENTORY_HISTORY_RETENTION не задана (None).
        if INVENTORY_HISTORY_RETENTION is not None:
            cutoff = now - INVENTORY_HISTORY_RETENTION
            try:
                async with self._session_factory() as s:
                    async with s.begin():
                        ids_stmt = (
                            select(InventoryHistory.id)
                            .where(
                                InventoryHistory.warehouse_id == self.warehouse_id,
                                InventoryHistory.created_at < cutoff
                            )
                            .limit(INVENTORY_HISTORY_CLEAN_CHUNK)
                        )
                        ids_res = await s.execute(ids_stmt)
                        ids = [row[0] for row in ids_res.fetchall()]
                        if ids:
                            await s.execute(
                                delete(InventoryHistory).where(InventoryHistory.id.in_(ids))
                            )
            except Exception as e:
                print(f"⚠️ Janitor({self.warehouse_id}) cleanup error: {e}", flush=True)

    async def _run_one_tick(self, interval: float) -> None:
        assert self._session_factory is not None
        try:
            async with self._session_factory() as session:
                result = await session.execute(select(Robot.id).where(Robot.warehouse_id == self.warehouse_id))
                robot_ids = list(result.scalars().all())
        except Exception as e:
            print(f"⚠️ _run_one_tick: DB error fetching robot ids (wh={self.warehouse_id}): {e}", flush=True)
            await self._janitor()
            return

        if not robot_ids:
            await self._janitor()
            return

        if ENABLE_ROBOT_THREADS:
            # Поднимаем новые потоки
            for rid in robot_ids:
                if rid not in self._robot_runners:
                    rr = RobotRunner(self.warehouse_id, rid)
                    rr.start()
                    self._robot_runners[rid] = rr
            # Гасим исчезнувших
            for rid in list(self._robot_runners.keys()):
                if rid not in robot_ids:
                    try:
                        self._robot_runners[rid].stop()
                    except Exception as e:
                        print(f"⚠️ Stop RobotRunner {rid} error: {e}", flush=True)
                    finally:
                        self._robot_runners.pop(rid, None)
            # Пинаем каждый роботный поток своим тиком
            for rid, rr in self._robot_runners.items():
                rr.submit_tick(interval)
        else:
            # Старое поведение: asyncio внутри потока склада
            sema = self._sema or asyncio.Semaphore(_MAX_CONCURRENT_ROBOTS_PER_WAREHOUSE)

            async def run_one_robot(rid: str):
                async with sema:
                    async with self._session_factory() as s:
                        async with s.begin():
                            await _move_robot_once_impl(s, rid, interval)

            await asyncio.gather(*[run_one_robot(rid) for rid in robot_ids])

        if EMIT_POSITION_BATCH:
            async with self._session_factory() as s2:
                result = await s2.execute(select(Robot).where(Robot.warehouse_id == self.warehouse_id))
                robots = list(result.scalars().all())
            batch = []
            for r in robots:
                y = int(r.current_shelf or 0)
                batch.append({
                    "robot_id": r.id,
                    "x": int(r.current_row or 0),
                    "y": y,
                    "shelf": shelf_num_to_str(y),
                    "battery_level": int(round(float(r.battery_level or 0.0))),
                    "status": (r.status or "idle"),
                })
            await _emit({
                "type": "robot.position",
                "warehouse_id": self.warehouse_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "robots": batch,
            })

        await self._janitor()

# =========================
# Вотчер
# =========================

def _try_acquire_process_lock(lock_path: Optional[str]) -> bool:
    global _LOCK_FILE_HANDLE
    if not lock_path or fcntl is None:
        return True
    try:
        fh = open(lock_path, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.write(f"pid={os.getpid()} time={datetime.now(timezone.utc).isoformat()}\n")
        fh.flush()
        _LOCK_FILE_HANDLE = fh
        return True
    except BlockingIOError:
        return False
    except Exception:
        return True


def _release_process_lock():
    global _LOCK_FILE_HANDLE
    if _LOCK_FILE_HANDLE is None:
        return
    try:
        if fcntl is not None:
            fcntl.flock(_LOCK_FILE_HANDLE, fcntl.LOCK_UN)
    finally:
        try:
            _LOCK_FILE_HANDLE.close()
        except Exception:
            pass
        _LOCK_FILE_HANDLE = None


async def run_robot_watcher(
    interval: float = 2,
    max_robot_workers: int = 20,
    max_warehouse_workers: int = 4,
    require_singleton: bool = True,
    singleton_lock_path: Optional[str] = DEFAULT_WATCHER_LOCK_PATH,
) -> None:
    """
    - Для каждого активного склада поднимается постоянный воркер-поток со своим loop.
    - В каждом воркере СВОЙ AsyncEngine/Session.
    - Публикации событий идут в Redis-каналы (ROBOT_CH/COMMON_CH) через bus, привязанный к текущему loop’у.
    - Память стабилизируется за счёт janitor-ов и коалесинга/рателимита событий.
    """
    global _WATCHER_RUNNING

    if require_singleton and _WATCHER_RUNNING:
        print("ℹ️ Robot watcher already running in this process — skipping second start.", flush=True)
        return

    if require_singleton:
        if not _try_acquire_process_lock(singleton_lock_path):
            print(f"ℹ️ Robot watcher: another instance holds lock {singleton_lock_path!r}. Skipping start.", flush=True)
            return

    _WATCHER_RUNNING = True
    runners: Dict[str, WarehouseRunner] = {}  # >>> moved вверх, чтобы быть доступным в finally

    try:
        print(f"🚀 Robot watcher started (persistent warehouse workers). pid={os.getpid()}", flush=True)

        while True:
            session_factory_main = _session_factory_main()
            async with session_factory_main() as session:
                result = await session.execute(
                    select(Warehouse).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
                )
                warehouses = list(result.scalars().all())

            active_ids = {wh.id for wh in warehouses}

            # старт новых
            for wh in warehouses:
                if wh.id not in runners:
                    runner = WarehouseRunner(wh.id)
                    runner.start()
                    runners[wh.id] = runner

            # остановка исчезнувших
            for wid in list(runners.keys()):
                if wid not in active_ids:
                    runners[wid].stop()
                    del runners[wid]
                    with _LOCK_TARGETS:
                        _CLAIMED_TARGETS.pop(wid, None)
                    _LAST_SCAN_CACHE.pop(wid, None)
                    _WAREHOUSE_NEXT_JANITOR_AT.pop(wid, None)

            # тик всем активным
            for _, runner in runners.items():
                runner.submit_tick(interval)

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("\n🛑 Robot watcher stopping...", flush=True)
    finally:
        for wid, runner in list(runners.items()):
            try:
                runner.stop()
            except Exception as e:
                print(f"⚠️ Stop runner {wid} error: {e}", flush=True)
        _release_process_lock()
        _WATCHER_RUNNING = False
        print("✅ Robot watcher stopped.", flush=True)
