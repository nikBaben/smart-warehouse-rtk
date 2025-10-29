from __future__ import annotations
# === Segfault hardening: отключаем C-extensions SQLAlchemy и GC у greenlet ДО импортов sqlalchemy
import os as _os
_os.environ.setdefault("SQLALCHEMY_DISABLE_CEXT", "1")
_os.environ.setdefault("GREENLET_USE_GC", "0")  # опционально; снижает шанс падений при GC

"""
Эмулятор робота с БД и шиной событий + multiprocessing.

Анти-лаги и стабильность:
- Fast scanner loop: быстрый цикл каждые FAST_SCAN_INTERVAL_MS, завершает сканы вне общей очереди.
- Приоритет тиков для сканирующих + round-robin окно ROBOTS_PER_TICK для остальных.
- «Двойное» определение сканирующих (in-memory таймер ИЛИ статус в снапшоте) — не залипают после рестартов.
- Fail-safe завершение скана (_safe_finish_scan): при ошибке очищает состояние и шлёт product.scan с reason=scan_error.
- Watchdog SCAN_MAX_DURATION_MS: форс-завершение, если скан висит слишком долго.
- In-memory снапшот позиций: robot.positions / robot.positions.diff + keepalive.
- Версионирование снапшота, прогрев из БД, мягкий rate-limit, per-tick кэш eligibility, lazy goal refresh.

Запуск:
    asyncio.run(run_robot_watcher())          # однопроцессный
    asyncio.run(run_robot_watcher_mproc())    # по процессу на склад
"""

import asyncio
import os
import random
import multiprocessing as mp
import signal
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import load_only

from app.db.session import async_session as AppSession
from app.core.config import settings  # noqa: F401
from app.models.warehouse import Warehouse
from app.models.robot import Robot
from app.models.product import Product
from app.models.inventory_history import InventoryHistory

from app.events.bus import (
    get_bus_for_current_loop,
    close_bus_for_current_loop,
    ROBOT_CH,
    COMMON_CH,
)

# =========================
# Константы симуляции
# =========================
FIELD_X = 50
FIELD_Y = 26
DOCK_X, DOCK_Y = 0, 0

TICK_INTERVAL = float(os.getenv("ROBOT_TICK_INTERVAL", "0.5"))
SCAN_DURATION = timedelta(seconds=int(os.getenv("SCAN_DURATION_SEC", "6")))
RESCAN_COOLDOWN = timedelta(seconds=int(os.getenv("RESCAN_COOLDOWN_SEC", "30")))
CHARGE_DURATION = timedelta(seconds=int(os.getenv("CHARGE_DURATION_SEC", "45")))
LOW_BATTERY_THRESHOLD = float(os.getenv("LOW_BATTERY_THRESHOLD", "15"))

BATTERY_DROP_PER_STEP = float(os.getenv("BATTERY_DROP_PER_STEP", "0.6"))
POSITION_RATE_LIMIT_PER_ROBOT = float(os.getenv("POSITION_RATE_LIMIT_SEC", "0.25"))
ROBOTS_CONCURRENCY = int(os.getenv("ROBOT_CONCURRENCY", "12"))

# =========================
# Параметры позиций/шины
# =========================
POSITIONS_MIN_INTERVAL_MS = int(os.getenv("POSITIONS_MIN_INTERVAL_MS", "75"))
POSITIONS_KEEPALIVE_MS = int(os.getenv("POSITIONS_KEEPALIVE_MS", "1000"))
KEEPALIVE_FULL = os.getenv("KEEPALIVE_FULL", "1") == "1"
POSITIONS_DIFFS = os.getenv("POSITIONS_DIFFS", "0") == "1"
# === БЫЛ БАГ: флаг одиночных позиций был инвертирован. Фикс:
SEND_ROBOT_POSITION = os.getenv("SEND_ROBOT_POSITION", "1") == "0"

# Разрежённый поиск цели
IDLE_GOAL_LOOKUP_EVERY = int(os.getenv("IDLE_GOAL_LOOKUP_EVERY", "2"))

# Round-robin окно по складу
ROBOTS_PER_TICK = int(os.getenv("ROBOTS_PER_TICK", "256"))

# Fast scanner loop (ускоренное завершение сканов)
FAST_SCAN_LOOP = os.getenv("FAST_SCAN_LOOP", "1") == "1"
FAST_SCAN_INTERVAL_MS = int(os.getenv("FAST_SCAN_INTERVAL_MS", "75"))
FAST_SCAN_MAX_PER_TICK = int(os.getenv("FAST_SCAN_MAX_PER_TICK", "512"))

# Watchdog: максимум длительности скана (мс). По умолчанию x3 от SCAN_DURATION.
SCAN_MAX_DURATION_MS = int(os.getenv(
    "SCAN_MAX_DURATION_MS",
    str(int(max(1.0, SCAN_DURATION.total_seconds()) * 3000))
))

# === Частота широковещания позиций (строго, независимо от нагрузки) ===========
# раз в 1 секунду пытаемся отправить обновление; максимум 2 секунды без пакета (keepalive)
POSITIONS_BROADCAST_INTERVAL_MS = int(os.getenv("POSITIONS_BROADCAST_INTERVAL_MS", "1000"))
POSITIONS_MAX_INTERVAL_MS = int(os.getenv("POSITIONS_MAX_INTERVAL_MS", "2000"))

# =========================
# Память процесса
# =========================
_TARGETS: Dict[str, Tuple[int, int]] = {}
_SCANNING_UNTIL: Dict[str, datetime] = {}
_SCANNING_CELL: Dict[str, Tuple[int, int]] = {}
_SCANNING_STARTED_AT: Dict[str, datetime] = {}
_LAST_POS_SENT_AT: Dict[str, datetime] = {}                   # per-robot
_CLAIMED: Dict[str, Set[Tuple[int, int]]] = {}                # per-warehouse

# In-memory снапшот состояний роботов по складу
_WH_SNAPSHOT: Dict[str, Dict[str, dict]] = {}
_WH_SNAPSHOT_VER: Dict[str, int] = {}
_WH_LAST_SENT_VER: Dict[str, int] = {}
_WH_LAST_SENT_MAP: Dict[str, Dict[str, dict]] = {}
_LAST_POS_BROADCAST_AT: Dict[str, float] = {}
_LAST_ANY_SENT_AT: Dict[str, float] = {}
_WH_LOCKS: Dict[str, asyncio.Lock] = {}

