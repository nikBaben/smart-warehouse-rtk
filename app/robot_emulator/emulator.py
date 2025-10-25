# app/services/robot_mover.py
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.ws.ws_manager import EVENTS
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from app.models.product import Product
from app.models.inventory_history import InventoryHistory
from app.service.robot_history import write_robot_status_event  # ✅ добавлено

# =========================
# Параметры зарядки/сканирования
# =========================
CHARGE_DURATION = timedelta(seconds=60)
SCAN_DURATION = timedelta(seconds=10)
DOCK_ROW = 0
DOCK_SHELF_STR = "A"
STALE_AGE = timedelta(minutes=5)

# =========================
# Состояние в памяти процесса
# =========================
_TARGETS: Dict[str, Tuple[int, int]] = {}
_BATT_ACCUM: Dict[str, float] = {}
_CHARGING_UNTIL: Dict[str, datetime] = {}
_SCANNING_UNTIL: Dict[str, datetime] = {}
_SCANNING_TARGET: Dict[str, Tuple[int, int]] = {}

# =========================
# Утилиты для полок
# ========================= 
def shelf_str_to_num(s: Optional[str]) -> int:
    if not s:
        return 1
    c = s.strip().upper()[:1]
    return (ord(c) - ord("A")) + 1 if "A" <= c <= "Z" else 1

def shelf_num_to_str(n: int) -> str:
    n = max(1, min(26, int(n or 1)))
    return chr(ord("A") + (n - 1))

DOCK_SHELF_NUM = shelf_str_to_num(DOCK_SHELF_STR)

