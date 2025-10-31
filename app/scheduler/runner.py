# app/scheduler/runner.py
from __future__ import annotations

import time
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.scheduler.config import Config
from app.scheduler.jobs import create_shipment_job

log = logging.getLogger("scheduler.runner")


def run_once(cfg: Config) -> None:
    engine = create_engine(cfg.database_url, pool_pre_ping=True, future=True)
    with Session(engine) as session:
        create_shipment_job(session, cfg)


def loop(cfg: Config) -> None:
    log.info("Старт планировщика. Интервал: %s сек.", cfg.interval_sec)
    engine = create_engine(cfg.database_url, pool_pre_ping=True, future=True)

    while True:
        try:
            with Session(engine) as session:
                create_shipment_job(session, cfg)
        except Exception as e:
            log.exception("Ошибка выполнения задачи: %s", e)

        if cfg.run_once:
            break

        time.sleep(cfg.interval_sec)
