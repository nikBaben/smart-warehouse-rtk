from __future__ import annotations
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Set, List

from sqlalchemy import select
from sqlalchemy.orm import load_only
from app.models.robot import Robot
from app.emulator.service.coords_service import clamp_xy
from app.emulator.service.scanning_service import _log_robot_status

from app.emulator.config import (
    DOCK_X, DOCK_Y, TICK_INTERVAL, CHARGE_DURATION, LOW_BATTERY_THRESHOLD,
    BATTERY_DROP_PER_STEP, RESCAN_COOLDOWN,SCAN_MAX_DURATION_MS, IDLE_GOAL_LOOKUP_EVERY
)
from app.emulator.service.coords_service import clamp_xy, manhattan, shelf_num_to_str
from app.emulator.service.state_service import (
    update_wh_snapshot_from_robot, TARGETS, wh_lock, get_tick_cache,
    next_tick_id, ROBOT_WH, SCANNING_UNTIL, SCANNING_STARTED_AT
)
from app.emulator.service.eligibility_service import eligible_cells, eligible_products_in_cell, cell_still_eligible
from app.emulator.service.redis_coord_service import claim_global, free_claim_global
from app.emulator.service.events_service import emit_position_if_needed
from app.emulator.service.positions_service import maybe_emit_positions_snapshot_inmem
from app.emulator.service.scanning_service import start_scan, safe_finish_scan

def robot_xy(robot: Robot) -> tuple[int, int]:
    return int(robot.current_shelf or 0), int(robot.current_row or 0)

def set_robot_xy(robot: Robot, x: int, y: int) -> None:
    robot.current_shelf = int(x or 0)
    robot.current_row = int(y or 0)

async def robot_tick(session, robot_id: str, tick_id: Optional[int] = None) -> None:
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

    ROBOT_WH[robot.id] = robot.warehouse_id
    wid = robot.warehouse_id
    tid = tick_id or next_tick_id(wid)
    cache = get_tick_cache(wid, tid)
    cutoff = datetime.now(timezone.utc) - RESCAN_COOLDOWN
    cache["cutoff"] = cutoff

    # 1) Сканируем?
    if (robot.status or "").lower() == "scanning":
        if robot.id not in SCANNING_UNTIL:
            now = datetime.now(timezone.utc)
            SCANNING_STARTED_AT[robot.id] = now
            SCANNING_UNTIL[robot.id] = now  # немедленно готов к завершению (fast-loop обработает)
        # если fast-loop выключен — watchdog завершаем здесь
        start_at = SCANNING_STARTED_AT.get(robot.id)
        now_dt = datetime.now(timezone.utc)
        if start_at and (now_dt - start_at).total_seconds() * 1000.0 > SCAN_MAX_DURATION_MS:
            await safe_finish_scan(session, robot)
            await session.flush()
            update_wh_snapshot_from_robot(robot)
            await maybe_emit_positions_snapshot_inmem(robot.warehouse_id)
            return

        until = SCANNING_UNTIL.get(robot.id)
        if until and now_dt >= until:
            await safe_finish_scan(session, robot)
            await session.flush()
            update_wh_snapshot_from_robot(robot)
            await emit_position_if_needed(robot)
            await maybe_emit_positions_snapshot_inmem(robot.warehouse_id)
        return

    # 2) Зарядка?
    if (robot.status or "").lower() == "charging":
        inc = 100.0 * (TICK_INTERVAL / CHARGE_DURATION.total_seconds())
        robot.battery_level = min(100.0, float(robot.battery_level or 0.0) + inc)
        if float(robot.battery_level) >= 100.0:
            robot.status = "idle"
        await session.flush()
        update_wh_snapshot_from_robot(robot)
        await emit_position_if_needed(robot)
        await maybe_emit_positions_snapshot_inmem(wid)
        return

    # 3) Поиск/поддержание цели
    cur = robot_xy(robot)
    goal = TARGETS.get(robot.id)

    if float(robot.battery_level or 0.0) <= LOW_BATTERY_THRESHOLD:
        if goal:
            await free_claim_global(wid, goal)
            TARGETS.pop(robot.id, None)
        goal = (DOCK_X, DOCK_Y)
    else:
        if goal is not None:
            still_ok = await cell_still_eligible(session, wid, goal, cutoff)
            if not still_ok:
                await free_claim_global(wid, goal)
                TARGETS.pop(robot.id, None); goal = None
        if goal is None:
            if tid % IDLE_GOAL_LOOKUP_EVERY == 0:
                if cache["cells"] is None:
                    cache["cells"] = await eligible_cells(session, wid, cutoff)
                cells = cache["cells"] or []
                if cells:
                    claimed_local = set()  # глобальная бронь через Redis; локальная кэш не используем
                    local_sel: set[tuple[int, int]] = cache["local_selected"]
                    best, best_d = None, None
                    for c in cells:
                        if c in local_sel:
                            continue
                        d = manhattan(cur, c)
                        if best_d is None or d < best_d:
                            best_d, best = d, c
                    if best is not None:
                        async with wh_lock(wid):
                            cache_now = get_tick_cache(wid, tid)
                            local_sel_now: set[tuple[int,int]] = cache_now["local_selected"]
                            if best not in local_sel_now and await claim_global(wid, best):
                                local_sel_now.add(best)
                                TARGETS[robot.id] = best
                                goal = best

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
        valid = [(x, y) for (x, y) in cand if 1 <= x and 0 <= y]  # простая валидация; clamp ниже
        nx, ny = random.choice(valid) if valid else (cur_x, cur_y)
    nx, ny = clamp_xy(nx, ny)

    moved = (nx, ny) != (cur_x, cur_y)
    if moved:
        robot.battery_level = max(0.0, float(robot.battery_level or 0.0) - BATTERY_DROP_PER_STEP)

    # Разряжен — к доку
    if float(robot.battery_level or 0.0) <= 0.0:
        set_robot_xy(robot, DOCK_X, DOCK_Y)
        robot.status = "charging"
        if goal and goal != (DOCK_X, DOCK_Y):
            await free_claim_global(wid, goal)
        TARGETS.pop(robot.id, None)
        await session.flush()
        update_wh_snapshot_from_robot(robot)
        await _log_robot_status(session, robot, "charging")
        await emit_position_if_needed(robot)
        await maybe_emit_positions_snapshot_inmem(wid)
        return

    set_robot_xy(robot, nx, ny)
    robot.status = "idle"
    await session.flush()
    update_wh_snapshot_from_robot(robot)
    await emit_position_if_needed(robot)
    await maybe_emit_positions_snapshot_inmem(wid)

    if (nx, ny) == (DOCK_X, DOCK_Y) and float(robot.battery_level) < 100.0:
        robot.status = "charging"
        if goal and goal != (DOCK_X, DOCK_Y):
            await free_claim_global(wid, goal)
        TARGETS.pop(robot.id, None)
        await session.flush()
        update_wh_snapshot_from_robot(robot)
        await maybe_emit_positions_snapshot_inmem(wid)
        return

    if goal and (nx, ny) == goal:
        key = (nx, ny)
        if key not in cache["by_cell"]:
            cache["by_cell"][key] = await eligible_products_in_cell(session, wid, nx, ny, cutoff)
        eligible_now = cache["by_cell"][key]
        if eligible_now:
            await start_scan(robot, nx, ny)
            await _log_robot_status(session, robot, "scanning")
        else:
            await free_claim_global(wid, goal)
        TARGETS.pop(robot.id, None)
        await session.flush()
        update_wh_snapshot_from_robot(robot)
        await maybe_emit_positions_snapshot_inmem(wid)