# per-tick cache для eligibility
_ELIGIBLE_CACHE: Dict[str, dict] = {}
_WH_TICK_COUNTER: Dict[str, int] = {}

# Планировщик/приоритеты
_ROBOT_WH: Dict[str, str] = {}           # robot_id -> warehouse_id
_WH_ROBOT_OFFSET: Dict[str, int] = {}    # смещение окна по складу

# Fast scanner task registry
_WH_FASTSCAN_TASK: Dict[str, asyncio.Task] = {}  # wh -> task

# Positions broadcaster task registry
_WH_POS_TASK: Dict[str, asyncio.Task] = {}  # wh -> task

# =========================
# Утилиты координат/полок
# =========================
ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def shelf_num_to_str(n: int) -> str:
    return ALPH[max(0, min(25, n - 1))] if n > 0 else "0"

def shelf_str_to_num(s: Optional[str]) -> int:
    if not s:
        return 0
    s = s.strip().upper()
    if not s or s == "0":
        return 0
    c = s[0]
    return ALPH.index(c) + 1 if c in ALPH else 0

def clamp_xy(x: int, y: int) -> Tuple[int, int]:
    x = max(0, min(FIELD_X - 1, x))
    y = max(0, min(FIELD_Y, y))
    return x, y

def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def _claimed_set(warehouse_id: str) -> Set[Tuple[int, int]]:
    return _CLAIMED.setdefault(warehouse_id, set())

def _claim(warehouse_id: str, cell: Tuple[int, int]) -> None:
    _claimed_set(warehouse_id).add(cell)

def _free_claim(warehouse_id: str, cell: Tuple[int, int]) -> None:
    _claimed_set(warehouse_id).discard(cell)

def _wh_lock(warehouse_id: str) -> asyncio.Lock:
    lk = _WH_LOCKS.get(warehouse_id)
    if lk is None:
        lk = _WH_LOCKS[warehouse_id] = asyncio.Lock()
    return lk

def _wh_snapshot(warehouse_id: str) -> Dict[str, dict]:
    return _WH_SNAPSHOT.setdefault(warehouse_id, {})

def _last_sent_map(warehouse_id: str) -> Dict[str, dict]:
    return _WH_LAST_SENT_MAP.setdefault(warehouse_id, {})

def _next_tick_id(warehouse_id: str) -> int:
    _WH_TICK_COUNTER[warehouse_id] = _WH_TICK_COUNTER.get(warehouse_id, 0) + 1
    return _WH_TICK_COUNTER[warehouse_id]

def _get_tick_cache(warehouse_id: str, tick_id: int) -> dict:
    c = _ELIGIBLE_CACHE.get(warehouse_id)
    if not c or c.get("tick_id") != tick_id:
        c = _ELIGIBLE_CACHE[warehouse_id] = {
            "cells": None,
            "by_cell": {},
            "cutoff": None,
            "tick_id": tick_id,
            "local_selected": set(),  # локально выбранные клетки на этот тик склада
        }
    return c

# =========================
# События
# =========================
async def _emit(evt: dict) -> None:
    t = evt.get("type", "")
    ch = ROBOT_CH if t.startswith("robot.position") or t in {
        "robot.positions", "robot.positions.diff", "robot.positions.keepalive", "product.scan"
    } else COMMON_CH
    bus = await get_bus_for_current_loop()
    await bus.publish(ch, evt)

async def _emit_position_if_needed(robot: Robot) -> None:
    if not SEND_ROBOT_POSITION:
        return
    now = datetime.now(timezone.utc)
    last = _LAST_POS_SENT_AT.get(robot.id, datetime.fromtimestamp(0, tz=timezone.utc))
    if (now - last).total_seconds() < POSITION_RATE_LIMIT_PER_ROBOT:
        return
    _LAST_POS_SENT_AT[robot.id] = now
    y = int(robot.current_shelf or 0)
    await _emit({
        "type": "robot.position",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": int(robot.current_row or 0),
        "y": y,
        "shelf": shelf_num_to_str(y),
        "battery_level": round(float(robot.battery_level or 0.0), 1),
        "status": (robot.status or "idle"),
        "ts": now.isoformat(),
    })

# === Снапшот склада ===========================================================
def _update_wh_snapshot_from_robot(robot: Robot) -> None:
    wh = robot.warehouse_id
    _ROBOT_WH[robot.id] = wh
    y_int = int(robot.current_shelf or 0)
    new_item = {
        "robot_id": robot.id,
        "x": int(robot.current_row or 0),
        "y": y_int,
        "shelf": shelf_num_to_str(y_int),
        "battery_level": round(float(robot.battery_level or 0.0), 1),
        "status": (robot.status or "idle"),
    }
    snap = _wh_snapshot(wh)
    old_item = snap.get(robot.id)
    if old_item != new_item:
        snap[robot.id] = new_item
        _WH_SNAPSHOT_VER[wh] = _WH_SNAPSHOT_VER.get(wh, 0) + 1

def _is_scanning_in_snapshot(warehouse_id: str, rid: str) -> bool:
    item = _wh_snapshot(warehouse_id).get(rid)
    return bool(item and (item.get("status") or "").lower() == "scanning")

# === DIFF helpers =============================================================
def _calc_diff_payload(warehouse_id: str, snap: Dict[str, dict]) -> Tuple[List[dict], List[str]]:
    last = _last_sent_map(warehouse_id)
    changed: List[dict] = []
    removed: List[str] = []
    for rid, item in snap.items():
        if last.get(rid) != item:
            changed.append(item)
    for rid in list(last.keys()):
        if rid not in snap:
            removed.append(rid)
    return changed, removed

def _remember_last_sent_map(warehouse_id: str, snap: Dict[str, dict]) -> None:
    _WH_LAST_SENT_MAP[warehouse_id] = {rid: dict(item) for rid, item in snap.items()}

