# app/services/robot_mover.py
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Set
from threading import RLock
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.ws.ws_manager import EVENTS
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from app.models.product import Product
from app.models.inventory_history import InventoryHistory
from app.service.robot_history import write_robot_status_event  # лог статусов

# =========================
# Управление форматом событий позиции
# =========================
EMIT_POSITION_PER_ROBOT = True   # одиночные события для каждого робота
EMIT_POSITION_BATCH = False        # один батч на склад за тик

# =========================
# Параметры поля / зарядки / сканирования
# =========================
DOCK_X, DOCK_Y = 0, 0                    # док-станция — ровно (0,0)
SCAN_DURATION = timedelta(seconds=5)     # длительность скана
CHARGE_DURATION = timedelta(minutes=15)  # длительность полной зарядки до 100%
MIN_BATT_DROP_PER_STEP = 1.0             # нижняя граница расхода на шаг (в процентах)
RESCAN_COOLDOWN = timedelta(minutes=5)   # повторный скан того же товара — не чаще чем раз в 5 минут

# =========================
# Память процесса + блокировки (для потокобезопасности)
# =========================
_TARGETS: Dict[str, Tuple[int, int]] = {}            # цель каждого робота
_CLAIMED_TARGETS: Set[Tuple[int, int]] = set()       # занятые цели (между роботами)
_SCANNING_UNTIL: Dict[str, datetime] = {}            # время окончания сканирования
_SCANNING_TARGET: Dict[str, Tuple[int, int]] = {}    # координата сканируемой клетки
_CHARGE_ACCUM: Dict[str, float] = {}                 # аккумулятор дробных шагов зарядки

_LOCK_TARGETS = RLock()
_LOCK_SCAN = RLock()

# =========================
# Утилиты координат/полок
# =========================
def shelf_str_to_num(s: Optional[str]) -> int:
    """A..Z -> 1..26; '0' -> 0; None/пусто -> 1."""
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
    """0 -> '0' (док); 1..26 -> 'A'..'Z'."""
    if n <= 0:
        return "0"
    n = min(26, int(n))
    return chr(ord("A") + (n - 1))

def _bounded(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def _manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def _next_step_towards(start: Tuple[int, int], goal: Tuple[int, int]) -> Tuple[int, int]:
    """Один шаг по Манхэттену к цели."""
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

# =========================
# Сессии / движки
# =========================
def _session_factory_main() -> async_sessionmaker[AsyncSession]:
    """
    Главный sessionmaker для «коротких» операций в главном event loop (НЕ в потоках),
    например, чтобы получить список складов.
    """
    from app.db.session import async_session as app_sessionmaker
    return app_sessionmaker

def _thread_local_session_factory():
    """
    Создаёт НОВЫЙ async engine и sessionmaker в КАЖДОМ потоке.
    Нельзя передавать engine/sessionmaker между потоками/loop'ами — будут ошибки вида
    'Future attached to a different loop' и 'another operation is in progress'.
    """
    engine = create_async_engine(
        settings.DB_URL,
        echo=False,
        future=True,
        poolclass=NullPool,  # исключаем разделяемый пул между потоками
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return factory, engine

# =========================
# Логирование статуса — КАЖДЫЙ ТИК + touch last_update
# =========================
async def _log_status_every_tick(session: AsyncSession, robot: Robot) -> None:
    """Всегда пишем запись в RobotHistory, независимо от смены статуса."""
    with session.no_autoflush:
        await write_robot_status_event(session, robot.id)

def _touch_robot(robot: Robot) -> None:
    """Обновить last_update на текущий момент (UTC)."""
    robot.last_update = datetime.now(timezone.utc)

# =========================
# Работа с товарами / сканирование
# =========================
async def _product_cells(session: AsyncSession, warehouse_id: str) -> List[Tuple[int, int]]:
    """Уникальные координаты клеток, где есть товары (Y от 1 до 26)."""
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
            continue  # товары не лежат на '0' полке
        cells.append((x, y))
    return cells

async def _eligible_products_for_scan(
    session: AsyncSession,
    warehouse_id: str,
    x: int,
    y: int,
    cutoff: datetime,
) -> List[Product]:
    """Товары в ячейке (x,y), у которых нет сканов или последний скан старше cutoff."""
    shelf_letter = shelf_num_to_str(y)

    last_scan_sq = (
        select(
            InventoryHistory.product_id.label("pid"),
            func.max(InventoryHistory.created_at).label("last_scan"),
        )
        .where(InventoryHistory.warehouse_id == warehouse_id)
        .group_by(InventoryHistory.product_id)
        .subquery()
    )

    q = (
        select(Product, last_scan_sq.c.last_scan)
        .outerjoin(last_scan_sq, last_scan_sq.c.pid == Product.id)
        .where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            Product.current_shelf == shelf_letter,
        )
    )
    rows = await session.execute(q)
    eligible: List[Product] = []
    for p, last_scan in rows.all():
        if last_scan is None or last_scan < cutoff:
            eligible.append(p)
    return eligible

async def _begin_scan(session: AsyncSession, robot: Robot, x: int, y: int) -> None:
    """Запустить 5-секундное сканирование текущей клетки."""
    robot.status = "scanning"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)  # логируем старт скана
    with _LOCK_SCAN:
        _SCANNING_TARGET[robot.id] = (x, y)
        _SCANNING_UNTIL[robot.id] = datetime.now(timezone.utc) + SCAN_DURATION

    # событие позиции со статусом scanning (если включено одиночное)
    if EMIT_POSITION_PER_ROBOT:
        EVENTS.sync_q.put({
            "type": "robot.position",
            "warehouse_id": robot.warehouse_id,
            "robot_id": robot.id,
            "x": x,
            "y": y,
            "shelf": shelf_num_to_str(y),
            "battery_level": round(float(robot.battery_level or 0.0), 1),
            "status": robot.status,
        })

