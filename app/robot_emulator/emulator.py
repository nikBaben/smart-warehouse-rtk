from __future__ import annotations

import asyncio
import random
import uuid
import threading
import queue
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Set, Callable, Awaitable, Union

# POSIX file-lock для синглтона
try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None  # на Windows просто не используем файловый лок

from sqlalchemy import select, distinct, func, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
from sqlalchemy.orm import selectinload

# settings может и не содержать DATABASE_URL — это ок, ниже больше не полагаемся на него напрямую
from app.core.config import settings
# ВАЖНО: импортируем ДВЕ janus-очереди
from app.ws.ws_manager import EVENTS_COMMON, EVENTS_ROBOT
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from app.models.product import Product
from app.models.inventory_history import InventoryHistory
from app.service.robot_history import write_robot_status_event  # лог статусов


# =========================
# Управление форматом событий позиции
# =========================
EMIT_POSITION_PER_ROBOT = True   # одиночные события для каждого робота
EMIT_POSITION_BATCH = False      # один батч на склад за тик

# =========================
# Параметры поля / зарядки / сканирования
# =========================
DOCK_X, DOCK_Y = 0, 0                    # док-станция — ровно (0,0)
SCAN_DURATION = timedelta(seconds=5)     # длительность скана
CHARGE_DURATION = timedelta(minutes=15)  # длительность полной зарядки до 100%
MIN_BATT_DROP_PER_STEP = 0.2             # ниже расход на шаг (в процентах)
# делаем рескан «тише», чтобы не штормить WS
RESCAN_COOLDOWN = timedelta(minutes=3)   # повторный скан того же товара — не чаще чем раз в 3 минуты

# =========================
# Конфигурация логирования истории робота (оптимизация нагрузки на БД)
# =========================
LOG_EVERY_TICK = False                          # если True — лог как раньше, каждый тик
TICK_LOG_MIN_INTERVAL = timedelta(seconds=15)   # минимальный интервал heartbeat-логов при неизменном состоянии

# =========================
# Память процесса + блокировки (для потокобезопасности)
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

# Кеш клеток с товарами на склад (TTL)
_PRODUCT_CELLS_CACHE: Dict[str, Tuple[datetime, List[Tuple[int, int]]]] = {}
PRODUCT_CELLS_TTL = timedelta(seconds=90)

# Кэш последних сканов по складу: product_id -> max(created_at) (TTL)
_LAST_SCAN_CACHE: Dict[str, Tuple[datetime, Dict[str, datetime]]] = {}
LAST_SCAN_TTL = timedelta(seconds=30)

# Ограничитель конкурентных роботов на склад
_MAX_CONCURRENT_ROBOTS_PER_WAREHOUSE = 8

# =========================
# Антизасор: события, ретеншн и клининг
# =========================
EVENT_QUEUE_MAXSIZE = int(os.getenv("EVENT_QUEUE_MAXSIZE", "10000"))
EVENT_QUEUE_DROP_OLDEST = True  # при переполнении выбрасываем самый старый элемент

INVENTORY_HISTORY_RETENTION = timedelta(hours=6)   # сколько держим полные сканы
INVENTORY_HISTORY_CLEAN_CHUNK = 1000               # сколько записей удаляем за проход
WAREHOUSE_JANITOR_EVERY = timedelta(minutes=5)     # частота служебной уборки per warehouse

# =========================
# Rate-limit и типы «роботных» событий
# =========================
ROBOT_EVENT_TYPES = {"robot.position", "product.scan"}
POSITION_RATE_LIMIT = timedelta(seconds=2)  # частота отправки позиций per-warehouse
_LAST_POSITION_SENT_AT: Dict[str, datetime] = {}

# =========================
# Синглтон-гарды для вотчера
# =========================
_WATCHER_RUNNING = False
_LOCK_FILE_HANDLE = None  # type: ignore
DEFAULT_WATCHER_LOCK_PATH = os.environ.get("ROBOT_WATCHER_LOCK", "/tmp/robot_watcher.lock")

# расписание уборки per warehouse
_WAREHOUSE_NEXT_JANITOR_AT: Dict[str, datetime] = {}


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

# =========================
# Утилиты координат/полок
# =========================

