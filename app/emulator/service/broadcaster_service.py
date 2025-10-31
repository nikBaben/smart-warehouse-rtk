import asyncio
from app.emulator.service.positions_service import positions_broadcast_loop

_TASKS = {}

def ensure_positions_broadcaster_started(warehouse_id: str, shard_idx: int, shard_count: int) -> None:
    if warehouse_id in _TASKS and not _TASKS[warehouse_id].done():
        return
    _TASKS[warehouse_id] = asyncio.create_task(positions_broadcast_loop(warehouse_id, shard_idx, shard_count))

async def stop_positions_broadcaster(warehouse_id: str) -> None:
    t = _TASKS.pop(warehouse_id, None)
    if t:
        t.cancel()
        try:
            await t
        except Exception:
            pass
