from __future__ import annotations
import os
from datetime import timedelta

# === Segfault hardening (ранний setenv)
os.environ.setdefault("SQLALCHEMY_DISABLE_CEXT", "1")
os.environ.setdefault("GREENLET_USE_GC", "0")
EMIT_AUTOSEND_INIT = os.environ.setdefault("EMIT_AUTOSEND_INIT", "1") == "0"

# --- Координация/бронь
USE_REDIS_COORD  = os.getenv("USE_REDIS_COORD", "1") == "1"
USE_REDIS_CLAIMS = os.getenv("USE_REDIS_CLAIMS", "1") == "1"
REDIS_URL = os.getenv("REDIS_URL", "redis://myapp-redis:6379/0")
CLAIM_TTL_MS = int(os.getenv("CLAIM_TTL_MS", "120000"))
COORDINATOR_SHARD_INDEX = int(os.getenv("COORDINATOR_SHARD_INDEX", "0"))

# --- Поле/ось
FIELD_X = 26
FIELD_Y = 50
DOCK_X, DOCK_Y = 0, 0

# --- Тайминги/порогa
TICK_INTERVAL = float(os.getenv("ROBOT_TICK_INTERVAL", "0.5"))
SCAN_DURATION = timedelta(seconds=int(os.getenv("SCAN_DURATION_SEC", "6")))
RESCAN_COOLDOWN = timedelta(seconds=int(os.getenv("RESCAN_COOLDOWN_SEC", "120")))
CHARGE_DURATION = timedelta(seconds=int(os.getenv("CHARGE_DURATION_SEC", "45")))
LOW_BATTERY_THRESHOLD = float(os.getenv("LOW_BATTERY_THRESHOLD", "15"))
BATTERY_DROP_PER_STEP = float(os.getenv("BATTERY_DROP_PER_STEP", "0.6"))

POSITION_RATE_LIMIT_PER_ROBOT = float(os.getenv("POSITION_RATE_LIMIT_SEC", "0.25"))
ROBOTS_CONCURRENCY = int(os.getenv("ROBOT_CONCURRENCY", "12"))

# --- Позиции/шина
POSITIONS_MIN_INTERVAL_MS = int(os.getenv("POSITIONS_MIN_INTERVAL_MS", "75"))
POSITIONS_KEEPALIVE_MS = int(os.getenv("POSITIONS_KEEPALIVE_MS", "1000"))
KEEPALIVE_FULL = os.getenv("KEEPALIVE_FULL", "1") == "1"
POSITIONS_DIFFS = os.getenv("POSITIONS_DIFFS", "0") == "1"
SEND_ROBOT_POSITION = os.getenv("SEND_ROBOT_POSITION", "1") == "0"
POSITIONS_BROADCAST_INTERVAL_MS = int(os.getenv("POSITIONS_BROADCAST_INTERVAL_MS", "1000"))
POSITIONS_MAX_INTERVAL_MS = int(os.getenv("POSITIONS_MAX_INTERVAL_MS", "2000"))

# --- Логика поиска целей
IDLE_GOAL_LOOKUP_EVERY = int(os.getenv("IDLE_GOAL_LOOKUP_EVERY", "2"))
ROBOTS_PER_TICK = int(os.getenv("ROBOTS_PER_TICK", "256"))

# --- Fast scanner
FAST_SCAN_LOOP = os.getenv("FAST_SCAN_LOOP", "1") == "1"
FAST_SCAN_INTERVAL_MS = int(os.getenv("FAST_SCAN_INTERVAL_MS", "75"))
FAST_SCAN_MAX_PER_TICK = int(os.getenv("FAST_SCAN_MAX_PER_TICK", "512"))
SCAN_MAX_DURATION_MS = int(os.getenv(
    "SCAN_MAX_DURATION_MS",
    str(int(max(1.0, SCAN_DURATION.total_seconds()) * 3000))
))

# --- Последние сканы
LAST_SCANS_LIMIT = int(os.getenv("LAST_SCANS_LIMIT", "20"))

# --- Multiprocessing
MP_START_METHOD = os.getenv("MP_START_METHOD", "forkserver")
MAX_WAREHOUSE_PROCS = int(os.getenv("MAX_WAREHOUSE_PROCS", "0"))
ROBOTS_PER_PROC = int(os.getenv("ROBOTS_PER_PROC", "3"))