def shelf_str_to_num(s: Optional[str]) -> int:
    if s is None:
        return 1
    s = s.strip()
    if s == "0":
        return 0
    if not s:
        return 1
    c = s.upper()[:1]
    return (ord(c) - ord("A")) + 1 if "A" <= c <= "Z" else 1


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
    """Соседние клетки по Манхэттену (4-связность) с учётом границ поля (y ∈ [1..max_y])."""
    sx, sy = start
    cand = [
        (sx + 1, sy), (sx - 1, sy),
        (sx, sy + 1), (sx, sy - 1),
    ]
    res: List[Tuple[int, int]] = []
    for x, y in cand:
        if 0 <= x <= max_x and 1 <= y <= max_y:
            res.append((x, y))
    return res


def _random_wander_target(start: Tuple[int, int], max_x: int, max_y: int) -> Tuple[int, int]:
    """Цель для «бродяжничества», когда нет кандидатов для сканирования."""
    opts = [p for p in _neighbors(start, max_x, max_y) if p != start]
    return random.choice(opts) if opts else start

# =========================
# Главный sessionmaker для главного лупа (общий на процесс)
# =========================

def _session_factory_main() -> async_sessionmaker[AsyncSession]:
    from app.db.session import async_session as app_sessionmaker
    return app_sessionmaker

# ---------- НОВОЕ: надёжное определение DSN и фабрика engine/session под ТЕКУЩИЙ loop ----------

def _resolve_db_url() -> str:
    """
    Берём URL из уже сконфигурированного главного sessionmaker (его bind.url).
    Если вдруг недоступно — пробуем переменные окружения.
    """
    try:
        main_maker = _session_factory_main()
        # В разных версиях SQLAlchemy доступ к bind может лежать по-разному
        eng = getattr(main_maker, "bind", None)
        if eng is None:
            eng = getattr(main_maker, "kw", {}).get("bind")  # fallback для 2.x
        if eng is not None:
            try:
                # 2.x
                return eng.url.render_as_string(hide_password=False)
            except Exception:
                # 1.4 стиль
                return str(eng.url)
    except Exception:
        pass

    for key in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "DB_DSN"):
        v = os.getenv(key)
        if v:
            return v

    # Последняя попытка — вдруг в settings под другим именем
    for attr in ("DATABASE_URL", "SQLALCHEMY_DATABASE_URI", "DB_DSN"):
        if hasattr(settings, attr):
            return getattr(settings, attr)  # type: ignore

    raise RuntimeError(
        "Не удалось определить URL базы данных: нет bind у основного sessionmaker, "
        "и не найдены переменные окружения DATABASE_URL/SQLALCHEMY_DATABASE_URI/DB_DSN."
    )


def _session_factory_for_current_loop() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """
    Создаёт НОВЫЙ AsyncEngine и async_sessionmaker, привязанные к текущему event loop.
    Важно: не делим engine между разными лупами/тредами.
    """
    db_url = _resolve_db_url()
    engine = create_async_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
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
async def _product_cells(session: AsyncSession, warehouse_id: str) -> List[Tuple[int, int]]:
    q = (
        select(distinct(Product.current_row), Product.current_shelf)
        .where(Product.warehouse_id == warehouse_id)
    )
    rows = await session.execute(q)
    cells: List[Tuple[int, int]] = []
    for r, shelf_str in rows.all():
        x = int(r or 0)
        y = shelf_str_to_num(shelf_str)
        if y <= 0:
            continue
        cells.append((x, y))
    return cells


async def _product_cells_cached(session: AsyncSession, warehouse_id: str) -> List[Tuple[int, int]]:
    now = datetime.now(timezone.utc)
    cached = _PRODUCT_CELLS_CACHE.get(warehouse_id)
    if cached and (now - cached[0]) < PRODUCT_CELLS_TTL:
        return cached[1]
    cells = await _product_cells(session, warehouse_id)
    _PRODUCT_CELLS_CACHE[warehouse_id] = (now, cells)
    return cells