# =========================
# Фабрика сессий
# =========================
def _make_session_factory() -> tuple[async_sessionmaker[AsyncSession], any]:
    engine = create_async_engine(settings.DB_URL, echo=False, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return factory, engine

# =========================
# Общие утилиты
# =========================
def _bounded(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def _next_step_towards(start: Tuple[int, int], goal: Tuple[int, int]) -> Tuple[int, int]:
    sx, sy = start
    gx, gy = goal
    dx, dy = gx - sx, gy - sy
    if dx == 0 and dy == 0:
        return start
    choices: List[Tuple[int, int]] = []
    if dx != 0:
        choices.append((sx + (1 if dx > 0 else -1), sy))
    if dy != 0:
        choices.append((sx, sy + (1 if dy > 0 else -1)))
    return random.choice(choices)

# =========================
# Помощники по складу
# =========================
async def _fetch_stale_product_cells(
    session: AsyncSession,
    warehouse_id: str,
    max_x: int,
    max_y_num: int,
    older_than: datetime,
) -> List[Tuple[int, int]]:
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
        select(
            Product.current_row,
            Product.current_shelf,
            last_scan_sq.c.last_scan,
        )
        .outerjoin(last_scan_sq, last_scan_sq.c.pid == Product.id)
        .where(
            Product.warehouse_id == warehouse_id,
            or_(
                last_scan_sq.c.last_scan.is_(None),
                last_scan_sq.c.last_scan < older_than,
            ),
        )
    )

    rows = await session.execute(q)
    cells: List[Tuple[int, int]] = []
    for r, shelf_str, _last in rows.all():
        y_num = shelf_str_to_num(shelf_str)
        x = int(r or 0)
        if 0 <= x <= max_x and 1 <= y_num <= max_y_num:
            cells.append((x, y_num))
    return cells

def _choose_goal_from_products(
    start: Tuple[int, int],
    product_cells: List[Tuple[int, int]],
) -> Tuple[int, int] | None:
    if not product_cells:
        return None
    sx, sy = start
    best_d: Optional[int] = None
    bucket: List[Tuple[int, int]] = []
    for (x, y) in product_cells:
        d = abs(x - sx) + abs(y - sy)
        if best_d is None or d < best_d:
            best_d, bucket = d, [(x, y)]
        elif d == best_d:
            bucket.append((x, y))
    return random.choice(bucket) if bucket else None

# =========================
# Зарядка и батарея
# =========================
def _battery_drop_per_step(row_x: int, row_y: int) -> float:
    rx, ry = max(1, int(row_x or 1)), max(1, int(row_y or 1))
    return 100.0 / (rx * ry)

def _consume_battery(robot: Robot, row_x: int, row_y: int) -> None:
    acc = _BATT_ACCUM.get(robot.id, 0.0) + _battery_drop_per_step(row_x, row_y)
    drop = int(acc // 1.0)
    if drop > 0:
        robot.battery_level = max(0, (robot.battery_level or 0) - drop)
        acc -= drop
    _BATT_ACCUM[robot.id] = acc

async def _begin_charging(robot: Robot, session: AsyncSession) -> None:
    robot.current_row = DOCK_ROW
    robot.current_shelf = DOCK_SHELF_NUM
    robot.status = "charging"
    await write_robot_status_event(session, robot.id)
    until = datetime.now(timezone.utc) + CHARGE_DURATION
    _CHARGING_UNTIL[robot.id] = until
    EVENTS.sync_q.put({
        "type": "robot.charging",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": robot.current_row,
        "y": robot.current_shelf,
        "shelf": shelf_num_to_str(robot.current_shelf),
        "battery_level": robot.battery_level or 0,
        "status": robot.status,
        "charging_until": until.isoformat(),
    })
    print(f"⚡ Robot {robot.id} docked — charging until {until.isoformat()}", flush=True)

async def _maybe_finish_charging(robot: Robot, session: AsyncSession) -> bool:
    if robot.status == "charging":
        until = _CHARGING_UNTIL.get(robot.id)
        now = datetime.now(timezone.utc)
        if until and now >= until:
            robot.battery_level = 100
            robot.status = "idle"
            await write_robot_status_event(session, robot.id)
            _BATT_ACCUM[robot.id] = 0.0
            _CHARGING_UNTIL.pop(robot.id, None)
            EVENTS.sync_q.put({
                "type": "robot.charged",
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "battery_level": robot.battery_level,
                "status": robot.status,
            })
            print(f"🔋 Robot {robot.id} finished charging", flush=True)
            return True
    return False

# =========================
# Сканирование
# =========================
async def _cell_has_products(session: AsyncSession, warehouse_id: str, x: int, y_num: int) -> bool:
    shelf_letter = shelf_num_to_str(y_num)
    res = await session.execute(
        select(Product.id).where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            Product.current_shelf == shelf_letter,
        ).limit(1)
    )
    return res.scalar_one_or_none() is not None

async def _begin_scanning(robot: Robot, x: int, y_num: int, session: AsyncSession) -> None:
    robot.status = "scanning"
    await write_robot_status_event(session, robot.id)
    until = datetime.now(timezone.utc) + SCAN_DURATION
    _SCANNING_UNTIL[robot.id] = until
    _SCANNING_TARGET[robot.id] = (x, y_num)
    EVENTS.sync_q.put({
        "type": "robot.scanning_start",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": x,
        "y": y_num,
        "shelf": shelf_num_to_str(y_num),
        "battery_level": robot.battery_level or 0,
        "status": robot.status,
        "scanning_until": until.isoformat(),
    })
    print(f"📡 Robot {robot.id} scanning START at ({x},{shelf_num_to_str(y_num)})", flush=True)

async def _maybe_finish_scanning(robot: Robot, session: AsyncSession) -> bool:
    if robot.status != "scanning":
        return False
    until = _SCANNING_UNTIL.get(robot.id)
    now = datetime.now(timezone.utc)
    if until and now >= until:
        rx, ry = _SCANNING_TARGET.get(robot.id, (robot.current_row, robot.current_shelf))
        shelf_letter = shelf_num_to_str(ry)
        _SCANNING_UNTIL.pop(robot.id, None)
        _SCANNING_TARGET.pop(robot.id, None)
        robot.status = "idle"
        await write_robot_status_event(session, robot.id)

        result = await session.execute(
            select(Product).where(
                Product.warehouse_id == robot.warehouse_id,
                Product.current_row == rx,
                Product.current_shelf == shelf_letter,
            )
        )
        products = list(result.scalars().all())
        if not products:
            return True

        history_rows, payload_products = [], []
        for p in products:
            current_stock = int(p.stock or 0)
            status = "critical" if p.min_stock and current_stock < p.min_stock else (
                "low" if p.optimal_stock and current_stock < p.optimal_stock else "ok"
            )
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
                    stock=current_stock,
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
                "stock": current_stock,
                "status": status,
            })

        session.add_all(history_rows)
        await session.flush()

        EVENTS.sync_q.put({
            "type": "robot.scanned_end",
            "warehouse_id": robot.warehouse_id,
            "robot_id": robot.id,
            "x": rx,
            "y": ry,
            "shelf": shelf_letter,
            "status": robot.status,
        })
        EVENTS.sync_q.put({
            "type": "product.scan",
            "warehouse_id": robot.warehouse_id,
            "robot_id": robot.id,
            "x": rx,
            "y": ry,
            "shelf": shelf_letter,
            "products": payload_products,
        })
        print(f"✅ Robot {robot.id} SCAN DONE — записано {len(products)} товаров", flush=True)
        return True
    return False