async def _finish_scan(session: AsyncSession, robot: Robot) -> None:
    """Завершить сканирование: записать результаты и вернуть статус idle. Освобождаем цель здесь!"""
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

    # фильтруем по кулдауну повторного сканирования
    if products:
        cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
        last_scan_sq = (
            select(
                InventoryHistory.product_id.label("pid"),
                func.max(InventoryHistory.created_at).label("last_scan"),
            )
            .where(InventoryHistory.warehouse_id == robot.warehouse_id)
            .group_by(InventoryHistory.product_id)
            .subquery()
        )
        q = (
            select(Product.id, last_scan_sq.c.last_scan)
            .outerjoin(last_scan_sq, last_scan_sq.c.pid == Product.id)
            .where(Product.id.in_([p.id for p in products]))
        )
        rows = await session.execute(q)
        allowed_ids = {
            pid for pid, last_scan in rows.all()
            if last_scan is None or last_scan < cutoff
        }
        products = [p for p in products if p.id in allowed_ids]

    if not products:
        # никто не проходит по кулдауну — просто завершаем скан
        with _LOCK_TARGETS:
            _CLAIMED_TARGETS.discard((rx, ry))
        robot.status = "idle"
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)  # фиксируем idle этого тика
        return

    payload_products: List[dict] = []
    history_rows: List[InventoryHistory] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for p in products:
        stock = int(p.stock or 0)
        status = "ok"
        if p.min_stock and stock < p.min_stock:
            status = "critical"
        elif p.optimal_stock and stock < p.optimal_stock:
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

    EVENTS.sync_q.put({
        "type": "product.scan",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": rx,
        "y": ry,
        "shelf": shelf_letter,
        "products": payload_products,
    })

    # освобождаем «застолблённую» цель только после завершения скана
    with _LOCK_TARGETS:
        _CLAIMED_TARGETS.discard((rx, ry))

    # статус -> idle (в БД), логируем этот тик
    robot.status = "idle"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)

# =========================
# Энергия
# =========================
def _drop_per_step_for_field(max_x: int, max_y: int) -> float:
    """
    Дробный расход: чтобы 100% хватало минимум на кратчайший «проход поля»:
    (0,0) -> (max_x, max_y) = max_x + max_y шагов.
    """
    steps_for_pass = max(1, max_x + max_y)
    drop = 100.0 / steps_for_pass
    return max(MIN_BATT_DROP_PER_STEP, drop)

