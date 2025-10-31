from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Dict, Set, Tuple, Optional
from app.emulator.service.coords_service import shelf_num_to_str
from app.emulator.config import POSITION_RATE_LIMIT_PER_ROBOT

# ===== Память процесса
TARGETS: Dict[str, Tuple[int, int]] = {}
SCANNING_UNTIL: Dict[str, datetime] = {}
SCANNING_CELL: Dict[str, Tuple[int, int]] = {}
SCANNING_STARTED_AT: Dict[str, datetime] = {}
LAST_POS_SENT_AT: Dict[str, datetime] = {}
CLAIMED: Dict[str, Set[Tuple[int, int]]] = {}

WH_SNAPSHOT: Dict[str, Dict[str, dict]] = {}
WH_SNAPSHOT_VER: Dict[str, int] = {}
WH_LAST_SENT_VER: Dict[str, int] = {}
WH_LAST_SENT_MAP: Dict[str, Dict[str, dict]] = {}
LAST_POS_BROADCAST_AT: Dict[str, float] = {}
LAST_ANY_SENT_AT: Dict[str, float] = {}
WH_LOCKS: Dict[str, asyncio.Lock] = {}

ELIGIBLE_CACHE: Dict[str, dict] = {}
WH_TICK_COUNTER: Dict[str, int] = {}
ROBOT_WH: Dict[str, str] = {}
WH_ROBOT_OFFSET: Dict[str, int] = {}

SCANNING_FINISHING: Dict[str, bool] = {}
SCAN_LOCKS: Dict[str, asyncio.Lock] = {}

def scan_lock(rid: str) -> asyncio.Lock:
    lk = SCAN_LOCKS.get(rid)
    if lk is None:
        lk = SCAN_LOCKS[rid] = asyncio.Lock()
    return lk

def wh_lock(wid: str) -> asyncio.Lock:
    lk = WH_LOCKS.get(wid)
    if lk is None:
        lk = WH_LOCKS[wid] = asyncio.Lock()
    return lk

def wh_snapshot(wid: str) -> Dict[str, dict]:
    return WH_SNAPSHOT.setdefault(wid, {})

def last_sent_map(wid: str) -> Dict[str, dict]:
    return WH_LAST_SENT_MAP.setdefault(wid, {})

def next_tick_id(wid: str) -> int:
    WH_TICK_COUNTER[wid] = WH_TICK_COUNTER.get(wid, 0) + 1
    return WH_TICK_COUNTER[wid]

def get_tick_cache(wid: str, tid: int) -> dict:
    c = ELIGIBLE_CACHE.get(wid)
    if not c or c.get("tick_id") != tid:
        c = ELIGIBLE_CACHE[wid] = {
            "cells": None, "by_cell": {}, "cutoff": None,
            "tick_id": tid, "local_selected": set(),
        }
    return c

def update_wh_snapshot_from_robot(robot) -> None:
    wh = robot.warehouse_id
    ROBOT_WH[robot.id] = wh
    x_int, y_int = int(robot.current_shelf or 0), int(robot.current_row or 0)
    now_iso = datetime.now(timezone.utc).isoformat()
    base = {
        "robot_id": robot.id,
        "x": x_int, "y": y_int,
        "shelf": shelf_num_to_str(x_int),
        "battery_level": round(float(robot.battery_level or 0.0), 1),
        "status": (robot.status or "idle"),
    }
    snap = wh_snapshot(wh)
    old_item = snap.get(robot.id) or {}
    changed = {k: old_item.get(k) for k in base} != base
    updated_at = now_iso if changed else (old_item.get("updated_at") or now_iso)
    new_item = dict(base, updated_at=updated_at)
    if old_item != new_item:
        snap[robot.id] = new_item
        WH_SNAPSHOT_VER[wh] = WH_SNAPSHOT_VER.get(wh, 0) + 1

def should_emit_position(robot) -> bool:
    now = datetime.now(timezone.utc)
    last = LAST_POS_SENT_AT.get(robot.id, datetime.fromtimestamp(0, tz=timezone.utc))
    if (now - last).total_seconds() < POSITION_RATE_LIMIT_PER_ROBOT:
        return False
    LAST_POS_SENT_AT[robot.id] = now
    return True

# --- кэш "самых протухших" клеток по складу ---
# wid -> {"data": list[tuple[int,int,float]], "until": float}
STALE_CELLS_CACHE: Dict[str, dict] = {}

def get_stale_cells_from_cache(wid: str):
    rec = STALE_CELLS_CACHE.get(wid)
    if not rec:
        return None
    if asyncio.get_running_loop().time() <= rec.get("until", 0.0):
        return rec.get("data")
    return None

def put_stale_cells_to_cache(wid: str, data, ttl_sec: float = 1.0):
    STALE_CELLS_CACHE[wid] = {
        "data": data,
        "until": asyncio.get_running_loop().time() + ttl_sec
    }