# === Пакетные позиции (full/diff + keepalive) =================================
async def _maybe_emit_positions_snapshot_inmem(warehouse_id: str) -> None:
    loop = asyncio.get_running_loop()
    now_mono = loop.time()
    last_any = _LAST_ANY_SENT_AT.get(warehouse_id, 0.0)
    need_keepalive = (now_mono - last_any) * 1000.0 >= POSITIONS_KEEPALIVE_MS
    last_rl = _LAST_POS_BROADCAST_AT.get(warehouse_id, 0.0)
    rl_ok = (now_mono - last_rl) * 1000.0 >= POSITIONS_MIN_INTERVAL_MS

    async with _wh_lock(warehouse_id):
        now_mono = loop.time()
        need_keepalive = need_keepalive or ((now_mono - _LAST_ANY_SENT_AT.get(warehouse_id, 0.0)) * 1000.0 >= POSITIONS_KEEPALIVE_MS)
        rl_ok = rl_ok and ((now_mono - _LAST_POS_BROADCAST_AT.get(warehouse_id, 0.0)) * 1000.0 >= POSITIONS_MIN_INTERVAL_MS)

        cur_ver = _WH_SNAPSHOT_VER.get(warehouse_id, 0)
        last_sent_ver = _WH_LAST_SENT_VER.get(warehouse_id, -1)
        snap_dict = _wh_snapshot(warehouse_id)

        has_changes = cur_ver != last_sent_ver
        have_data = bool(snap_dict)

        if not have_data and not need_keepalive:
            return

        if has_changes and rl_ok and have_data:
            payload_ts = datetime.now(timezone.utc).isoformat()
            if POSITIONS_DIFFS:
                changed, removed = _calc_diff_payload(warehouse_id, snap_dict)
                if changed or removed:
                    await _emit({
                        "type": "robot.positions.diff",
                        "warehouse_id": warehouse_id,
                        "version": cur_ver,
                        "base_version": last_sent_ver,
                        "changed": changed,
                        "removed": removed,
                        "ts": payload_ts,
                    })
                    _remember_last_sent_map(warehouse_id, snap_dict)
                    _WH_LAST_SENT_VER[warehouse_id] = cur_ver
                    _LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
                    _LAST_ANY_SENT_AT[warehouse_id] = _LAST_POS_BROADCAST_AT[warehouse_id]
                    return
            await _emit({
                "type": "robot.positions",
                "warehouse_id": warehouse_id,
                "robots": list(snap_dict.values()),
                "version": cur_ver,
                "ts": payload_ts,
            })
            _remember_last_sent_map(warehouse_id, snap_dict)
            _WH_LAST_SENT_VER[warehouse_id] = cur_ver
            _LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
            _LAST_ANY_SENT_AT[warehouse_id] = _LAST_POS_BROADCAST_AT[warehouse_id]
            return

        if need_keepalive:
            payload_ts = datetime.now(timezone.utc).isoformat()
            if POSITIONS_DIFFS and not KEEPALIVE_FULL:
                await _emit({
                    "type": "robot.positions.keepalive",
                    "warehouse_id": warehouse_id,
                    "version": cur_ver,
                    "robot_count": len(snap_dict),
                    "ts": payload_ts,
                })
            else:
                await _emit({
                    "type": "robot.positions",
                    "warehouse_id": warehouse_id,
                    "robots": list(snap_dict.values()),
                    "version": cur_ver,
                    "ts": payload_ts,
                })
                _remember_last_sent_map(warehouse_id, snap_dict)
                _WH_LAST_SENT_VER[warehouse_id] = cur_ver
                _LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
            _LAST_ANY_SENT_AT[warehouse_id] = loop.time()
            return

