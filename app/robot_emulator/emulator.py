from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.ws.ws_manager import EVENTS  # janus queue: для WS-событий
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from app.models.product import Product  
from app.models.inventory_history import InventoryHistory 


_TARGETS: Dict[str, Tuple[int, int]] = {}  # robot_id -> (goal_x, goal_y)

#Создаёт async_engine + async_sessionmaker.
#Вызывается внутри потока (см. _run_in_thread), у каждого потока свой event loop.
def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.DB_URL, echo=False, future=True)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

def _bounded(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

#Случайная новая цель, не равная текущей позиции.
def _pick_new_goal(max_x: int, max_y: int, start: Tuple[int, int]) -> Tuple[int, int]:
    while True:
        gx = random.randint(0, max_x)
        gy = random.randint(0, max_y)
        if (gx, gy) != start:
            return gx, gy

#Делает ОДИН шаг по кратчайшему манхэттенскому пути:
#- если нужно и по X, и по Y — выбираем ось случайно (живее траектория);
#- если по одной оси — двигаемся по ней.
def _next_step_towards(start: Tuple[int, int], goal: Tuple[int, int]) -> Tuple[int, int]:
    sx, sy = start
    gx, gy = goal
    dx = gx - sx
    dy = gy - sy

    if dx == 0 and dy == 0:
        return start

    choices: List[Tuple[int, int]] = []
    if dx != 0:
        choices.append((sx + (1 if dx > 0 else -1), sy))
    if dy != 0:
        choices.append((sx, sy + (1 if dy > 0 else -1)))
    return random.choice(choices)

async def _scan_cell_for_products_and_log(
    session: AsyncSession,
    warehouse_id: str,
    x: int,
    y: int,
    robot_id: str,
) -> None:
    
    #Если на клетке (x,y) есть товары:
    #  1) пишет записи в InventoryHistory (одна на каждый товар на клетке)
    #  2) публикует WS-событие product.scan (батчом)
    #  3) печатает диагностический лог
    result = await session.execute(
        select(Product).where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            Product.current_shelf == y,
        )
    )
    products = list(result.scalars().all())
    if not products:
        print(f"🟦 [SCAN] No products at ({x},{y}) in warehouse {warehouse_id} by robot {robot_id}")
        return

    now = datetime.now(timezone.utc).isoformat()
    history_rows: List[InventoryHistory] = []
    for p in products:
        history_rows.append(
            InventoryHistory(
                id=str(uuid.uuid4()),
                product_id=p.id,
                robot_id=robot_id,
                warehouse_id=warehouse_id,
                current_zone=getattr(p, "current_zone", None),
                current_row=getattr(p, "current_row", x),
                current_shelf=getattr(p, "current_shelf", y),
                name=p.name,
                category=p.category,
                min_stock=p.min_stock,
                optimal_stock=p.optimal_stock,
            )
        )
    session.add_all(history_rows)

    # гарантируем, что записи готовы до отправки WS-события
    await session.flush()

    print(
        f"🔎 [SCAN] Robot {robot_id} scanned {len(products)} product(s) at ({x},{y}) "
        f"in warehouse {warehouse_id}: {[p.id for p in products]}"
    )

    EVENTS.sync_q.put({
        "type": "product.scan",
        "ts": now,
        "warehouse_id": warehouse_id,
        "robot_id": robot_id,
        "x": x,
        "y": y,
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "current_zone": getattr(p, "current_zone", None),
                "current_row": getattr(p, "current_row", x),
                "current_shelf": getattr(p, "current_shelf", y),
                "min_stock": p.min_stock,
                "optimal_stock": p.optimal_stock,
            }
            for p in products
        ],
    })

