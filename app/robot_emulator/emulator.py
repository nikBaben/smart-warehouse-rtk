# app/services/robot_mover.py
from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone, timedelta
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


# Параметры зарядки/сканирования
CHARGE_DURATION = timedelta(seconds=60)
SCAN_DURATION = timedelta(seconds=10)
DOCK_ROW = 0           # строка док-станции
DOCK_SHELF_STR = "A"   # полка док-станции (как буква)

# Состояние в памяти процесса
_TARGETS: Dict[str, Tuple[int, int]] = {}         # robot_id -> (goal_x, goal_y_num)  (y: 1..26)
_BATT_ACCUM: Dict[str, float] = {}                # robot_id -> накопленная дробная "стоимость" шагов
_CHARGING_UNTIL: Dict[str, datetime] = {}         # robot_id -> конец зарядки (UTC)
_SCANNING_UNTIL: Dict[str, datetime] = {}         # robot_id -> конец сканирования (UTC)
_SCANNING_TARGET: Dict[str, Tuple[int, int]] = {} # robot_id -> (x, y_num) клетка, которую сканируем


# Вспомогательные конвертеры полок
def shelf_str_to_num(s: str | None) -> int:
    #'A'->1, 'B'->2, ... 'Z'->26. Некорректные -> 1.
    if not s:
        return 1
    c = s.strip().upper()[:1]
    if "A" <= c <= "Z":
        return (ord(c) - ord("A")) + 1
    return 1

#1->'A', ..., 26->'Z'. Вне диапазона прижимаем к [1..26].
def shelf_num_to_str(n: int) -> str:
    n = max(1, min(26, int(n or 1)))
    return chr(ord("A") + (n - 1))

