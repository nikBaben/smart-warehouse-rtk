# app/scheduler/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timezone
from app.models.enums import ShipmentStatus


@dataclass(frozen=True)
class Config:
    database_url: str
    interval_sec: int
    item_qty_default: int
    shipment_name_prefix: str
    shipment_status: ShipmentStatus
    timezone: timezone
    run_once: bool


def load_config() -> Config:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/myapp",
    )
    interval_sec = int(os.getenv("SCHEDULER_INTERVAL_SEC", "600"))
    item_qty_default = int(os.getenv("SHIPMENT_ITEM_QTY", "1"))
    shipment_name_prefix = os.getenv("SHIPMENT_NAME_PREFIX", "Auto shipment")
    status_name = os.getenv("SHIPMENT_STATUS", "scheduled")

    try:
        shipment_status = ShipmentStatus[status_name]
    except Exception:
        shipment_status = ShipmentStatus.scheduled

    run_once = os.getenv("RUN_ONCE", "0") == "1"

    # можно заменить на локальную TZ, если нужно
    tz = timezone.utc

    return Config(
        database_url=database_url,
        interval_sec=interval_sec,
        item_qty_default=item_qty_default,
        shipment_name_prefix=shipment_name_prefix,
        shipment_status=shipment_status,
        timezone=tz,
        run_once=run_once,
    )