def _consume_battery(robot: Robot, drop_per_step: float) -> None:
    lvl = float(robot.battery_level or 0.0)
    robot.battery_level = max(0.0, lvl - drop_per_step)

# =========================
# Цели (без конфликтов) + потокобезопасность
# =========================
def _free_claim(target: Tuple[int, int]) -> None:
    with _LOCK_TARGETS:
        _CLAIMED_TARGETS.discard(target)

def _claim(target: Tuple[int, int]) -> None:
    with _LOCK_TARGETS:
        _CLAIMED_TARGETS.add(target)

def _is_claimed(target: Tuple[int, int]) -> bool:
    with _LOCK_TARGETS:
        return target in _CLAIMED_TARGETS

def _pick_goal(
    start: Tuple[int, int],
    candidates: List[Tuple[int, int]],
    max_x: int,
    max_y: int,
) -> Tuple[int, int]:
    """Ближайшая свободная клетка с товарами; иначе — случайная свободная клетка."""
    if candidates:
        best_d = None
        bucket: List[Tuple[int, int]] = []
        with _LOCK_TARGETS:
            for c in candidates:
                if c in _CLAIMED_TARGETS:
                    continue
                d = _manhattan(start, c)
                if best_d is None or d < best_d:
                    best_d, bucket = d, [c]
                elif d == best_d:
                    bucket.append(c)
            if bucket:
                goal = random.choice(bucket)
                _CLAIMED_TARGETS.add(goal)
                return goal

    for _ in range(50):
        gx = random.randint(0, max_x)
        gy = random.randint(1, max_y)  # товары только на 1..max_y
        goal = (gx, gy)
        with _LOCK_TARGETS:
            if goal != start and goal not in _CLAIMED_TARGETS:
                _CLAIMED_TARGETS.add(goal)
                return goal

    return start

