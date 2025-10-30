from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import json
from app.emulator.config import (
    USE_REDIS_COORD, POSITIONS_MIN_INTERVAL_MS, POSITIONS_KEEPALIVE_MS,
    KEEPALIVE_FULL, POSITIONS_DIFFS, POSITIONS_BROADCAST_INTERVAL_MS,
    POSITIONS_MAX_INTERVAL_MS, COORDINATOR_SHARD_INDEX
)
from app.emulator.service.state_service import (
    wh_lock, wh_snapshot, WH_SNAPSHOT_VER, WH_LAST_SENT_VER, LAST_POS_BROADCAST_AT,
    LAST_ANY_SENT_AT, last_sent_map, ROBOT_WH
)
from app.emulator.service.redis_coord_service import robots_hash_key, robots_ver_key, robots_last_sent_map_key, get_redis
from app.emulator.service.events_service import emit

def _calc_diff_payload(wid: str, snap: Dict[str, dict]):
    last = last_sent_map(wid)
    changed, removed = [], []
    for rid, item in snap.items():
        if last.get(rid) != item:
            changed.append(item)
    for rid in list(last.keys()):
        if rid not in snap:
            removed.append(rid)
    return changed, removed

def _remember_last_sent_map(wid: str, snap: Dict[str, dict]) -> None:
    l = last_sent_map(wid)
    l.clear()
    l.update({rid: dict(item) for rid, item in snap.items()})

async def maybe_emit_positions_snapshot_inmem(warehouse_id: str) -> None:
    if USE_REDIS_COORD:
        return
    loop = asyncio.get_running_loop()
    now_mono = loop.time()
    need_keepalive = (now_mono - LAST_ANY_SENT_AT.get(warehouse_id, 0.0)) * 1000.0 >= POSITIONS_KEEPALIVE_MS
    rl_ok = (now_mono - LAST_POS_BROADCAST_AT.get(warehouse_id, 0.0)) * 1000.0 >= POSITIONS_MIN_INTERVAL_MS

    async with wh_lock(warehouse_id):
        cur_ver = WH_SNAPSHOT_VER.get(warehouse_id, 0)
        last_sent_ver = WH_LAST_SENT_VER.get(warehouse_id, -1)
        snap_dict = wh_snapshot(warehouse_id)
        has_changes = cur_ver != last_sent_ver
        have_data = bool(snap_dict)

        if not have_data and not need_keepalive:
            return

        if has_changes and rl_ok and have_data:
            ts = datetime.now(timezone.utc).isoformat()
            if POSITIONS_DIFFS:
                changed, removed = _calc_diff_payload(warehouse_id, snap_dict)
                if changed or removed:
                    await emit({
                        "type": "robot.positions.diff",
                        "warehouse_id": warehouse_id,
                        "version": cur_ver,
                        "base_version": last_sent_ver,
                        "changed": changed,
                        "removed": removed,
                        "ts": ts,
                    })
                    _remember_last_sent_map(warehouse_id, snap_dict)
                    WH_LAST_SENT_VER[warehouse_id] = cur_ver
                    LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
                    LAST_ANY_SENT_AT[warehouse_id] = LAST_POS_BROADCAST_AT[warehouse_id]
                    return
            await emit({
                "type": "robot.positions",
                "warehouse_id": warehouse_id,
                "robots": list(snap_dict.values()),
                "version": cur_ver,
                "ts": ts,
            })
            _remember_last_sent_map(warehouse_id, snap_dict)
            WH_LAST_SENT_VER[warehouse_id] = cur_ver
            LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
            LAST_ANY_SENT_AT[warehouse_id] = LAST_POS_BROADCAST_AT[warehouse_id]
            return

        if need_keepalive:
            ts = datetime.now(timezone.utc).isoformat()
            if POSITIONS_DIFFS and not KEEPALIVE_FULL:
                await emit({
                    "type": "robot.positions.keepalive",
                    "warehouse_id": warehouse_id,
                    "version": cur_ver,
                    "robot_count": len(snap_dict),
                    "ts": ts,
                })
            else:
                await emit({
                    "type": "robot.positions",
                    "warehouse_id": warehouse_id,
                    "robots": list(snap_dict.values()),
                    "version": cur_ver,
                    "ts": ts,
                })
                _remember_last_sent_map(warehouse_id, snap_dict)
                WH_LAST_SENT_VER[warehouse_id] = cur_ver
                LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
            LAST_ANY_SENT_AT[warehouse_id] = loop.time()

