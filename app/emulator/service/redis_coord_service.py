from __future__ import annotations
import json
from typing import Optional, Tuple, List, Dict
from app.emulator.config import (
    USE_REDIS_COORD, USE_REDIS_CLAIMS, REDIS_URL, CLAIM_TTL_MS, LAST_SCANS_LIMIT
)
try:
    from redis import asyncio as aioredis
except Exception:  # redis не обязателен
    aioredis = None  # type: ignore

_pool = None

async def get_redis():
    global _pool
    if not (USE_REDIS_COORD or USE_REDIS_CLAIMS):
        return None
    if aioredis is None:
        raise RuntimeError("redis[async] не установлен, а USE_REDIS_* = 1")
    if _pool is None:
        _pool = await aioredis.from_url(REDIS_URL, decode_responses=True)
    return _pool

async def close_redis():
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        finally:
            _pool = None

def claim_key(wid: str, x: int, y: int) -> str:
    return f"wh:{wid}:claim:{x}:{y}"

def robots_hash_key(wid: str) -> str:
    return f"wh:{wid}:robots"

def robots_ver_key(wid: str) -> str:
    return f"wh:{wid}:robots:ver"

def robots_last_sent_map_key(wid: str) -> str:
    return f"wh:{wid}:robots:lastsent"

def last_scans_key(wid: str) -> str:
    return f"wh:{wid}:lastscans"

async def claim_global(wid: str, cell: Tuple[int, int]) -> bool:
    if not USE_REDIS_CLAIMS:
        return True
    r = await get_redis()
    x, y = cell
    ok = await r.set(claim_key(wid, x, y), "1", nx=True, px=CLAIM_TTL_MS)
    return bool(ok)

async def free_claim_global(wid: str, cell: Tuple[int, int]) -> None:
    if not USE_REDIS_CLAIMS:
        return
    r = await get_redis()
    x, y = cell
    await r.delete(claim_key(wid, x, y))