# =========================
# Один тик робота (реализация на предоставленном session)
# =========================
async def _move_robot_once_impl(session: AsyncSession, robot_id: str, interval: float) -> None:
    result = await session.execute(
        select(Robot).where(Robot.id == robot_id).options(selectinload(Robot.warehouse))
    )
    robot = result.scalar_one_or_none()
    if not robot:
        return

    # Инициализация аккумулятора для уже-заряжающихся роботов (после рестарта вотчера)
    if (robot.status or "").lower() == "charging" and robot.id not in _CHARGE_ACCUM:
        _CHARGE_ACCUM[robot.id] = 0.0

    wh = robot.warehouse
    max_x = max(0, (wh.row_x or 1) - 1)
    max_y = max(1, min((wh.row_y or 1), 26))
    drop_per_step = _drop_per_step_for_field(max_x, max_y)

    # 0) если идёт сканирование — логируем каждый тик, обновляем last_update, проверяем окончание
    with _LOCK_SCAN:
        scanning_until = _SCANNING_UNTIL.get(robot.id)
    if (robot.status or "").lower() == "scanning":
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)  # лог этого тика
        if scanning_until and datetime.now(timezone.utc) >= scanning_until:
            await _finish_scan(session, robot)
        return

    # 1) режим зарядки — стоим на (0,0), пополняем заряд через аккумулятор дробных шагов
    if (robot.status or "").lower() == "charging":
        robot.current_row, robot.current_shelf = DOCK_X, DOCK_Y  # ровно (0,0)

        # шаг (доля %) за этот тик
        charge_step = 100.0 * interval / CHARGE_DURATION.total_seconds()
        acc = _CHARGE_ACCUM.get(robot.id, 0.0) + charge_step

        # целые проценты, которые можно прибавить в БД
        inc = int(acc // 1.0)
        if inc > 0:
            acc -= inc
            current_lvl = float(robot.battery_level or 0.0)
            robot.battery_level = min(100.0, current_lvl + inc)

        _CHARGE_ACCUM[robot.id] = acc

        # обновляем last_update и лог этого тика зарядки
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)

        # окончание зарядки
        if float(robot.battery_level or 0.0) >= 100.0:
            robot.status = "idle"
            _touch_robot(robot)
            await _log_status_every_tick(session, robot)
            _CHARGE_ACCUM.pop(robot.id, None)

        if EMIT_POSITION_PER_ROBOT:
            EVENTS.sync_q.put({
                "type": "robot.position",
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": robot.current_row,
                "y": robot.current_shelf,
                "shelf": shelf_num_to_str(int(robot.current_shelf or 0)),
                "battery_level": round(float(robot.battery_level or 0.0), 1),
                "status": robot.status,
            })
        return

    # 2) выбор/уточнение цели
    cur = (int(robot.current_row or 0), int(robot.current_shelf or 0))
    with _LOCK_TARGETS:
        goal = _TARGETS.get(robot.id)
    if goal is None or goal == cur:
        if goal:
            _free_claim(goal)
        cells = await _product_cells(session, robot.warehouse_id)
        goal = _pick_goal(cur, cells, max_x, max_y)
        with _LOCK_TARGETS:
            _TARGETS[robot.id] = goal

    # 3) двигаемся на ОДНУ клетку за тик
    step = _next_step_towards(cur, goal)
    nx = _bounded(step[0], 0, max_x)
    ny = _bounded(step[1], 0, max_y)  # 0 допустим только для дока

    # списываем энергию
    _consume_battery(robot, drop_per_step)

    # если энергия 0 — сразу в док (0,0) и charging
    if float(robot.battery_level or 0.0) <= 0.0:
        robot.current_row, robot.current_shelf = DOCK_X, DOCK_Y
        robot.status = "charging"
        _CHARGE_ACCUM[robot.id] = 0.0  # сбрасываем аккумулятор при входе в зарядку
        _touch_robot(robot)
        await _log_status_every_tick(session, robot)  # лог входа в зарядку (этот тик)
        if EMIT_POSITION_PER_ROBOT:
            EVENTS.sync_q.put({
                "type": "robot.position",
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": robot.current_row,
                "y": robot.current_shelf,
                "shelf": shelf_num_to_str(int(robot.current_shelf or 0)),
                "battery_level": round(float(robot.battery_level or 0.0), 1),
                "status": robot.status,
            })
        # освобождаем цель (она более не актуальна)
        _free_claim(goal)
        with _LOCK_TARGETS:
            _TARGETS.pop(robot.id, None)
        return

    # применяем новое положение
    robot.current_row, robot.current_shelf, robot.status = nx, ny, "idle"
    _touch_robot(robot)
    await _log_status_every_tick(session, robot)  # лог этого тика движения

    if EMIT_POSITION_PER_ROBOT:
        EVENTS.sync_q.put({
            "type": "robot.position",
            "warehouse_id": robot.warehouse_id,
            "robot_id": robot.id,
            "x": nx,
            "y": ny,
            "shelf": shelf_num_to_str(ny),
            "battery_level": round(float(robot.battery_level or 0.0), 1),
            "status": robot.status,
        })

    # если дошли до цели — проверяем кулдаун и либо сканируем, либо пропускаем
    if (nx, ny) == goal:
        cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
        eligible = await _eligible_products_for_scan(session, robot.warehouse_id, nx, ny, cutoff)
        if not eligible:
            # нечего сканировать — освобождаем цель, лог уже сделан выше (idle этого тика)
            _free_claim(goal)
            with _LOCK_TARGETS:
                _TARGETS.pop(robot.id, None)
        else:
            await _begin_scan(session, robot, nx, ny)
            with _LOCK_TARGETS:
                _TARGETS.pop(robot.id, None)

