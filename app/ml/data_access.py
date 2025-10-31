# app/ml/data_access.py
from __future__ import annotations
from typing import Optional, List, Dict
from datetime import datetime
import pandas as pd
from sqlalchemy import select

from app.db.session import async_session
from app.models.inventory_history import InventoryHistory
from app.models.shipment import ShipmentItems
from app.models.delivery import ScheduledDelivery
from app.models.delivery_items import DeliveryItems

__all__ = [
    "fetch_snapshot_at",
    "fetch_planned_incoming",
    "fetch_outgoing_timeseries",
]

def _ensure_dt64(df: pd.DataFrame, col: str):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col])
    return df

async def fetch_snapshot_at(product_id: str, warehouse_id: Optional[str], at_time: datetime) -> Optional[float]:
    """Последний снимок остатков ≤ at_time."""
    async with async_session() as session:
        stmt = select(InventoryHistory).where(InventoryHistory.product_id == product_id)
        if warehouse_id:
            stmt = stmt.where(InventoryHistory.warehouse_id == warehouse_id)
        stmt = stmt.where(InventoryHistory.created_at <= at_time).order_by(InventoryHistory.created_at.desc())
        row = (await session.execute(stmt)).scalars().first()
    if not row:
        return None
    return float(row.stock) if row.stock is not None else None

async def fetch_outgoing_timeseries(
    product_id: str,
    warehouse_id: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    freq: str = "D",
) -> pd.DataFrame:
    """Собирает ряд исходящих: ds, y — из shipment_items → shipments."""
    async with async_session() as session:
        stmt = select(ShipmentItems).where(ShipmentItems.product_id == product_id)
        if warehouse_id:
            stmt = stmt.where(ShipmentItems.warehouse_id == warehouse_id)
        if start:
            stmt = stmt.where(ShipmentItems.created_at >= start)
        if end:
            stmt = stmt.where(ShipmentItems.created_at <= end)
        rows = (await session.execute(stmt)).scalars().all()

    recs = []
    for r in rows:
        ts = r.shipment.shipped_at if (r.shipment and getattr(r.shipment, "shipped_at", None)) else r.created_at
        if ts:
            recs.append({"ts": pd.to_datetime(ts), "outgoing": float(r.fact_quantity or 0)})

    if not recs:
        return pd.DataFrame(columns=["ds", "y"]).astype({"ds": "datetime64[ns]", "y": "float"})

    df = pd.DataFrame(recs).set_index("ts").sort_index()
    agg = df.resample(freq).sum().fillna(0).reset_index().rename(columns={"ts": "ds", "outgoing": "y"})
    _ensure_dt64(agg, "ds")
    return agg[["ds", "y"]]

async def fetch_planned_incoming(
    product_id: str,
    warehouse_id: Optional[str],
    start: datetime,
    end: datetime,
    freq: str = "D",
) -> pd.DataFrame:
    """
    Объединяет планы из:
      1) deliveries→delivery_items (scheduled_at, ordered_quantity)
      2) scheduled_deliveries (scheduled_at, quantity) со статусом 'scheduled'
    Возвращает ['ds','incoming'] агрегировано по freq.
    """
    async with async_session() as session:
        # 1) материализованные планы
        q_di = select(DeliveryItems).where(DeliveryItems.product_id == product_id)
        if warehouse_id:
            q_di = q_di.where(DeliveryItems.warehouse_id == warehouse_id)
        rows_di = (await session.execute(q_di)).scalars().all()

        recs: List[Dict] = []
        for item in rows_di:
            d = item.delivery
            sched = d.scheduled_at if (d and d.scheduled_at) else None
            if sched and (start <= sched <= end):
                recs.append({"ts": pd.to_datetime(sched), "incoming": float(item.ordered_quantity or 0)})

        # 2) ещё не материализованные планы
        q_sd = select(ScheduledDelivery).where(ScheduledDelivery.product_id == product_id)
        if warehouse_id:
            q_sd = q_sd.where(ScheduledDelivery.warehouse_id == warehouse_id)
        q_sd = q_sd.where(ScheduledDelivery.status.in_(["scheduled"]))
        rows_sd = (await session.execute(q_sd)).scalars().all()

        for sd in rows_sd:
            if sd.scheduled_at and (start <= sd.scheduled_at <= end):
                recs.append({"ts": pd.to_datetime(sd.scheduled_at), "incoming": float(sd.quantity or 0)})

    if not recs:
        return pd.DataFrame(columns=["ds", "incoming"]).astype({"ds": "datetime64[ns]", "incoming": "float"})

    df = pd.DataFrame(recs).set_index("ts").sort_index()
    agg = df.resample(freq).sum().fillna(0).reset_index().rename(columns={"ts": "ds"})
    _ensure_dt64(agg, "ds")
    return agg[["ds", "incoming"]]