async def _last_scans_map(session: AsyncSession, warehouse_id: str) -> Dict[str, datetime]:
    now = datetime.now(timezone.utc)
    cached = _LAST_SCAN_CACHE.get(warehouse_id)
    if cached and (now - cached[0]) < LAST_SCAN_TTL:
        return cached[1]

    q = (
        select(
            InventoryHistory.product_id,
            func.max(InventoryHistory.created_at)
        )
        .where(InventoryHistory.warehouse_id == warehouse_id)
        .group_by(InventoryHistory.product_id)
    )
    rows = await session.execute(q)
    mp = {pid: ts for pid, ts in rows.all()}
    _LAST_SCAN_CACHE[warehouse_id] = (now, mp)
    return mp


async def _eligible_products_for_scan(
    session: AsyncSession,
    warehouse_id: str,
    x: int,
    y: int,
    cutoff: datetime,
) -> List[Product]:
    shelf_letter = shelf_num_to_str(y)

    q = (
        select(Product)
        .where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            Product.current_shelf == shelf_letter,
        )
    )
    rows = await session.execute(q)
    products: List[Product] = list(rows.scalars().all())
    if not products:
        return []

    last_map = await _last_scans_map(session, warehouse_id)
    eligible: List[Product] = [
        p for p in products
        if (last_map.get(p.id) is None) or (last_map[p.id] < cutoff)
    ]
    return eligible


async def _begin_scan(session: AsyncSession, robot: Robot, x: int, y: int) -> None:
    robot.status = "scanning"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)
    with _LOCK_SCAN:
        _SCANNING_TARGET[robot.id] = (x, y)
        _SCANNING_UNTIL[robot.id] = datetime.now(timezone.utc) + SCAN_DURATION

    if EMIT_POSITION_PER_ROBOT:
        _emit_position(robot.warehouse_id, robot.id, x, y, robot.status, float(robot.battery_level or 0.0))