# =========================
# Один тик робота (функция для потока)
# =========================
def _run_robot_once_threadsafe(
    robot_id: str,
    interval: float
) -> None:
    """
    Запуск одного тика робота в отдельном потоке со своим event loop и СВОИМ async engine/session.
    Ничего «глобального» из главного лупа сюда не передаём.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)

        async def runner():
            session_factory, engine = _thread_local_session_factory()
            try:
                async with session_factory() as session:
                    async with session.begin():
                        await _move_robot_once_impl(session, robot_id, interval)
            finally:
                await engine.dispose()

        loop.run_until_complete(runner())
    except Exception as e:
        print(f"⚠️ Ошибка в потоке робота {robot_id}: {e}", flush=True)
    finally:
        try:
            loop.close()
        except Exception:
            pass

# =========================
# Один тик СКЛАДА (функция для отдельного потока)
# =========================
def _run_warehouse_once_threadsafe(
    warehouse_id: str,
    interval: float,
    max_robot_workers: int
) -> None:
    """
    Выполнить один тик для ОДНОГО склада в отдельном потоке:
      - свой event loop
      - свой async engine/session (для чтения списка роботов)
      - внутри склада роботы параллелятся собственными потоками (_run_robot_once_threadsafe)
      - ПОСЛЕ — шлём один батч robot.position для склада (если включено)
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)

        async def runner():
            # локальный engine/session для ЭТОГО ПОТОКА (склада)
            session_factory, engine = _thread_local_session_factory()
            try:
                # читаем роботов этого склада
                async with session_factory() as session:
                    result = await session.execute(
                        select(Robot.id).where(Robot.warehouse_id == warehouse_id)
                    )
                    robot_ids = list(result.scalars().all())

                if not robot_ids:
                    return

                # запустим роботов ПАРАЛЛЕЛЬНО в потоках (как и прежде)
                current_loop = asyncio.get_running_loop()
                with ThreadPoolExecutor(max_workers=max_robot_workers) as executor:
                    tasks = [
                        current_loop.run_in_executor(
                            executor, _run_robot_once_threadsafe, rid, interval
                        )
                        for rid in robot_ids
                    ]
                    await asyncio.gather(*tasks)

                # === Батч позиций по складу ===
                if EMIT_POSITION_BATCH:
                    session_factory2, engine2 = _thread_local_session_factory()
                    try:
                        async with session_factory2() as session2:
                            result = await session2.execute(
                                select(Robot).where(Robot.warehouse_id == warehouse_id)
                            )
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

                        EVENTS.sync_q.put({
                            "type": "robot.position",
                            "warehouse_id": warehouse_id,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "robots": batch,
                        })
                    finally:
                        await engine2.dispose()

            finally:
                await engine.dispose()

        loop.run_until_complete(runner())
    except Exception as e:
        print(f"⚠️ Ошибка в потоке склада {warehouse_id}: {e}", flush=True)
    finally:
        try:
            loop.close()
        except Exception:
            pass

# =========================
# Вотчер: ПАРАЛЛЕЛЬНО по складам (потоки), и внутри склада — тоже потоки по роботам
# =========================
async def run_robot_watcher(
    interval: float = 2,
    max_robot_workers: int = 20,
    max_warehouse_workers: int = 4,
) -> None:
    """
    Основной цикл:
      - СКЛАДЫ: по-настоящему ПАРАЛЛЕЛЬНО (каждый склад в отдельном потоке, свой loop/engine)
      - ВНУТРИ СКЛАДА: роботы ПАРАЛЛЕЛЬНО (потоки, свой loop/engine у каждого робота)
      - скан — 5 секунд; зарядка — 15 минут; (0,0); анти-повтор скана 5 минут
      - WebSocket: только robot.position (батч или одиночные) и product.scan
      - RobotHistory пишется КАЖДЫЙ ТИК; last_update обновляется КАЖДЫЙ ТИК
      - Зарядка безопасна для целочисленного battery_level (через _CHARGE_ACCUM)
    """
    print("🚀 Robot watcher started.", flush=True)
    try:
        while True:
            # список складов читаем в главном лупе через главный sessionmaker
            session_factory_main = _session_factory_main()
            async with session_factory_main() as session:
                result = await session.execute(
                    select(Warehouse).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
                )
                warehouses = list(result.scalars().all())

            if not warehouses:
                print("⌛ Нет роботов — ждём появления...", flush=True)
            else:
                loop = asyncio.get_running_loop()
                # ПАРАЛЛЕЛИМ СКЛАДЫ: по потоку на склад
                with ThreadPoolExecutor(max_workers=max_warehouse_workers) as executor:
                    tasks = [
                        loop.run_in_executor(
                            executor,
                            _run_warehouse_once_threadsafe,
                            wh.id,
                            interval,
                            max_robot_workers,
                        )
                        for wh in warehouses
                    ]
                    await asyncio.gather(*tasks)

                # опционально: лог по результатам
                print(
                    "✅ Обработаны склады: "
                    + ", ".join(f"{wh.name} ({wh.id})" for wh in warehouses),
                    flush=True,
                )

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("\n🛑 Robot watcher stopped.", flush=True)
