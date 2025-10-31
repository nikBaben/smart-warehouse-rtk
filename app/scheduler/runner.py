# app/scheduler/runner.py
from __future__ import annotations

import time
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.scheduler.config import Config
from app.scheduler.jobs import create_shipment_job
from app.scheduler.jobs.materialize_scheduled_deliveries import run as deliveries_job

log = logging.getLogger("scheduler.runner")

def run_once(cfg: Config) -> None:
    engine = create_engine(cfg.database_url, pool_pre_ping=True, future=True)
    with Session(engine) as session:
        create_shipment_job(session, cfg)

def loop(cfg: Config) -> None:
    # новые: отдельные интервалы
    shipments_interval = getattr(cfg, "interval_sec", 60)  # например, 60 сек для отгрузок
    deliveries_interval = getattr(cfg, "deliveries_interval_sec", 900)  # 15 минут по умолчанию

    log.info(
        "Старт планировщика. Интервалы: shipments=%s сек, deliveries=%s сек.",
        shipments_interval, deliveries_interval
    )

    engine = create_engine(cfg.database_url, pool_pre_ping=True, future=True)

    next_shipments = time.monotonic()
    next_deliveries = time.monotonic()

    while True:
        now = time.monotonic()
        try:
            with Session(engine) as session:
                # запускаем каждую задачу, когда подошло её время
                if now >= next_shipments:
                    create_shipment_job(session, cfg)
                    next_shipments = now + shipments_interval

                if now >= next_deliveries:
                    created = deliveries_job(session, cfg)
                    if created:
                        log.info("Materialized %s scheduled deliveries.", created)
                    next_deliveries = now + deliveries_interval

        except Exception as e:
            log.exception("Ошибка выполнения задачи: %s", e)

        if cfg.run_once:
            break

        # короткий сон, чтобы не жечь CPU (подстройка под ближайший дедлайн)
        sleep_for = min(next_shipments, next_deliveries) - time.monotonic()
        if sleep_for > 0:
            time.sleep(min(sleep_for, 1.0))  # спим до секунды за цикл