async def _finish_scan(session: AsyncSession, robot: Robot) -> None:
    with _LOCK_SCAN:
        rx, ry = _SCANNING_TARGET.pop(robot.id, (int(robot.current_row or 0), int(robot.current_shelf or 0)))
        _SCANNING_UNTIL.pop(robot.id, None)

    shelf_letter = shelf_num_to_str(ry)
    result = await session.execute(
        select(Product).where(
            Product.warehouse_id == robot.warehouse_id,
            Product.current_row == rx,
            Product.current_shelf == shelf_letter,
        )
    )
    products = list(result.scalars().all())

    if products:
        cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
        last_map = await _last_scans_map(session, robot.warehouse_id)
        products = [
            p for p in products
            if (last_map.get(p.id) is None) or (last_map[p.id] < cutoff)
        ]

    if not products:
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

    _emit({
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
    # делаем поле «экономнее» — примерно в 2 раза ниже базовый расход
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
        return target in _claimed_set(warehouse_id)


def _pick_goal(
    warehouse_id: str,
    start: Tuple[int, int],
    candidates: List[Tuple[int, int]],
    max_x: int,
    max_y: int,
) -> Tuple[int, int]:
    if candidates:
        best_d = None
        bucket: List[Tuple[int, int]] = []
        with _LOCK_TARGETS:
            claimed = _claimed_set(warehouse_id)
            for c in candidates:
                if c in claimed:
                    continue
                d = _manhattan(start, c)
                if best_d is None or d < best_d:
                    best_d, bucket = d, [c]
                elif d == best_d:
                    bucket.append(c)
            if bucket:
                goal = random.choice(bucket)
                claimed.add(goal)
                return goal

    # если кандидатов нет — ранний фолбэк к случайной свободной клетке
    for _ in range(50):
        gx = random.randint(0, max_x)
        gy = random.randint(1, max_y)
        goal = (gx, gy)
        with _LOCK_TARGETS:
            claimed = _claimed_set(warehouse_id)
            if goal != start and goal not in claimed:
                claimed.add(goal)
                return goal

    return start

# =========================
# Отправка событий (неблокирующая + антидубль, с разделением очередей)
# =========================

def _emit(evt: dict) -> None:
    """Кладём событие в соответствующую janus-очередь: ROBOT или COMMON, с вытеснением старого при переполнении."""
    q = EVENTS_ROBOT if evt.get("type") in ROBOT_EVENT_TYPES else EVENTS_COMMON
    try:
        q.sync_q.put_nowait(evt)  # janus: синхронная сторона
    except queue.Full:
        # при переполнении — выбрасываем старый элемент ЭТОЙ ЖЕ очереди (не трогаем другую)
        try:
            q.sync_q.get_nowait()
        except Exception:
            pass
        try:
            q.sync_q.put_nowait(evt)
        except Exception:
            pass
    except Exception:
        pass


def _emit_position(warehouse_id: str, robot_id: str, x: int, y: int, status: str, battery_level: float) -> None:
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
    _emit({
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
    result = await session.execute(
        select(Robot).where(Robot.id == robot_id).options(selectinload(Robot.warehouse))
    )
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
    if (robot.status or "").lower() == "scanning":
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)
        if scanning_until and datetime.now(timezone.utc) >= scanning_until:
            await _finish_scan(session, robot)
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

        if EMIT_POSITION_PER_ROBOT:
            _emit_position(
                robot.warehouse_id,
                robot.id,
                int(robot.current_row or 0),
                int(robot.current_shelf or 0),
                robot.status,
                float(robot.battery_level or 0.0),
            )
        return

    # цель
    cur = (int(robot.current_row or 0), int(robot.current_shelf or 0))
    with _LOCK_TARGETS:
        goal = _TARGETS.get(robot.id)

    if goal is None or goal == cur:
        if goal:
            _free_claim(robot.warehouse_id, goal)

        cells = await _product_cells_cached(session, robot.warehouse_id)
        if cells:
            # обычная логика — целимся в ближайшую клетку с товарами, избегая конфликтов
            goal = _pick_goal(robot.warehouse_id, cur, cells, max_x, max_y)
        else:
            # «бродим» по соседним клеткам без бронирования, если нечего сканировать
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
        if EMIT_POSITION_PER_ROBOT:
            _emit_position(
                robot.warehouse_id,
                robot.id,
                int(robot.current_row or 0),
                int(robot.current_shelf or 0),
                robot.status,
                float(robot.battery_level or 0.0),
            )
        _free_claim(robot.warehouse_id, goal)
        with _LOCK_TARGETS:
            _TARGETS.pop(robot.id, None)
        return

    # обновляем состояние
    robot.current_row, robot.current_shelf, robot.status = nx, ny, "idle"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)

    if EMIT_POSITION_PER_ROBOT:
        _emit_position(robot.warehouse_id, robot.id, nx, ny, robot.status, float(robot.battery_level or 0.0))

    # если пришли в цель — запускаем скан или сбрасываем цель
    if (nx, ny) == goal:
        cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
        eligible = await _eligible_products_for_scan(session, robot.warehouse_id, nx, ny, cutoff)
        if not eligible:
            _free_claim(robot.warehouse_id, goal)
            with _LOCK_TARGETS:
                _TARGETS.pop(robot.id, None)
        else:
            await _begin_scan(session, robot, nx, ny)
            with _LOCK_TARGETS:
                _TARGETS.pop(robot.id, None)

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
        # очередь корутин (а не callables с ensure_future) — далее runner их AWAIT-ит
        self._queue: Optional[asyncio.Queue[Optional[Callable[[], Awaitable[None]]]]] = None
        self._started = threading.Event()
        self._stopped = False
        self._sema: Optional[asyncio.Semaphore] = None

    def start(self) -> None:
        self._thread.start()
        self._started.wait()

    def stop(self) -> None:
        if not self._loop:
            return
        self._stopped = True
        # кладём sentry None и ждём остановку цикла
        fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        fut.result(timeout=10)
        self._thread.join(timeout=10)

    async def _shutdown(self):
        assert self._queue is not None
        await self._queue.put(None)
        # остановка цикла произойдёт в _thread_main после выхода runner()

    def submit_tick(self, interval: float) -> None:
        if not self._loop or not self._queue:
            return

        async def job():
            await self._run_one_tick(interval)

        # складываем КОРУТИНУ, а не запускаем её тут
        asyncio.run_coroutine_threadsafe(self._queue.put(job), self._loop)

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.Queue()

        # ВАЖНО: создаём СВОЙ engine/sessionmaker для этого event loop
        self._session_factory, self._engine = _session_factory_for_current_loop()

        self._sema = asyncio.Semaphore(_MAX_CONCURRENT_ROBOTS_PER_WAREHOUSE)
        self._started.set()

        async def runner():
            try:
                while not self._stopped:
                    maker = await self._queue.get()
                    if maker is None:
                        break
                    try:
                        # теперь мы ЖДЁМ выполнение задачи, а не плодим ensure_future
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
            finally:
                loop.close()

    async def _janitor(self) -> None:
        """Периодический клининг: чистим глобальные словари и ограничиваем рост таблиц."""
        now = datetime.now(timezone.utc)
        # расписание
        next_at = _WAREHOUSE_NEXT_JANITOR_AT.get(self.warehouse_id, datetime.fromtimestamp(0, tz=timezone.utc))
        if now < next_at:
            return
        _WAREHOUSE_NEXT_JANITOR_AT[self.warehouse_id] = now + WAREHOUSE_JANITOR_EVERY

        # 1) выясняем активные роботы этого склада
        assert self._session_factory is not None
        async with self._session_factory() as session:
            result = await session.execute(select(Robot.id).where(Robot.warehouse_id == self.warehouse_id))
            active_robot_ids = set(result.scalars().all())

        # 2) чистим глобальные структуры от «мертвых» роботов
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

        # 3) подчищаем историю инвентаризации по чуть-чуть
        cutoff = now - INVENTORY_HISTORY_RETENTION
        try:
            async with self._session_factory() as s:
                async with s.begin():
                    # dialect-agnostic delete with LIMIT: выбираем id батчем и удаляем по IN
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
                        await s.execute(delete(InventoryHistory).where(InventoryHistory.id.in_(ids)))
        except Exception as e:
            print(f"⚠️ Janitor({self.warehouse_id}) cleanup error: {e}", flush=True)

    async def _run_one_tick(self, interval: float) -> None:
        assert self._session_factory is not None
        async with self._session_factory() as session:
            result = await session.execute(select(Robot.id).where(Robot.warehouse_id == self.warehouse_id))
            robot_ids = list(result.scalars().all())
        if not robot_ids:
            # даже если роботов нет — запускаем периодический клининг
            await self._janitor()
            return

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
            _emit({
                "type": "robot.position",
                "warehouse_id": self.warehouse_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "robots": batch,
            })

        # периодический клининг после выполнения тика
        await self._janitor()

# =========================
# Вотчер
# =========================

async def run_robot_watcher(
    interval: float = 2,
    max_robot_workers: int = 20,
    max_warehouse_workers: int = 4,
    require_singleton: bool = True,
    singleton_lock_path: Optional[str] = DEFAULT_WATCHER_LOCK_PATH,
) -> None:
    """
    - Для каждого активного склада поднимается постоянный воркер-поток со своим loop.
    - В каждом воркере СОБСТВЕННЫЙ AsyncEngine/Session, привязанные к его loop
      (исправляет 'Future attached to a different loop').
    - Защита от роста памяти: ограниченная очередь событий + периодический janitor.
    - События маршрутизируются в отдельные janus-очереди (COMMON/ROBOT), чтобы телеметрия не блокировала прочие WS.
    """
    global _WATCHER_RUNNING

    if require_singleton and _WATCHER_RUNNING:
        print("ℹ️ Robot watcher already running in this process — skipping second start.", flush=True)
        return

    if require_singleton:
        if not _try_acquire_process_lock(singleton_lock_path):
            print(f"ℹ️ Robot watcher: another instance holds lock {singleton_lock_path!r}. Skipping start.", flush=True)
            return

    # гарантируем ограниченные очереди (janus уже ограничены в ws_manager),
    # здесь лишь информативный лог размеров:
    try:
        print(f"ℹ️ Queues: common_max={getattr(EVENTS_COMMON.sync_q, 'maxsize', '?')}, "
              f"robot_max={getattr(EVENTS_ROBOT.sync_q, 'maxsize', '?')}", flush=True)
    except Exception:
        pass

    _WATCHER_RUNNING = True

    try:
        print(f"🚀 Robot watcher started (persistent warehouse workers). pid={os.getpid()}", flush=True)
        runners: Dict[str, WarehouseRunner] = {}

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
                    # также подчистим кэши и claimed по складу
                    with _LOCK_TARGETS:
                        _CLAIMED_TARGETS.pop(wid, None)
                    _PRODUCT_CELLS_CACHE.pop(wid, None)
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