# Фабрика сессий
def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.DB_URL, echo=False, future=True)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Утилиты движения
def _bounded(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

#Случайная новая цель (x: 0..max_x, y_num: 1..max_y_num), не равная текущей позиции.
def _pick_new_goal(max_x: int, max_y_num: int, start: Tuple[int, int]) -> Tuple[int, int]:
    while True:
        gx = random.randint(0, max_x)
        gy = random.randint(1, max_y_num)
        if (gx, gy) != start:
            return gx, gy

#ОДИН шаг по манхэттену; для Y работаем в числах (1..26).
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

# Динамический расход батареи по размерам склада
def _battery_drop_per_step(row_x: int, row_y: int) -> float:
    #На полный проход row_x * row_y шагов тратим 100%.
    rx = max(1, int(row_x or 1))
    ry = max(1, int(row_y or 1))
    steps = rx * ry
    return 100.0 / steps

#Накопительная схема: аккумулируем дробь до целого процента.
def _consume_battery(robot: Robot, row_x: int, row_y: int) -> None:
    acc = _BATT_ACCUM.get(robot.id, 0.0) + _battery_drop_per_step(row_x, row_y)
    drop = int(acc // 1.0)
    if drop > 0:
        new_level = max(0, (robot.battery_level or 0) - drop)
        if new_level != robot.battery_level:
            robot.battery_level = new_level
        acc -= drop
    _BATT_ACCUM[robot.id] = acc

# Зарядка
def _begin_charging(robot: Robot) -> None:
    robot.current_row = DOCK_ROW
    robot.current_shelf = DOCK_SHELF_STR  # буква
    robot.status = "charging"
    until = datetime.now(timezone.utc) + CHARGE_DURATION
    _CHARGING_UNTIL[robot.id] = until

    EVENTS.sync_q.put({
        "type": "robot.dock",
        "ts": datetime.now(timezone.utc).isoformat(),
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": robot.current_row,
        "y": shelf_str_to_num(robot.current_shelf),   
        "shelf": robot.current_shelf,                 
        "battery_level": robot.battery_level or 0,
        "status": robot.status,
        "charging_until": until.isoformat(),
    })
    EVENTS.sync_q.put({
        "type": "robot.charging",
        "ts": datetime.now(timezone.utc).isoformat(),
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": robot.current_row,
        "y": shelf_str_to_num(robot.current_shelf),
        "shelf": robot.current_shelf,
        "battery_level": robot.battery_level or 0,
        "status": robot.status,
        "charging_until": until.isoformat(),
    })

def _maybe_finish_charging(robot: Robot) -> bool:
    if robot.status == "charging":
        until = _CHARGING_UNTIL.get(robot.id)
        now = datetime.now(timezone.utc)
        if until and now >= until:
            robot.battery_level = 100
            robot.status = "idle"
            _BATT_ACCUM[robot.id] = 0.0
            _CHARGING_UNTIL.pop(robot.id, None)
            EVENTS.sync_q.put({
                "type": "robot.charged",
                "ts": now.isoformat(),
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": robot.current_row,
                "y": shelf_str_to_num(robot.current_shelf),
                "shelf": robot.current_shelf,
                "battery_level": robot.battery_level,
                "status": robot.status,
            })
            return True
    return False

# Работа со stock/status при сканировании
def _status_by_stock(stock: int, min_stock: int | None, optimal_stock: int | None) -> str:
    m = min_stock if isinstance(min_stock, int) else None
    o = optimal_stock if isinstance(optimal_stock, int) else None
    if m is not None and stock < m:
        return "critical"
    if o is not None and stock < o:
        return "low"
    return "ok"

def _recalculate_stock_for_scan(p: Product) -> int:
    """Эмуляция измерения остатка при сканировании."""
    if getattr(p, "stock", None) is None:
        base = p.optimal_stock if isinstance(p.optimal_stock, int) else 0
        return max(0, base)
    delta = random.randint(0, 2)
    return max(0, int(p.stock) - delta)

# Сканирование товаров + запись истории + WS (фактическая операция)
async def _scan_cell_for_products_and_log(
    session: AsyncSession,
    warehouse_id: str,
    x: int,
    y_num: int,       
    robot_id: str,
) -> None:
    shelf_letter = shelf_num_to_str(y_num) 
    result = await session.execute(
        select(Product).where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            Product.current_shelf == shelf_letter,
        )
    )
    products = list(result.scalars().all())
    if not products:
        print(f"🟦 [SCAN] No products at ({x},{shelf_letter}) in warehouse {warehouse_id} by robot {robot_id}")
        return

    now = datetime.now(timezone.utc).isoformat()
    history_rows: List[InventoryHistory] = []
    payload_products: List[dict] = []

    for p in products:
        # 1) обновляем текущий остаток товара (эмуляция инвентаризации)
        new_stock = _recalculate_stock_for_scan(p)
        p.stock = new_stock  # <-- обновление в Product
        # 2) вычисляем статус относительно min/optimal
        st = _status_by_stock(new_stock, p.min_stock, p.optimal_stock)

        # 3) пишем строку в историю (включая stock и status)
        history_rows.append(
            InventoryHistory(
                id=str(uuid.uuid4()),
                product_id=p.id,
                robot_id=robot_id,
                warehouse_id=warehouse_id,
                current_zone=getattr(p, "current_zone", None),
                current_row=getattr(p, "current_row", x),
                current_shelf=shelf_letter,
                name=p.name,
                category=p.category,
                min_stock=p.min_stock,
                optimal_stock=p.optimal_stock,
                stock=new_stock,
                status=st,
            )
        )

        # 4) формируем WS-данные
        payload_products.append({
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "current_zone": getattr(p, "current_zone", None),
            "current_row": getattr(p, "current_row", x),
            "current_shelf": shelf_letter,   # строкой, как в таблице products
            "shelf_num": y_num,              # и числом — удобно для UI/гридов
            "min_stock": p.min_stock,
            "optimal_stock": p.optimal_stock,
            "stock": new_stock,
            "status": st,
        })

    # сохраняем изменения Product.stock и историю
    session.add_all(history_rows)
    await session.flush()

    print(
        f"🔎 [SCAN] Robot {robot_id} scanned {len(products)} product(s) at ({x},{shelf_letter}) "
        f"in warehouse {warehouse_id}: {[p.id for p in products]}"
    )

    # WS: одно событие с батчем товаров и их актуальными остатками/статусами
    EVENTS.sync_q.put({
        "type": "product.scan",
        "ts": now,
        "warehouse_id": warehouse_id,
        "robot_id": robot_id,
        "x": x,
        "y": y_num,
        "shelf": shelf_letter,
        "products": payload_products,
    })

# Сканирование: запуск и завершение
def _begin_scanning(robot: Robot, x: int, y_num: int) -> None:
    #Старт 10-секундного сканирования: статус 'scanning', фиксируем цель клетки (y как число).
    robot.status = "scanning"
    until = datetime.now(timezone.utc) + SCAN_DURATION
    _SCANNING_UNTIL[robot.id] = until
    _SCANNING_TARGET[robot.id] = (x, y_num)

    EVENTS.sync_q.put({
        "type": "robot.scanning_start",
        "ts": datetime.now(timezone.utc).isoformat(),
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": x,
        "y": y_num,
        "shelf": shelf_num_to_str(y_num),
        "battery_level": robot.battery_level or 0,
        "status": robot.status,
        "scanning_until": until.isoformat(),
    })

#Если сканирование завершилось — пишем историю и возвращаем статус 'idle'.
async def _maybe_finish_scanning(robot: Robot, session: AsyncSession) -> bool:
    if robot.status == "scanning":
        until = _SCANNING_UNTIL.get(robot.id)
        now = datetime.now(timezone.utc)
        if until and now >= until:
            tx, ty_num = _SCANNING_TARGET.get(
                robot.id,
                (robot.current_row, shelf_str_to_num(robot.current_shelf))
            )
            await _scan_cell_for_products_and_log(
                session,
                warehouse_id=robot.warehouse_id,
                x=tx,
                y_num=ty_num,
                robot_id=robot.id,
            )
            robot.status = "idle"
            _SCANNING_UNTIL.pop(robot.id, None)
            _SCANNING_TARGET.pop(robot.id, None)

            await session.flush()
            EVENTS.sync_q.put({
                "type": "robot.scanned_end",
                "ts": now.isoformat(),
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": robot.current_row,
                "y": shelf_str_to_num(robot.current_shelf),
                "shelf": robot.current_shelf,
                "battery_level": robot.battery_level or 0,
                "status": robot.status,
            })
            return True
    return False

# Один тик робота
async def _move_robot_once(robot_id: str) -> str:
    session_factory = _make_session_factory()

    async with session_factory() as session:
        #транзакция 1: зарядка/сканирование/движение
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
            max_x = max(0, (warehouse.row_x or 1) - 1)
            max_y_num = max(1, min((warehouse.row_y or 1), 26))

            # завершилась ли зарядка?
            _maybe_finish_charging(robot)
            await session.flush()

            # заряжается — стоим
            if robot.status == "charging":
                EVENTS.sync_q.put({
                    "type": "robot.position",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "warehouse_id": robot.warehouse_id,
                    "robot_id": robot.id,
                    "x": robot.current_row,
                    "y": shelf_str_to_num(robot.current_shelf),
                    "shelf": robot.current_shelf,
                    "battery_level": robot.battery_level or 0,
                    "status": robot.status,
                    "charging_until": _CHARGING_UNTIL.get(robot.id).isoformat() if _CHARGING_UNTIL.get(robot.id) else None,
                })
                print(f"⚡ [Warehouse {robot.warehouse_id}] Robot {robot.id} charging at ({DOCK_ROW},{DOCK_SHELF_STR})")
                return robot_id

            # идёт сканирование?
            _ = await _maybe_finish_scanning(robot, session)
            await session.flush()
            if robot.status == "scanning":
                EVENTS.sync_q.put({
                    "type": "robot.position",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "warehouse_id": robot.warehouse_id,
                    "robot_id": robot.id,
                    "x": robot.current_row,
                    "y": shelf_str_to_num(robot.current_shelf),
                    "shelf": robot.current_shelf,
                    "battery_level": robot.battery_level or 0,
                    "status": robot.status,
                    "scanning_until": _SCANNING_UNTIL.get(robot.id).isoformat() if _SCANNING_UNTIL.get(robot.id) else None,
                })
                print(f"📡 [Warehouse {robot.warehouse_id}] Robot {robot.id} scanning at "
                      f"({robot.current_row},{robot.current_shelf}) "
                      f"until={_SCANNING_UNTIL.get(robot.id)}")
                return robot_id

            # батарея 0 — на зарядку
            if (robot.battery_level or 0) <= 0:
                _begin_charging(robot)
                await session.flush()
                print(f"🪫 [Warehouse {robot.warehouse_id}] Robot {robot.id} moved to dock ({DOCK_ROW},{DOCK_SHELF_STR}) for charging")
                return robot_id

            # движение
            start_x = robot.current_row
            start_y_num = shelf_str_to_num(robot.current_shelf)
            start = (start_x, start_y_num)

            goal = _TARGETS.get(robot.id)
            if (
                goal is None
                or not (0 <= goal[0] <= max_x and 1 <= goal[1] <= max_y_num)
                or goal == start
            ):
                goal = _pick_new_goal(max_x, max_y_num, start)
                _TARGETS[robot.id] = goal

            next_x, next_y_num = _next_step_towards(start, goal)
            next_x = _bounded(next_x, 0, max_x)
            next_y_num = _bounded(next_y_num, 1, max_y_num)

            # расход батареи за шаг
            _consume_battery(robot, warehouse.row_x or 1, warehouse.row_y or 1)

            # фиксация координат
            robot.current_row = next_x
            robot.current_shelf = shelf_num_to_str(next_y_num)  # буква
            robot.status = robot.status or "idle"
            if (next_x, next_y_num) == goal:
                _TARGETS[robot.id] = _pick_new_goal(max_x, max_y_num, (next_x, next_y_num))

            # если батарея упала до 0 — зарядка
            if (robot.battery_level or 0) <= 0:
                _begin_charging(robot)
                await session.flush()
                print(f"🪫 [Warehouse {robot.warehouse_id}] Robot {robot.id} moved to dock ({DOCK_ROW},{DOCK_SHELF_STR}) for charging")
                return robot_id

            # позиция после шага
            await session.flush()
            print(
                f"🤖 [Warehouse {robot.warehouse_id}] Robot {robot.id} "
                f"({start_x},{shelf_num_to_str(start_y_num)}) → ({next_x},{shelf_num_to_str(next_y_num)})  "
                f"goal=({goal[0]},{shelf_num_to_str(goal[1])})  battery={robot.battery_level}%"
            )
            EVENTS.sync_q.put({
                "type": "robot.position",
                "ts": datetime.now(timezone.utc).isoformat(),
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": next_x,
                "y": next_y_num,                        # числовой Y (1..26)
                "shelf": shelf_num_to_str(next_y_num),  # буквенный Y
                "battery_level": robot.battery_level or 0,
                "status": robot.status or "idle",
            })

        #транзакция 2: если на клетке есть товары — СТАРТ сканирования (10 сек)
        async with session.begin():
            if robot.status not in ("charging", "scanning"):
                cur_y_num = shelf_str_to_num(robot.current_shelf)
                cell_has_products = await _cell_has_products(session, robot.warehouse_id, robot.current_row, cur_y_num)
                if cell_has_products:
                    _begin_scanning(robot, robot.current_row, cur_y_num)
                    await session.flush()
                    EVENTS.sync_q.put({
                        "type": "robot.position",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "warehouse_id": robot.warehouse_id,
                        "robot_id": robot.id,
                        "x": robot.current_row,
                        "y": cur_y_num,
                        "shelf": robot.current_shelf,
                        "battery_level": robot.battery_level or 0,
                        "status": robot.status,
                        "scanning_until": _SCANNING_UNTIL.get(robot.id).isoformat(),
                    })

    return robot_id

# helper: проверка наличия товаров на клетке (Product.current_shelf = str)
async def _cell_has_products(session: AsyncSession, warehouse_id: str, x: int, y_num: int) -> bool:
    shelf_letter = shelf_num_to_str(y_num)
    result = await session.execute(
        select(Product.id).where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            Product.current_shelf == shelf_letter,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None

# Параллельный шаг всех роботов склада
def _run_in_thread(robot_id: str) -> str:
    return asyncio.run(_move_robot_once(robot_id))

async def move_all_robots_concurrently(
    warehouse_id: str,
    global_session_factory: async_sessionmaker[AsyncSession],
    *,
    max_workers: int = 8,
) -> List[str]:
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

# Вотчер
async def run_robot_watcher(interval: float = 5.0, max_workers: int = 8) -> None:
    from app.db.session import async_session

    print("🚀 [async] Robot watcher started. (parallel, battery/charging, scanning, history/stock, shelf A..Z)")
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