async def emit_positions_snapshot_force(warehouse_id: str) -> None:
    if USE_REDIS_COORD:
        return
    async with wh_lock(warehouse_id):
        snap_dict = wh_snapshot(warehouse_id)
        payload = list(snap_dict.values())
        cur_ver = WH_SNAPSHOT_VER.get(warehouse_id, 0)
    if not payload:
        return
    await emit({
        "type": "robot.positions",
        "warehouse_id": warehouse_id,
        "robots": payload,
        "version": cur_ver,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    loop = asyncio.get_running_loop()
    _remember_last_sent_map(warehouse_id, snap_dict)
    WH_LAST_SENT_VER[warehouse_id] = cur_ver
    LAST_POS_BROADCAST_AT[warehouse_id] = loop.time()
    LAST_ANY_SENT_AT[warehouse_id] = LAST_POS_BROADCAST_AT[warehouse_id]

async def positions_broadcast_loop(warehouse_id: str, shard_idx: int, shard_count: int) -> None:
    """Широковещатель позиций (строго периодический)."""
    interval = max(100, POSITIONS_BROADCAST_INTERVAL_MS) / 1000.0
    try:
        while True:
            await asyncio.sleep(interval)

            if USE_REDIS_COORD:
                if shard_idx != COORDINATOR_SHARD_INDEX:
                    continue
                r = await get_redis()
                hkey = robots_hash_key(warehouse_id)
                ver_key = robots_ver_key(warehouse_id)
                lastsent_key = robots_last_sent_map_key(warehouse_id)

                data = await r.hgetall(hkey)
                if not data:
                    continue
                robots = []
                for _, s in data.items():
                    try:
                        robots.append(json.loads(s))
                    except Exception:
                        pass

                cur_ver = int(await r.incr(ver_key))
                ts = datetime.now(timezone.utc).isoformat()

                if POSITIONS_DIFFS:
                    last_json = await r.get(lastsent_key)
                    last_map = {}
                    if last_json:
                        try:
                            last_map = json.loads(last_json)
                        except Exception:
                            last_map = {}
                    cur_map = {item["robot_id"]: item for item in robots}
                    changed = [v for k, v in cur_map.items() if last_map.get(k) != v]
                    removed = [k for k in last_map.keys() if k not in cur_map]
                    if changed or removed:
                        await emit({
                            "type": "robot.positions.diff",
                            "warehouse_id": warehouse_id,
                            "version": cur_ver,
                            "base_version": cur_ver - 1,
                            "changed": changed,
                            "removed": removed,
                            "ts": ts,
                        })
                        await r.set(lastsent_key, json.dumps(cur_map))
                else:
                    await emit({
                        "type": "robot.positions",
                        "warehouse_id": warehouse_id,
                        "robots": robots,
                        "version": cur_ver,
                        "ts": ts,
                    })
                    await r.set(lastsent_key, json.dumps({x["robot_id"]: x for x in robots}))
                continue

            # локальный режим
            loop = asyncio.get_running_loop()
            now_mono = loop.time()
            async with wh_lock(warehouse_id):
                cur_ver = WH_SNAPSHOT_VER.get(warehouse_id, 0)
                last_sent_ver = WH_LAST_SENT_VER.get(warehouse_id, -1)
                snap_dict = wh_snapshot(warehouse_id)
                have_data = bool(snap_dict)
                last_any = LAST_ANY_SENT_AT.get(warehouse_id, 0.0)
                need_keepalive = (now_mono - last_any) * 1000.0 >= POSITIONS_MAX_INTERVAL_MS
                changed = cur_ver != last_sent_ver
                if not have_data:
                    continue

                ts = datetime.now(timezone.utc).isoformat()
                if changed:
                    if POSITIONS_DIFFS:
                        changed_items, removed = _calc_diff_payload(warehouse_id, snap_dict)
                        if changed_items or removed:
                            await emit({
                                "type": "robot.positions.diff",
                                "warehouse_id": warehouse_id,
                                "version": cur_ver,
                                "base_version": last_sent_ver,
                                "changed": changed_items,
                                "removed": removed,
                                "ts": ts,
                            })
                            _remember_last_sent_map(warehouse_id, snap_dict)
                            WH_LAST_SENT_VER[warehouse_id] = cur_ver
                    else:
                        await emit({
                            "type": "robot.positions",
                            "warehouse_id": warehouse_id,
                            "robots": list(snap_dict.values()),
                            "version": cur_ver,
                            "ts": ts,
                        })
                        _remember_last_sent_map(warehouse_id, snap_dict)
                        WH_LAST_SENT_VER[warehouse_id] = cur_ver
                    LAST_POS_BROADCAST_AT[warehouse_id] = now_mono
                    LAST_ANY_SENT_AT[warehouse_id] = now_mono
                    continue

                if need_keepalive:
                    if POSITIONS_DIFFS and not KEEPALIVE_FULL:
                        await emit({
                            "type": "robot.positions.keepalive",
                            "warehouse_id": warehouse_id,
                            "version": cur_ver,
                            "robot_count": len(snap_dict),
                            "ts": ts,
                        })
                    else:
                        await emit({
                            "type": "robot.positions",
                            "warehouse_id": warehouse_id,
                            "robots": list(snap_dict.values()),
                            "version": cur_ver,
                            "ts": ts,
                        })
                        _remember_last_sent_map(warehouse_id, snap_dict)
                        WH_LAST_SENT_VER[warehouse_id] = cur_ver
                    LAST_POS_BROADCAST_AT[warehouse_id] = now_mono
                    LAST_ANY_SENT_AT[warehouse_id] = now_mono
    except asyncio.CancelledError:
        pass