# === Немедленная отсылка полного снапшота (без rate-limit) ===================
async def _emit_positions_snapshot_force(warehouse_id: str) -> None:
    async with _wh_lock(warehouse_id):
        snap_dict = _wh_snapshot(warehouse_id)
        payload = list(snap_dict.values())
        cur_ver = _WH_SNAPSHOT_VER.get(warehouse_id, 0)
    if not payload:
        return
    await _emit({
        "type": "robot.positions",
        "warehouse_id": warehouse_id,
        "robots": payload,
        "version": cur_ver,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    loop = asyncio.get_running_loop()
    _remember_last_sent_map(warehouse_id, snap_dict)
    _WH_LAST_SENT_VER[warehouse_id] = cur_ver
    _LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
    _LAST_ANY_SENT_AT[warehouse_id] = _LAST_POS_BROADCAST_AT[warehouse_id]

# === Прогрев/синхронизация снапшота из БД ====================================
async def _warmup_or_sync_snapshot(session: AsyncSession, warehouse_id: str, robot_ids: Optional[List[str]] = None) -> None:
    if robot_ids is None:
        r = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
        robot_ids = list(r.scalars().all())
    if robot_ids:
        res = await session.execute(
            select(Robot.id, Robot.current_row, Robot.current_shelf, Robot.battery_level, Robot.status)
            .where(Robot.warehouse_id == warehouse_id, Robot.id.in_(robot_ids))
        )
        db_rows = {rid: (x, y, battery, status) for rid, x, y, battery, status in res.all()}
    else:
        db_rows = {}
    changed = False
    async with _wh_lock(warehouse_id):
        snap = _wh_snapshot(warehouse_id)
        if robot_ids is not None:
            for rid in list(snap.keys()):
                if rid not in robot_ids:
                    snap.pop(rid, None)
                    changed = True
        for rid in robot_ids:
            x, y, battery, status = db_rows.get(rid, (0, 0, 0.0, "idle"))
            _ROBOT_WH[rid] = warehouse_id
            y_int = int(y or 0)
            new_item = {
                "robot_id": rid,
                "x": int(x or 0),
                "y": y_int,
                "shelf": shelf_num_to_str(y_int),
                "battery_level": round(float(battery or 0.0), 1),
                "status": status or "idle",
            }
            if snap.get(rid) != new_item:
                snap[rid] = new_item
                changed = True
        if changed:
            _WH_SNAPSHOT_VER[warehouse_id] = _WH_SNAPSHOT_VER.get(warehouse_id, 0) + 1

# =========================
# Выборки из БД
# =========================
async def _eligible_cells(session: AsyncSession, warehouse_id: str, cutoff: datetime) -> List[Tuple[int, int]]:
    rows = await session.execute(
        select(Product.current_row, func.upper(func.trim(Product.current_shelf)))
        .where(
            Product.warehouse_id == warehouse_id,
            func.upper(func.trim(Product.current_shelf)) != "0",
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
        .distinct()
    )
    cells: List[Tuple[int, int]] = []
    for x, shelf_str in rows.all():
        y = shelf_str_to_num(shelf_str)
        if y > 0:
            x_int = int(x or 0)
            if 0 <= x_int <= 49 and 1 <= y <= 26:
                cells.append((x_int, y))
    return cells

async def _eligible_products_in_cell(
    session: AsyncSession, warehouse_id: str, x: int, y: int, cutoff: datetime
) -> List[Product]:
    shelf = shelf_num_to_str(y)
    res = await session.execute(
        select(Product)
        .options(
            load_only(
                Product.id, Product.name, Product.category, Product.article,
                Product.stock, Product.min_stock, Product.optimal_stock,
                Product.current_zone, Product.current_row, Product.current_shelf,
            )
        )
        .where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            func.upper(func.trim(Product.current_shelf)) == shelf,
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
    )
    return list(res.scalars().all())

# =========================
# Сканирование
# =========================
async def _start_scan(robot: Robot, x: int, y: int) -> None:
    robot.status = "scanning"
    _SCANNING_CELL[robot.id] = (x, y)
    now = datetime.now(timezone.utc)
    _SCANNING_STARTED_AT[robot.id] = now
    _SCANNING_UNTIL[robot.id] = now + SCAN_DURATION
    _update_wh_snapshot_from_robot(robot)

async def _finish_scan(session: AsyncSession, robot: Robot) -> None:
    rx, ry = _SCANNING_CELL.pop(robot.id, (int(robot.current_row or 0), int(robot.current_shelf or 0)))
    _SCANNING_UNTIL.pop(robot.id, None)
    _SCANNING_STARTED_AT.pop(robot.id, None)

    shelf = shelf_num_to_str(ry)
    if shelf == "0":
        await _emit({
            "type": "product.scan",
            "warehouse_id": robot.warehouse_id,
            "robot_id": robot.id,
            "x": rx, "y": ry, "shelf": shelf,
            "products": [],
            "reason": "no_valid_shelf",
        })
        _free_claim(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        _update_wh_snapshot_from_robot(robot)
        return

    cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
    products = await _eligible_products_in_cell(session, robot.warehouse_id, rx, ry, cutoff)

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    if not products:
        await _emit({
            "type": "product.scan",
            "warehouse_id": robot.warehouse_id,
            "robot_id": robot.id,
            "x": rx, "y": ry, "shelf": shelf,
            "products": [],
            "reason": "under_cooldown",
            "ts": now_iso,
        })
        _free_claim(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        _update_wh_snapshot_from_robot(robot)
        return

    rows: List[dict] = []
    payload: List[dict] = []
    for p in products:
        stock = int(p.stock or 0)
        status = "ok"
        if p.min_stock is not None and stock < p.min_stock:
            status = "critical"
        elif p.optimal_stock is not None and stock < p.optimal_stock:
            status = "low"

        rows.append(
            {
                "id": f"ih_{os.urandom(6).hex()}",
                "product_id": p.id,
                "robot_id": robot.id,
                "warehouse_id": robot.warehouse_id,
                "current_zone": getattr(p, "current_zone", "Хранение"),
                "current_row": rx,
                "current_shelf": shelf,
                "name": p.name,
                "category": p.category,
                "article": getattr(p, "article", None) or "unknown",
                "stock": stock,
                "min_stock": p.min_stock,
                "optimal_stock": p.optimal_stock,
                "status": status,
            }
        )
        payload.append(
            {
                "id": p.id, "name": p.name, "category": p.category, "article": getattr(p, "article", None),
                "current_row": rx, "current_shelf": shelf, "shelf_num": ry,
                "stock": stock, "status": status, "scanned_at": now_iso,
            }
        )

    await session.execute(insert(InventoryHistory), rows)
    await session.execute(
        update(Product)
        .where(Product.id.in_([r["product_id"] for r in rows]))
        .values(last_scanned_at=now_dt)
    )

    await _emit({
        "type": "product.scan",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": rx, "y": ry, "shelf": shelf,
        "products": payload,
        "ts": now_iso,
    })

    _free_claim(robot.warehouse_id, (rx, ry))
    robot.status = "idle"
    _update_wh_snapshot_from_robot(robot)

async def _safe_finish_scan(session: AsyncSession, robot: Robot) -> None:
    """Защищённое завершение скана: при исключении очищает состояние и шлёт product.scan с reason=scan_error."""
    try:
        await _finish_scan(session, robot)
    except Exception as e:
        rx, ry = int(robot.current_row or 0), int(robot.current_shelf or 0)
        _SCANNING_CELL.pop(robot.id, None)
        _SCANNING_UNTIL.pop(robot.id, None)
        _SCANNING_STARTED_AT.pop(robot.id, None)
        _free_claim(robot.warehouse_id, (rx, ry))
        robot.status = "idle"
        await session.flush()
        _update_wh_snapshot_from_robot(robot)
        try:
            await _emit({
                "type": "product.scan",
                "warehouse_id": robot.warehouse_id,
                "robot_id": robot.id,
                "x": rx, "y": ry, "shelf": shelf_num_to_str(ry),
                "products": [],
                "reason": "scan_error",
                "error": (str(e) or "")[:200],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        print(f"⚠️ safe_finish_scan: error rid={robot.id}: {e}", flush=True)

# =========================
# Eligible-проверка цели
# =========================
async def _cell_still_eligible(session: AsyncSession, warehouse_id: str, cell: Tuple[int, int], cutoff: datetime) -> bool:
    x, y = cell
    shelf = shelf_num_to_str(y)
    row = await session.execute(
        select(Product.id).where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == x,
            func.upper(func.trim(Product.current_shelf)) == shelf,
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        ).limit(1)
    )
    return row.first() is not None

# =========================
# Один тик робота
# =========================
async def _robot_tick(session: AsyncSession, robot_id: str, tick_id: Optional[int] = None) -> None:
    rres = await session.execute(
        select(Robot)
        .options(load_only(
            Robot.id, Robot.warehouse_id, Robot.status,
            Robot.battery_level, Robot.current_row, Robot.current_shelf,
        ))
        .where(Robot.id == robot_id)
    )
    robot = rres.scalar_one_or_none()
    if not robot:
        return

    _ROBOT_WH[robot.id] = robot.warehouse_id
    wid = robot.warehouse_id
    tid = tick_id or _next_tick_id(wid)
    cache = _get_tick_cache(wid, tid)
    cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
    cache["cutoff"] = cutoff

    # 1) Сканируем?
    if (robot.status or "").lower() == "scanning":
        # если таймер отсутствует (после рестарта) — инициализируем
        if robot.id not in _SCANNING_UNTIL:
            now = datetime.now(timezone.utc)
            _SCANNING_STARTED_AT[robot.id] = now
            _SCANNING_UNTIL[robot.id] = now + SCAN_DURATION
            _SCANNING_CELL.setdefault(robot.id, (int(robot.current_row or 0), int(robot.current_shelf or 0)))
        # watchdog
        start_at = _SCANNING_STARTED_AT.get(robot.id)
        if start_at and (datetime.now(timezone.utc) - start_at).total_seconds() * 1000.0 > SCAN_MAX_DURATION_MS:
            await _safe_finish_scan(session, robot)
            await session.flush()
            _update_wh_snapshot_from_robot(robot)
            await _maybe_emit_positions_snapshot_inmem(wid)
            return

        until = _SCANNING_UNTIL.get(robot.id)
        if until and datetime.now(timezone.utc) >= until:
            await _safe_finish_scan(session, robot)
            await session.flush()
            _update_wh_snapshot_from_robot(robot)
            await _emit_position_if_needed(robot)
            await _maybe_emit_positions_snapshot_inmem(wid)
        return

    # 2) Зарядка?
    if (robot.status or "").lower() == "charging":
        inc = 100.0 * (TICK_INTERVAL / CHARGE_DURATION.total_seconds())
        robot.battery_level = min(100.0, float(robot.battery_level or 0.0) + inc)
        if float(robot.battery_level) >= 100.0:
            robot.status = "idle"
        await session.flush()
        _update_wh_snapshot_from_robot(robot)
        await _emit_position_if_needed(robot)
        await _maybe_emit_positions_snapshot_inmem(wid)
        return

    # 3) Поиск/поддержание цели
    cur = (int(robot.current_row or 0), int(robot.current_shelf or 0))
    goal = _TARGETS.get(robot.id)

    if float(robot.battery_level or 0.0) <= LOW_BATTERY_THRESHOLD:
        if goal:
            _free_claim(wid, goal)
            _TARGETS.pop(robot.id, None)
        goal = (DOCK_X, DOCK_Y)
    else:
        if goal is not None:
            still_ok = await _cell_still_eligible(session, wid, goal, cutoff)
            if not still_ok:
                _free_claim(wid, goal)
                _TARGETS.pop(robot.id, None)
                goal = None
        if goal is None:
            if tid % IDLE_GOAL_LOOKUP_EVERY == 0:
                if cache["cells"] is None:
                    cache["cells"] = await _eligible_cells(session, wid, cutoff)
                cells = cache["cells"] or []
                if cells:
                    claimed = _claimed_set(wid)
                    local_sel: Set[Tuple[int, int]] = cache["local_selected"]
                    best: Optional[Tuple[int, int]] = None
                    best_d: Optional[int] = None

                    # Предварительный выбор с учётом глобально занятых и уже локально выбранных на этот тик
                    for c in cells:
                        if c in claimed or c in local_sel:
                            continue
                        d = manhattan(cur, c)
                        if best_d is None or d < best_d:
                            best_d, best = d, c

                    if best is not None:
                        # Атомарная фиксация под локом склада для предотвращения гонок в рамках тика
                        async with _wh_lock(wid):
                            cache_now = _get_tick_cache(wid, tid)
                            local_sel_now: Set[Tuple[int, int]] = cache_now["local_selected"]
                            if best not in _claimed_set(wid) and best not in local_sel_now:
                                local_sel_now.add(best)   # локально пометили на этот тик
                                _claim(wid, best)         # глобальная бронь
                                _TARGETS[robot.id] = best
                                goal = best
                            else:
                                # цель успели занять — попробуем снова в следующий цикл
                                pass

    # 4) Шаг движения
    cur_x, cur_y = cur
    if goal:
        tx, ty = goal
        nx, ny = cur_x, cur_y
        if nx != tx:
            nx += 1 if tx > nx else -1
        elif ny != ty:
            ny += 1 if ty > ny else -1
    else:
        cand = [(cur_x + 1, cur_y), (cur_x - 1, cur_y), (cur_x, cur_y + 1), (cur_x, cur_y - 1)]
        valid = [(x, y) for (x, y) in cand if 0 <= x <= FIELD_X - 1 and 1 <= y <= FIELD_Y]
        nx, ny = random.choice(valid) if valid else (cur_x, cur_y)

    nx, ny = clamp_xy(nx, ny)

    moved = (nx, ny) != (cur_x, cur_y)
    if moved:
        robot.battery_level = max(0.0, float(robot.battery_level or 0.0) - BATTERY_DROP_PER_STEP)

    # Села батарея — на док и зарядка
    if float(robot.battery_level or 0.0) <= 0.0:
        robot.current_row, robot.current_shelf = DOCK_X, DOCK_Y
        robot.status = "charging"
        if goal and goal != (DOCK_X, DOCK_Y):
            _free_claim(wid, goal)
        _TARGETS.pop(robot.id, None)
        await session.flush()
        _update_wh_snapshot_from_robot(robot)
        await _emit_position_if_needed(robot)
        await _maybe_emit_positions_snapshot_inmem(wid)
        return

    robot.current_row, robot.current_shelf = nx, ny
    robot.status = "idle"
    await session.flush()
    _update_wh_snapshot_from_robot(robot)
    await _emit_position_if_needed(robot)
    await _maybe_emit_positions_snapshot_inmem(wid)

    if (nx, ny) == (DOCK_X, DOCK_Y) and float(robot.battery_level) < 100.0:
        robot.status = "charging"
        if goal and goal != (DOCK_X, DOCK_Y):
            _free_claim(wid, goal)
        _TARGETS.pop(robot.id, None)
        await session.flush()
        _update_wh_snapshot_from_robot(robot)
        await _maybe_emit_positions_snapshot_inmem(wid)
        return

    if goal and (nx, ny) == goal:
        key = (nx, ny)
        if key not in cache["by_cell"]:
            cache["by_cell"][key] = await _eligible_products_in_cell(session, wid, nx, ny, cutoff)
        eligible_now = cache["by_cell"][key]
        if eligible_now:
            await _start_scan(robot, nx, ny)
        else:
            _free_claim(wid, goal)
        _TARGETS.pop(robot.id, None)
        await session.flush()
        _update_wh_snapshot_from_robot(robot)
        await _maybe_emit_positions_snapshot_inmem(wid)

# =========================
# Планировщик: окно с приоритетом сканов
# =========================
def _select_robot_batch(warehouse_id: str, robot_ids: List[str]) -> List[str]:
    if not robot_ids:
        return []
    # приоритет: ИЛИ есть таймер, ИЛИ статус в снапшоте == scanning
    scanning = [rid for rid in robot_ids if (rid in _SCANNING_UNTIL) or _is_scanning_in_snapshot(warehouse_id, rid)]
    scanning_set = set(scanning)
    normal = [rid for rid in robot_ids if rid not in scanning_set]

    win = max(ROBOTS_PER_TICK - len(scanning), 0)
    if win <= 0:
        return scanning

    n = len(normal)
    if n == 0:
        return scanning

    off = _WH_ROBOT_OFFSET.get(warehouse_id, 0) % n
    if off + win <= n:
        batch = normal[off:off + win]
    else:
        batch = normal[off:] + normal[:(off + win) % n]
    _WH_ROBOT_OFFSET[warehouse_id] = (off + win) % n
    return scanning + batch

# =========================
# FAST SCANNER LOOP
# =========================
async def _fast_scan_loop(warehouse_id: str) -> None:
    """Каждые FAST_SCAN_INTERVAL_MS завершает готовые сканы; инициализирует таймеры для роботов со статусом 'scanning'."""
    interval = max(5, FAST_SCAN_INTERVAL_MS) / 1000.0
    try:
        while True:
            now = datetime.now(timezone.utc)
            # Собираем кандидатов: все rid со статусом 'scanning' в снапшоте этого склада
            scan_rids = [item["robot_id"] for item in _wh_snapshot(warehouse_id).values()
                         if (item.get("status") or "").lower() == "scanning"]

            processed = 0
            for rid in scan_rids:
                if processed >= FAST_SCAN_MAX_PER_TICK:
                    break
                # Инициализируем таймер, если отсутствует (после рестарта/прогрева)
                if rid not in _SCANNING_UNTIL:
                    _SCANNING_STARTED_AT[rid] = now
                    _SCANNING_UNTIL[rid] = now  # сразу готов к завершению
                    snap = _wh_snapshot(warehouse_id).get(rid) or {}
                    _SCANNING_CELL.setdefault(rid, (int(snap.get("x") or 0), int(snap.get("y") or 0)))

                until = _SCANNING_UNTIL.get(rid)
                start_at = _SCANNING_STARTED_AT.get(rid)
                # watchdog
                if start_at and (now - start_at).total_seconds() * 1000.0 > SCAN_MAX_DURATION_MS:
                    try:
                        async with AppSession() as s:
                            async with s.begin():
                                rres = await s.execute(
                                    select(Robot).options(load_only(
                                        Robot.id, Robot.warehouse_id, Robot.status,
                                        Robot.battery_level, Robot.current_row, Robot.current_shelf,
                                    )).where(Robot.id == rid)
                                )
                                robot = rres.scalar_one_or_none()
                                if robot:
                                    await _safe_finish_scan(s, robot)
                                    await s.flush()
                                    _update_wh_snapshot_from_robot(robot)
                                    await _maybe_emit_positions_snapshot_inmem(robot.warehouse_id)
                    except Exception as e:
                        print(f"⚠️ fast-scan watchdog error (wh={warehouse_id}, rid={rid}): {e}", flush=True)
                    processed += 1
                    continue

                if until and now >= until:
                    try:
                        async with AppSession() as s:
                            async with s.begin():
                                rres = await s.execute(
                                    select(Robot).options(load_only(
                                        Robot.id, Robot.warehouse_id, Robot.status,
                                        Robot.battery_level, Robot.current_row, Robot.current_shelf,
                                    )).where(Robot.id == rid)
                                )
                                robot = rres.scalar_one_or_none()
                                if robot:
                                    await _safe_finish_scan(s, robot)
                                    await s.flush()
                                    _update_wh_snapshot_from_robot(robot)
                                    await _maybe_emit_positions_snapshot_inmem(robot.warehouse_id)
                    except Exception as e:
                        print(f"⚠️ fast-scan error (wh={warehouse_id}, rid={rid}): {e}", flush=True)
                    processed += 1

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass

def _ensure_fast_scan_task_started(warehouse_id: str) -> None:
    if not FAST_SCAN_LOOP:
        return
    if warehouse_id in _WH_FASTSCAN_TASK and not _WH_FASTSCAN_TASK[warehouse_id].done():
        return
    _WH_FASTSCAN_TASK[warehouse_id] = asyncio.create_task(_fast_scan_loop(warehouse_id))

async def _stop_fast_scan_task(warehouse_id: str) -> None:
    t = _WH_FASTSCAN_TASK.pop(warehouse_id, None)
    if t:
        t.cancel()
        try:
            await t
        except Exception:
            pass

# =========================
# POSITIONS BROADCASTER LOOP (строгий период 1–2 секунды)
# =========================
async def _positions_broadcast_loop(warehouse_id: str) -> None:
    """Отправляет robot.positions/robot.positions.diff или keepalive с фиксированным периодом."""
    interval = max(100, POSITIONS_BROADCAST_INTERVAL_MS) / 1000.0
    try:
        while True:
            await asyncio.sleep(interval)
            loop = asyncio.get_running_loop()
            now_mono = loop.time()

            async with _wh_lock(warehouse_id):
                cur_ver = _WH_SNAPSHOT_VER.get(warehouse_id, 0)
                last_sent_ver = _WH_LAST_SENT_VER.get(warehouse_id, -1)
                snap_dict = _wh_snapshot(warehouse_id)
                have_data = bool(snap_dict)
                last_any = _LAST_ANY_SENT_AT.get(warehouse_id, 0.0)
                need_keepalive = (now_mono - last_any) * 1000.0 >= POSITIONS_MAX_INTERVAL_MS
                changed = cur_ver != last_sent_ver

                if not have_data:
                    # нет роботов — ничего не отправляем
                    continue

                payload_ts = datetime.now(timezone.utc).isoformat()

                if changed:
                    if POSITIONS_DIFFS:
                        changed_items, removed = _calc_diff_payload(warehouse_id, snap_dict)
                        if changed_items or removed:
                            await _emit({
                                "type": "robot.positions.diff",
                                "warehouse_id": warehouse_id,
                                "version": cur_ver,
                                "base_version": last_sent_ver,
                                "changed": changed_items,
                                "removed": removed,
                                "ts": payload_ts,
                            })
                            _remember_last_sent_map(warehouse_id, snap_dict)
                            _WH_LAST_SENT_VER[warehouse_id] = cur_ver
                    else:
                        await _emit({
                            "type": "robot.positions",
                            "warehouse_id": warehouse_id,
                            "robots": list(snap_dict.values()),
                            "version": cur_ver,
                            "ts": payload_ts,
                        })
                        _remember_last_sent_map(warehouse_id, snap_dict)
                        _WH_LAST_SENT_VER[warehouse_id] = cur_ver

                    _LAST_POS_BROADCAST_AT[warehouse_id] = now_mono
                    _LAST_ANY_SENT_AT[warehouse_id] = now_mono
                    continue

                if need_keepalive:
                    if POSITIONS_DIFFS and not KEEPALIVE_FULL:
                        await _emit({
                            "type": "robot.positions.keepalive",
                            "warehouse_id": warehouse_id,
                            "version": cur_ver,
                            "robot_count": len(snap_dict),
                            "ts": payload_ts,
                        })
                    else:
                        await _emit({
                            "type": "robot.positions",
                            "warehouse_id": warehouse_id,
                            "robots": list(snap_dict.values()),
                            "version": cur_ver,
                            "ts": payload_ts,
                        })
                        _remember_last_sent_map(warehouse_id, snap_dict)
                        _WH_LAST_SENT_VER[warehouse_id] = cur_ver

                    _LAST_POS_BROADCAST_AT[warehouse_id] = now_mono
                    _LAST_ANY_SENT_AT[warehouse_id] = now_mono
    except asyncio.CancelledError:
        pass

def _ensure_positions_broadcaster_started(warehouse_id: str) -> None:
    if warehouse_id in _WH_POS_TASK and not _WH_POS_TASK[warehouse_id].done():
        return
    _WH_POS_TASK[warehouse_id] = asyncio.create_task(_positions_broadcast_loop(warehouse_id))

async def _stop_positions_broadcaster(warehouse_id: str) -> None:
    t = _WH_POS_TASK.pop(warehouse_id, None)
    if t:
        t.cancel()
        try:
            await t
        except Exception:
            pass

# =========================
# Корректное закрытие AsyncEngine (устраняет segfault при выходе)
# =========================
async def _dispose_async_engine_if_any():
    try:
        # если в проекте объявлен engine явно
        from app.db.session import async_engine as _engine  # подстрой, если модуль другой
    except Exception:
        _engine = getattr(AppSession, "bind", None)
    try:
        if isinstance(_engine, AsyncEngine):
            await _engine.dispose()
    except Exception:
        pass

# =========================
# Цикл склада (single-process helper)
# =========================
async def _run_warehouse(warehouse_id: str) -> None:
    sema = asyncio.Semaphore(ROBOTS_CONCURRENCY)
    tick = 0
    _ensure_fast_scan_task_started(warehouse_id)
    _ensure_positions_broadcaster_started(warehouse_id)
    try:
        while True:
            try:
                async with AppSession() as session:
                    r = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
                    all_robot_ids = list(r.scalars().all())
                if not all_robot_ids:
                    await asyncio.sleep(TICK_INTERVAL)
                    continue

                # Прогрев/первая отсылка
                if all_robot_ids and not _WH_SNAPSHOT.get(warehouse_id):
                    async with AppSession() as s:
                        await _warmup_or_sync_snapshot(s, warehouse_id, all_robot_ids)
                        await _emit_positions_snapshot_force(warehouse_id)

                # Синхронизация состава
                async with AppSession() as s:
                    await _warmup_or_sync_snapshot(s, warehouse_id, all_robot_ids)

                # Выбор окна
                robot_ids = _select_robot_batch(warehouse_id, all_robot_ids)

                tid = _next_tick_id(warehouse_id)

                async def run_one(rid: str):
                    async with sema:
                        async with AppSession() as s:
                            async with s.begin():
                                await _robot_tick(s, rid, tick_id=tid)

                await asyncio.gather(*[run_one(rid) for rid in robot_ids])

                tick += 1
                if tick % 20 == 0:
                    print(f"[{datetime.now().isoformat()}] wh={warehouse_id} tick={tick} robots_tick={len(robot_ids)}/{len(all_robot_ids)}", flush=True)

                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ warehouse loop error (wh={warehouse_id}): {e}", flush=True)
                await asyncio.sleep(0.5)
    finally:
        await _stop_fast_scan_task(warehouse_id)
        await _stop_positions_broadcaster(warehouse_id)

# =========================
# Вотчер (однопроцессный)
# =========================
async def run_robot_watcher() -> None:
    print(f"🚀 watcher started pid={os.getpid()} interval={TICK_INTERVAL}s", flush=True)
    tasks: Dict[str, asyncio.Task] = {}
    try:
        while True:
            try:
                async with AppSession() as session:
                    rows = await session.execute(
                        select(Warehouse.id).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
                    )
                    wh_ids = set(rows.scalars().all())

                # старт новых
                for wid in wh_ids:
                    if wid not in tasks or tasks[wid].done():
                        tasks[wid] = asyncio.create_task(_run_warehouse(wid))

                # стоп исчезнувших
                for wid in list(tasks.keys()):
                    if wid not in wh_ids:
                        tasks[wid].cancel()
                        try:
                            await tasks[wid]
                        except Exception:
                            pass
                        tasks.pop(wid, None)
                        _CLAIMED.pop(wid, None)
                        _WH_SNAPSHOT.pop(wid, None)
                        _WH_SNAPSHOT_VER.pop(wid, None)
                        _WH_LAST_SENT_VER.pop(wid, None)
                        _WH_LAST_SENT_MAP.pop(wid, None)
                        _LAST_POS_BROADCAST_AT.pop(wid, None)
                        _LAST_ANY_SENT_AT.pop(wid, None)
                        _ELIGIBLE_CACHE.pop(wid, None)
                        _WH_TICK_COUNTER.pop(wid, None)
                        _WH_ROBOT_OFFSET.pop(wid, None)
                        _WH_LOCKS.pop(wid, None)
                        await _stop_fast_scan_task(wid)
                        await _stop_positions_broadcaster(wid)

                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ watcher loop error: {e}", flush=True)
                await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        print("🛑 watcher cancelled", flush=True)
    finally:
        for wid, t in list(tasks.items()):
            t.cancel()
            try:
                await t
            except Exception:
                pass
            # на всякий случай остановим сервисные циклы
            await _stop_fast_scan_task(wid)
            await _stop_positions_broadcaster(wid)
        await close_bus_for_current_loop()
        await _dispose_async_engine_if_any()
        print("✅ watcher stopped", flush=True)

# =========================
# Multiprocessing watcher
# =========================
# На Linux чаще стабильнее 'forkserver' (меньше shared-состояния, чем при 'spawn')
MP_START_METHOD = os.getenv("MP_START_METHOD", "forkserver")
MAX_WAREHOUSE_PROCS = int(os.getenv("MAX_WAREHOUSE_PROCS", "0"))  # 0 = без лимита

@dataclass
class _WhProc:
    proc: mp.Process
    stop_evt: mp.Event

async def _list_active_warehouses() -> Set[str]:
    async with AppSession() as session:
        rows = await session.execute(
            select(Warehouse.id).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
        )
        return set(rows.scalars().all())

async def _graceful_wait(condition_fn, timeout: float, poll: float = 0.1) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if condition_fn():
            return True
        await asyncio.sleep(poll)
    return condition_fn()

def _warehouse_process_entry(warehouse_id: str, stop_evt: mp.Event) -> None:
    try:
        asyncio.run(_run_warehouse_until_event(warehouse_id, stop_evt))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"⚠️ worker({warehouse_id}) crashed: {e}", flush=True)
    finally:
        try:
            asyncio.run(close_bus_for_current_loop())
        except Exception:
            pass
        try:
            asyncio.run(_dispose_async_engine_if_any())
        except Exception:
            pass
        print(f"🧹 worker({warehouse_id}) stopped", flush=True)

async def _run_warehouse_until_event(warehouse_id: str, stop_evt: mp.Event) -> None:
    sema = asyncio.Semaphore(ROBOTS_CONCURRENCY)
    tick = 0
    print(f"🏭 worker({warehouse_id}) started pid={os.getpid()} interval={TICK_INTERVAL}s", flush=True)
    _ensure_fast_scan_task_started(warehouse_id)
    _ensure_positions_broadcaster_started(warehouse_id)

    def _stopping() -> bool:
        return stop_evt.is_set()

    try:
        while not _stopping():
            try:
                async with AppSession() as session:
                    r = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
                    all_robot_ids = list(r.scalars().all())
                if not all_robot_ids:
                    await asyncio.sleep(TICK_INTERVAL)
                    continue

                if all_robot_ids and not _WH_SNAPSHOT.get(warehouse_id):
                    async with AppSession() as s:
                        await _warmup_or_sync_snapshot(s, warehouse_id, all_robot_ids)
                        await _emit_positions_snapshot_force(warehouse_id)

                async with AppSession() as s:
                    await _warmup_or_sync_snapshot(s, warehouse_id, all_robot_ids)

                robot_ids = _select_robot_batch(warehouse_id, all_robot_ids)
                tid = _next_tick_id(warehouse_id)

                async def run_one(rid: str):
                    async with sema:
                        async with AppSession() as s:
                            async with s.begin():
                                await _robot_tick(s, rid, tick_id=tid)

                await asyncio.gather(*[run_one(rid) for rid in robot_ids])

                tick += 1
                if tick % 20 == 0:
                    print(f"[{datetime.now().isoformat()}] wh={warehouse_id} tick={tick} robots_tick={len(robot_ids)}/{len(all_robot_ids)}", flush=True)

                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ warehouse loop error (wh={warehouse_id}): {e}", flush=True)
                await asyncio.sleep(0.5)
    finally:
        await _stop_fast_scan_task(warehouse_id)
        await _stop_positions_broadcaster(warehouse_id)
        _CLAIMED.pop(warehouse_id, None)
        _WH_SNAPSHOT.pop(warehouse_id, None)
        _WH_SNAPSHOT_VER.pop(warehouse_id, None)
        _WH_LAST_SENT_VER.pop(warehouse_id, None)
        _WH_LAST_SENT_MAP.pop(warehouse_id, None)
        _LAST_POS_BROADCAST_AT.pop(warehouse_id, None)
        _LAST_ANY_SENT_AT.pop(warehouse_id, None)
        _ELIGIBLE_CACHE.pop(warehouse_id, None)
        _WH_TICK_COUNTER.pop(warehouse_id, None)
        _WH_ROBOT_OFFSET.pop(warehouse_id, None)
        _WH_LOCKS.pop(warehouse_id, None)
        await close_bus_for_current_loop()
        await _dispose_async_engine_if_any()

async def run_robot_watcher_mproc() -> None:
    mp.set_start_method(MP_START_METHOD, force=True)
    print(f"🚀 MP watcher started pid={os.getpid()} method={MP_START_METHOD} interval={TICK_INTERVAL}s", flush=True)

    procs: Dict[str, _WhProc] = {}
    stop = asyncio.Event()

    def _on_signal(sig, _frame=None):
        print(f"🛑 MP watcher got signal {sig}", flush=True)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _on_signal)
        except Exception:
            pass

    try:
        while not stop.is_set():
            try:
                wh_ids = await _list_active_warehouses()

                for wid in sorted(wh_ids):
                    if wid in procs and procs[wid].proc.is_alive():
                        continue
                    if MAX_WAREHOUSE_PROCS > 0 and len([p for p in procs.values() if p.proc.is_alive()]) >= MAX_WAREHOUSE_PROCS:
                        continue
                    stop_evt = mp.Event()
                    p = mp.Process(
                        target=_warehouse_process_entry,
                        args=(wid, stop_evt),
                        name=f"wh-{wid[:6]}",
                        daemon=False,
                    )
                    p.start()
                    procs[wid] = _WhProc(proc=p, stop_evt=stop_evt)
                    print(f"▶️ started worker for wh={wid} pid={p.pid}", flush=True)

                for wid in list(procs.keys()):
                    if wid not in wh_ids:
                        wp = procs.pop(wid, None)
                        if not wp:
                            continue
                        print(f"⏹ stopping worker for gone wh={wid}", flush=True)
                        wp.stop_evt.set()
                        wp.proc.join(timeout=10)
                        if wp.proc.is_alive():
                            print(f"⛔ force terminate wh={wid}", flush=True)
                            wp.proc.terminate()
                            wp.proc.join(timeout=5)

                for wid, wp in list(procs.items()):
                    if not wp.proc.is_alive():
                        procs.pop(wid, None)

                await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"⚠️ MP watcher loop error: {e}", flush=True)
                await asyncio.sleep(0.5)
    finally:
        print("🧹 MP watcher shutting down...", flush=True)
        for wid, wp in list(procs.items()):
            try:
                wp.stop_evt.set()
            except Exception:
                pass
        await _graceful_wait(lambda: all(not wp.proc.is_alive() for wp in procs.values()), timeout=12.0, poll=0.2)
        for wid, wp in list(procs.items()):
            if wp.proc.is_alive():
                print(f"⛔ force terminate wh={wid}", flush=True)
                wp.proc.terminate()
        for wid, wp in list(procs.items()):
            try:
                wp.proc.join(timeout=3)
            except Exception:
                pass
        await close_bus_for_current_loop()
        await _dispose_async_engine_if_any()
        print("✅ MP watcher stopped", flush=True)