# =========================
# Один тик робота
# =========================
async def _move_robot_once(robot_id: str) -> str:
    session_factory, engine = _make_session_factory()
    try:
        async with session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(Robot).where(Robot.id == robot_id).options(selectinload(Robot.warehouse))
                )
                robot = result.scalar_one_or_none()
                if not robot:
                    return robot_id

                wh = robot.warehouse
                max_x, max_y_num = max(0, (wh.row_x or 1) - 1), max(1, min((wh.row_y or 1), 26))

                await _maybe_finish_charging(robot, session)
                await session.flush()

                if robot.status == "charging":
                    return robot_id

                await _maybe_finish_scanning(robot, session)
                await session.flush()
                if robot.status == "scanning":
                    return robot_id

                start_x, start_y_num = robot.current_row, int(robot.current_shelf or 1)
                start = (start_x, start_y_num)

                older_than = datetime.now(timezone.utc) - STALE_AGE
                stale_cells = await _fetch_stale_product_cells(
                    session, robot.warehouse_id, max_x, max_y_num, older_than
                )

                goal = _choose_goal_from_products(start, stale_cells)
                if goal is None:
                    gx = random.randint(0, max_x)
                    gy = random.randint(1, max_y_num)
                    if (gx, gy) == start:
                        gy = 1 if gy != 1 else max_y_num
                    goal = (gx, gy)

                _TARGETS[robot.id] = goal

                step_x, step_y_num = _next_step_towards(start, goal)
                next_x = _bounded(step_x, 0, max_x)
                next_y_num = _bounded(step_y_num, 1, max_y_num)

                _consume_battery(robot, wh.row_x or 1, wh.row_y or 1)

                robot.current_row, robot.current_shelf, robot.status = next_x, next_y_num, "idle"
                await write_robot_status_event(session, robot.id)
                await session.flush()

                EVENTS.sync_q.put({
                    "type": "robot.position",
                    "warehouse_id": robot.warehouse_id,
                    "robot_id": robot.id,
                    "x": next_x,
                    "y": next_y_num,
                    "shelf": shelf_num_to_str(next_y_num),
                    "battery_level": robot.battery_level or 0,
                    "status": robot.status,
                })

            async with session.begin():
                if robot.status not in ("charging", "scanning"):
                    cur_y_num = int(robot.current_shelf or 1)
                    if await _cell_has_products(session, robot.warehouse_id, robot.current_row, cur_y_num):
                        await _begin_scanning(robot, robot.current_row, cur_y_num, session)
                        await session.flush()
        return robot_id
    finally:
        await engine.dispose()

# =========================
# ThreadPoolExecutor
# =========================
def _run_in_thread(robot_id: str) -> str:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_move_robot_once(robot_id))
    except Exception as e:
        print(f"⚠️ Ошибка в потоке робота {robot_id}: {e}", flush=True)
        return robot_id
    finally:
        loop.close()

async def move_all_robots_concurrently(
    warehouse_id: str,
    global_session_factory: async_sessionmaker[AsyncSession],
    *,
    max_workers: int = 8
) -> List[str]:
    async with global_session_factory() as session:
        result = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
        robot_ids = list(result.scalars().all())
    if not robot_ids:
        return []
    loop = asyncio.get_running_loop()
    done_ids: List[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [loop.run_in_executor(executor, _run_in_thread, rid) for rid in robot_ids]
        for coro in asyncio.as_completed(tasks):
            try:
                done_ids.append(await coro)
            except Exception as e:
                print(f"⚠️ Ошибка при движении одного из роботов: {e}", flush=True)
    return done_ids

# =========================
# Вотчер
# =========================
async def run_robot_watcher(interval: float = 5.0, max_workers: int = 8) -> None:
    from app.db.session import async_session as app_sessionmaker
    print("🚀 [async] Robot watcher started.", flush=True)
    try:
        while True:
            async with app_sessionmaker() as session:
                result = await session.execute(
                    select(Warehouse).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
                )
                warehouses = list(result.scalars().all())
            if not warehouses:
                print("⌛ Нет роботов — ждём появления...", flush=True)
            else:
                for wh in warehouses:
                    moved = await move_all_robots_concurrently(wh.id, app_sessionmaker, max_workers=max_workers)
                    if moved:
                        print(f"✅ Склад {wh.name} ({wh.id}) — перемещены роботы: {moved}", flush=True)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("\n🛑 Robot watcher stopped.", flush=True)
