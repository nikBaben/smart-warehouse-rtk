from typing import List
from state_service import SCANNING_UNTIL, WH_ROBOT_OFFSET, wh_snapshot
from config import ROBOTS_PER_TICK

def is_scanning_in_snapshot(warehouse_id: str, rid: str) -> bool:
    item = wh_snapshot(warehouse_id).get(rid)
    return bool(item and (item.get("status") or "").lower() == "scanning")

def select_robot_batch(warehouse_id: str, robot_ids: List[str]) -> List[str]:
    if not robot_ids:
        return []
    scanning = [rid for rid in robot_ids if (rid in SCANNING_UNTIL) or is_scanning_in_snapshot(warehouse_id, rid)]
    scanning_set = set(scanning)
    normal = [rid for rid in robot_ids if rid not in scanning_set]

    win = max(ROBOTS_PER_TICK - len(scanning), 0)
    if win <= 0:
        return scanning
    n = len(normal)
    if n == 0:
        return scanning

    off = WH_ROBOT_OFFSET.get(warehouse_id, 0) % n
    if off + win <= n:
        batch = normal[off:off + win]
    else:
        batch = normal[off:] + normal[:(off + win) % n]
    WH_ROBOT_OFFSET[warehouse_id] = (off + win) % n
    return scanning + batch