#Шаг робота:
# 1) загрузка робота + склада
# 2) цель из памяти (или назначение новой)
# 3) один шаг по манхэттену
# 4) фиксация координат + событие robot.position
# 5) ВТОРАЯ ТРАНЗАКЦИЯ в той же сессии: скан + запись истории + событие product.scan
async def _move_robot_once(robot_id: str) -> str:
    session_factory = _make_session_factory()

    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(Robot)
                .where(Robot.id == robot_id)
                .options(selectinload(Robot.warehouse))
            )
            robot: Robot | None = result.scalar_one_or_none()
            if not robot:
                return robot_id

            warehouse: Warehouse = robot.warehouse
            max_x = max(warehouse.row_x - 1, 0)
            max_y = max(warehouse.row_y - 1, 0)

            start = (robot.current_row, robot.current_shelf)

            goal = _TARGETS.get(robot.id)
            if (
                goal is None
                or not (0 <= goal[0] <= max_x and 0 <= goal[1] <= max_y)
                or goal == start
            ):
                goal = _pick_new_goal(max_x, max_y, start)
                _TARGETS[robot.id] = goal

            next_x, next_y = _next_step_towards(start, goal)
            next_x = _bounded(next_x, 0, max_x)
            next_y = _bounded(next_y, 0, max_y)

            robot.current_row, robot.current_shelf = next_x, next_y

            if (next_x, next_y) == goal:
                _TARGETS[robot.id] = _pick_new_goal(max_x, max_y, (next_x, next_y))

            print(
                f"🤖 [Warehouse {warehouse.id}] Robot {robot.id} "
                f"{start} → ({next_x}, {next_y})  goal={goal}"
            )
            EVENTS.sync_q.put({
                "type": "robot.position",
                "ts": datetime.now(timezone.utc).isoformat(),
                "warehouse_id": warehouse.id,
                "robot_id": robot.id,
                "x": next_x,
                "y": next_y,
            })

        async with session.begin():
            await _scan_cell_for_products_and_log(
                session,
                warehouse_id=warehouse.id,
                x=robot.current_row,
                y=robot.current_shelf,
                robot_id=robot.id,
            )

    return robot_id

# Запуск одного шага робота в отдельном потоке (с собственным event loop).
def _run_in_thread(robot_id: str) -> str:
    return asyncio.run(_move_robot_once(robot_id))

async def move_all_robots_concurrently(
    warehouse_id: str,
    global_session_factory: async_sessionmaker[AsyncSession],
    *,
    max_workers: int = 8,
) -> List[str]:
    
    #Параллельно двигает всех роботов склада (каждый шаг — в отдельном потоке).
    async with global_session_factory() as session:
        result = await session.execute(
            select(Robot.id).where(Robot.warehouse_id == warehouse_id)
        )
        robot_ids = list(result.scalars().all())

    if not robot_ids:
        return []

    done_ids: List[str] = []
    loop = asyncio.get_running_loop()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [loop.run_in_executor(executor, _run_in_thread, rid) for rid in robot_ids]
        for coro in asyncio.as_completed(tasks):
            try:
                rid = await coro
                done_ids.append(rid)
            except Exception as e:
                print(f"⚠️ Ошибка при движении одного из роботов: {e}")

    return done_ids

# Цикл:
#   - ищет склады с роботами
#   - двигает роботов на один шаг (параллельно)
#   - ждёт interval и повторяет
async def run_robot_watcher(interval: float = 5.0, max_workers: int = 8) -> None:
    from app.db.session import async_session  # общая фабрика для "списка"

    print("🚀 [async] Robot watcher started. (multi-thread mode, straight path + scan + WS + history)")
    try:
        while True:
            async with async_session() as session:
                result = await session.execute(
                    select(Warehouse)
                    .join(Robot, Robot.warehouse_id == Warehouse.id)
                    .distinct()
                )
                warehouses = list(result.scalars().all())

            if not warehouses:
                print("⌛ Роботов нет — ждем появления...")
            else:
                for wh in warehouses:
                    moved = await move_all_robots_concurrently(
                        wh.id, async_session, max_workers=max_workers
                    )
                    if moved:
                        print(f"✅ Склад {wh.name} ({wh.id}) — перемещены роботы: {moved}")

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        print("\n🛑 Robot watcher stopped.")
