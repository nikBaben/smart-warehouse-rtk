from typing import Optional
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import select
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory
from app.models.delivery_items import DeliveryItems
from app.models.shipment import ShipmentItems


"""
Event-driven data access helpers for ML.

Principle: do not derive consumption from inventory history timeseries.
Use `delivery_items` (incoming) and `shipment_items` (outgoing) as authoritative event sources.
`inventory_history` is used only to obtain a snapshot at prediction time (current stock).
"""


async def fetch_inventory_history(product_id: str, wharehouse_id: Optional[str]=None,
                                  start: Optional[datetime]=None, end: Optional[datetime] = None):
    async with async_session() as session:
        stmt = select(InventoryHistory).where(InventoryHistory.product_id == product_id)
        if wharehouse_id:
            stmt = stmt.where(InventoryHistory.warehouse_id == wharehouse_id)
        if start:
            stmt = stmt.where(InventoryHistory.created_at >= start)
        if end:
            stmt = stmt.where(InventoryHistory.created_at <= end)
        stmt = stmt.order_by(InventoryHistory.created_at)
        result = await session.execute(stmt)
        rows = result.scalars().all()
    
    if not rows:
        return pd.DataFrame(columns=["created_at", "stock"]).astype({"created_at": "datetime64[ns]", "stock": "float" })
    
    records = []
    for r in rows:
        records.append({
            "created_at": r.created_at,
            "stock": float(r.stock) if r.stock is not None else None
        })
    df = pd.DataFrame.from_records(records)
    df = df.dropna(subset=["created_at"]).set_index("created_at").sort_index()
    return df


async def fetch_snapshot_at(product_id: str, wharehouse_id: Optional[str], at_time: datetime) -> Optional[float]:
    """Return latest inventory snapshot (stock) for a product/warehouse at or before at_time.

    Returns float stock or None if no snapshot exists.
    """
    async with async_session() as session:
        stmt = select(InventoryHistory).where(InventoryHistory.product_id == product_id)
        if wharehouse_id:
            stmt = stmt.where(InventoryHistory.warehouse_id == wharehouse_id)
        stmt = stmt.where(InventoryHistory.created_at <= at_time).order_by(InventoryHistory.created_at.desc())
        row = (await session.execute(stmt)).scalars().first()

    if not row:
        return None
    return float(row.stock) if row.stock is not None else None


async def build_event_timeseries(product_id: str,
                                  wharehouse_id: Optional[str] = None,
                                  start: Optional[datetime] = None,
                                  end: Optional[datetime] = None,
                                  freq: str = "D",
                                  include_planned: bool = True,
                                  include_actuals: bool = True) -> pd.DataFrame:
    """Build a timeseries of incoming/outgoing events from delivery_items and shipment_items.

    - planned events use parent scheduled_at and ordered_quantity
    - actual events use parent delivered_at/shipped_at and fact_quantity (fallback to item.created_at)

    Returns DataFrame with columns: ds, incoming, outgoing, net_outgoing aggregated by `freq`.
    """
    async with async_session() as session:
        stmt_in = select(DeliveryItems).where(DeliveryItems.product_id == product_id)
        if wharehouse_id:
            stmt_in = stmt_in.where(DeliveryItems.warehouse_id == wharehouse_id)
        # limit fetched rows to a reasonable window if start/end provided to avoid huge scans
        if start:
            stmt_in = stmt_in.where(DeliveryItems.created_at >= (start - timedelta(days=3650)))
        rows_in = (await session.execute(stmt_in)).scalars().all()

        stmt_out = select(ShipmentItems).where(ShipmentItems.product_id == product_id)
        if wharehouse_id:
            stmt_out = stmt_out.where(ShipmentItems.warehouse_id == wharehouse_id)
        if start:
            stmt_out = stmt_out.where(ShipmentItems.created_at >= (start - timedelta(days=3650)))
        rows_out = (await session.execute(stmt_out)).scalars().all()

    records = []
    now = datetime.utcnow()

    # process incoming (deliveries)
    for item in rows_in:
        # planned: use delivery.scheduled_at + ordered_quantity
        if include_planned and getattr(item, "delivery", None) is not None:
            sched = getattr(item.delivery, "scheduled_at", None)
            if sched is not None and (not start or sched >= start) and (not end or sched <= end):
                records.append({"ts": pd.to_datetime(sched), "incoming": float(item.ordered_quantity or 0), "outgoing": 0.0})

        # actual: delivered_at (preferred) or item.created_at fallback
        if include_actuals:
            actual_ts = None
            if getattr(item, "delivery", None) is not None and getattr(item.delivery, "delivered_at", None):
                actual_ts = item.delivery.delivered_at
            else:
                actual_ts = item.created_at

            if actual_ts is not None and actual_ts <= now and (not start or actual_ts >= start) and (not end or actual_ts <= end):
                records.append({"ts": pd.to_datetime(actual_ts), "incoming": float(item.fact_quantity or 0), "outgoing": 0.0})

    # process outgoing (shipments)
    for item in rows_out:
        # planned: use shipment.scheduled_at + ordered_quantity
        if include_planned and getattr(item, "shipment", None) is not None:
            sched = getattr(item.shipment, "scheduled_at", None)
            if sched is not None and (not start or sched >= start) and (not end or sched <= end):
                records.append({"ts": pd.to_datetime(sched), "incoming": 0.0, "outgoing": float(item.ordered_quantity or 0)})

        # actual: shipped_at (preferred) or item.created_at fallback
        if include_actuals:
            actual_ts = None
            if getattr(item, "shipment", None) is not None and getattr(item.shipment, "shipped_at", None):
                actual_ts = item.shipment.shipped_at
            else:
                actual_ts = item.created_at

            if actual_ts is not None and actual_ts <= now and (not start or actual_ts >= start) and (not end or actual_ts <= end):
                records.append({"ts": pd.to_datetime(actual_ts), "incoming": 0.0, "outgoing": float(item.fact_quantity or 0)})

    if not records:
        return pd.DataFrame(columns=["ds", "incoming", "outgoing", "net_outgoing"]).astype({"ds": "datetime64[ns]", "incoming": "float", "outgoing": "float", "net_outgoing": "float"})

    df = pd.DataFrame.from_records(records)
    df = df.set_index("ts").sort_index()
    agg = df.resample(freq).sum().fillna(0)
    agg["net_outgoing"] = agg["outgoing"] - agg["incoming"]
    agg = agg.reset_index().rename(columns={"ts": "ds"})
    if "ds" not in agg.columns:
        agg.insert(0, "ds", agg.index)
    return agg[["ds", "incoming", "outgoing", "net_outgoing"]]


async def predict_depletion_from_snapshot(product_id: str,
                                         wharehouse_id: Optional[str],
                                         as_of: datetime,
                                         horizon_days: int = 365,
                                         freq: str = "D") -> Optional[datetime]:
    """Deterministic depletion predictor using snapshot + planned events.

    Algorithm:
      - get snapshot stock at `as_of`
      - collect planned events with scheduled_at in (as_of, as_of + horizon]
      - aggregate by `freq` and apply incoming/outgoing to stock cumulatively
      - return first datetime when stock <= 0, otherwise None
    """
    initial = await fetch_snapshot_at(product_id, wharehouse_id, as_of)
    if initial is None:
        return None

    start = as_of
    end = as_of + timedelta(days=horizon_days)
    events = await build_event_timeseries(product_id, wharehouse_id, start=start, end=end, freq=freq, include_planned=True, include_actuals=False)

    # ensure events are ordered by ds and have net_outgoing
    if events.empty:
        return None

    events = events.sort_values("ds").reset_index(drop=True)
    # iterate over aggregated periods
    stock = float(initial)
    for _, row in events.iterrows():
        # apply incoming first then outgoing to reflect inventory increases available for same period
        stock += float(row.get("incoming", 0) or 0)
        stock -= float(row.get("outgoing", 0) or 0)
        if stock <= 0:
            # return period timestamp (start of period)
            ds = pd.to_datetime(row["ds"])
            return ds.to_pydatetime()

    return None

async def fetch_consumption_timeseries(product_id: str, wharehouse_id: Optional[str] = None,
                                       start: Optional[datetime] = None, end: Optional[datetime] = None,
                                       freq: str = "D"):
    df = await fetch_inventory_history(product_id, wharehouse_id, start, end)
    if df.empty:
        return pd.DataFrame(columns=["ds", "y"]).astype({"ds": "datetime64[ns]", "y": "int16"})
    
    df.index = pd.to_datetime(df.index)
    regular = df["stock"].resample(freq).last().ffill()
    
    prev = regular.shift(1)
    consumption = (prev - regular).clip(lower=0).fillna(0)
    out = pd.DataFrame({"ds": regular.index, "y_inventory": consumption.values})

    # fetch event-based movements (incoming from deliveries, outgoing from shipments)
    events = await fetch_movement_timeseries(product_id, wharehouse_id, start, end, freq=freq)

    # merge inventory-based consumption with events-based net outgoing
    merged = out.set_index("ds").join(events.set_index("ds"), how="outer")
    merged = merged.sort_index().fillna(0)
    # events net is outgoing - incoming; keep positive = net outgoing (consumption)
    merged["y_events"] = merged.get("net_outgoing", 0).astype(float)
    merged["y_inventory"] = merged.get("y_inventory", 0).astype(float)

    # combined consumption: prefer inventory-observed consumption but fall back to events if larger
    merged["y_combined"] = merged[["y_inventory", "y_events"]].max(axis=1)

    merged = merged.reset_index().rename_axis(None, axis=1)
    # return ds, y_inventory, y_events, y_combined (ds is datetime index already)
    return merged[["ds", "y_inventory", "y_events", "y_combined"]]


async def fetch_movement_timeseries(product_id: str, wharehouse_id: Optional[str] = None,
                                    start: Optional[datetime] = None, end: Optional[datetime] = None,
                                    freq: str = "D"):
    """Return daily aggregated incoming/outgoing events for a product and optional warehouse.

    Returns DataFrame with columns:
      - ds (period start as datetime)
      - incoming (sum of incoming fact_quantity)
      - outgoing (sum of outgoing fact_quantity)
      - net_outgoing (outgoing - incoming)
    """
    async with async_session() as session:
        # deliveries
        stmt_in = select(DeliveryItems).where(DeliveryItems.product_id == product_id)
        if wharehouse_id:
            stmt_in = stmt_in.where(DeliveryItems.warehouse_id == wharehouse_id)
        if start:
            stmt_in = stmt_in.where(DeliveryItems.created_at >= start)
        if end:
            stmt_in = stmt_in.where(DeliveryItems.created_at <= end)
        stmt_in = stmt_in.order_by(DeliveryItems.created_at)
        rows_in = (await session.execute(stmt_in)).scalars().all()

        # shipments
        stmt_out = select(ShipmentItems).where(ShipmentItems.product_id == product_id)
        if wharehouse_id:
            stmt_out = stmt_out.where(ShipmentItems.warehouse_id == wharehouse_id)
        if start:
            stmt_out = stmt_out.where(ShipmentItems.created_at >= start)
        if end:
            stmt_out = stmt_out.where(ShipmentItems.created_at <= end)
        stmt_out = stmt_out.order_by(ShipmentItems.created_at)
        rows_out = (await session.execute(stmt_out)).scalars().all()

    records = []
    for r in rows_in:
        # prefer parent delivery timestamp if available, otherwise item create time
        ts = None
        try:
            ts = r.delivery.delivered_at if (hasattr(r, "delivery") and r.delivery and getattr(r.delivery, "delivered_at", None)) else r.created_at
        except Exception:
            ts = r.created_at
        if ts is None:
            continue
        records.append({"ts": pd.to_datetime(ts), "incoming": float(r.fact_quantity or 0), "outgoing": 0.0})

    for r in rows_out:
        ts = None
        try:
            ts = r.shipment.shipped_at if (hasattr(r, "shipment") and r.shipment and getattr(r.shipment, "shipped_at", None)) else r.created_at
        except Exception:
            ts = r.created_at
        if ts is None:
            continue
        records.append({"ts": pd.to_datetime(ts), "incoming": 0.0, "outgoing": float(r.fact_quantity or 0)})

    if not records:
        return pd.DataFrame(columns=["ds", "incoming", "outgoing", "net_outgoing"]).astype({"ds": "datetime64[ns]", "incoming": "float", "outgoing": "float", "net_outgoing": "float"})

    df = pd.DataFrame.from_records(records)
    df = df.set_index("ts").sort_index()

    # resample/aggregate by requested freq
    agg = df.resample(freq).sum().fillna(0)
    agg["net_outgoing"] = agg["outgoing"] - agg["incoming"]
    agg = agg.reset_index().rename(columns={"ts": "ds"})
    agg = agg.rename(columns={"ts": "ds"})
    agg = agg.rename_axis(None, axis=1)
    agg = agg.rename(columns={"ts": "ds"})

    # ensure column ds exists (resample produced index)
    if "ds" not in agg.columns:
        agg.insert(0, "ds", agg.index)

    return agg[["ds", "incoming", "outgoing", "net_outgoing"]]


async def fetch_snapshot_at(product_id: str, wharehouse_id: Optional[str], at_time: datetime):
    """Return the latest inventory snapshot (stock) for product/warehouse at or before at_time.

    Returns float stock or None if no snapshot exists.
    """
    async with async_session() as session:
        stmt = select(InventoryHistory).where(InventoryHistory.product_id == product_id)
        if wharehouse_id:
            stmt = stmt.where(InventoryHistory.warehouse_id == wharehouse_id)
        stmt = stmt.where(InventoryHistory.created_at <= at_time).order_by(InventoryHistory.created_at.desc())
        row = (await session.execute(stmt)).scalars().first()

    if not row:
        return None
    return float(row.stock) if row.stock is not None else None


async def build_event_timeseries(product_id: str, wharehouse_id: Optional[str] = None,
                                  start: Optional[datetime] = None, end: Optional[datetime] = None,
                                  freq: str = "D", include_planned: bool = True, include_actuals: bool = True):
    """Build event-only timeseries of incoming/outgoing for prediction.

    - include_planned: include scheduled_at events (ordered quantities)
    - include_actuals: include realized events (delivered_at/shipped_at with fact_quantity)

    Returns DataFrame with ds, incoming, outgoing, net_outgoing aggregated by `freq`.
    """
    async with async_session() as session:
        stmt_in = select(DeliveryItems).where(DeliveryItems.product_id == product_id)
        if wharehouse_id:
            stmt_in = stmt_in.where(DeliveryItems.warehouse_id == wharehouse_id)
        if start and include_actuals:
            # we'll still fetch all and filter timestamps later
            stmt_in = stmt_in.where(DeliveryItems.created_at >= (start - timedelta(days=3650)))
        rows_in = (await session.execute(stmt_in)).scalars().all()

        stmt_out = select(ShipmentItems).where(ShipmentItems.product_id == product_id)
        if wharehouse_id:
            stmt_out = stmt_out.where(ShipmentItems.warehouse_id == wharehouse_id)
        if start and include_actuals:
            stmt_out = stmt_out.where(ShipmentItems.created_at >= (start - timedelta(days=3650)))
        rows_out = (await session.execute(stmt_out)).scalars().all()

    records = []
    now = datetime.utcnow()
    for r in rows_in:
        # planned
        if include_planned and hasattr(r, "delivery") and r.delivery and getattr(r.delivery, "scheduled_at", None):
            ts = r.delivery.scheduled_at
            if (not start or ts >= start) and (not end or ts <= end):
                records.append({"ts": pd.to_datetime(ts), "incoming": float(r.ordered_quantity or 0), "outgoing": 0.0})

        # actuals
        if include_actuals:
            ts = None
            if hasattr(r, "delivery") and r.delivery and getattr(r.delivery, "delivered_at", None):
                ts = r.delivery.delivered_at
            else:
                ts = r.created_at
            if ts and (not start or ts >= start) and (not end or ts <= end) and ts <= datetime.utcnow():
                records.append({"ts": pd.to_datetime(ts), "incoming": float(r.fact_quantity or 0), "outgoing": 0.0})

    for r in rows_out:
        # planned
        if include_planned and hasattr(r, "shipment") and r.shipment and getattr(r.shipment, "scheduled_at", None):
            ts = r.shipment.scheduled_at
            if (not start or ts >= start) and (not end or ts <= end):
                records.append({"ts": pd.to_datetime(ts), "incoming": 0.0, "outgoing": float(r.ordered_quantity or 0)})

        # actuals
        if include_actuals:
            ts = None
            if hasattr(r, "shipment") and r.shipment and getattr(r.shipment, "shipped_at", None):
                ts = r.shipment.shipped_at
            else:
                ts = r.created_at
            if ts and (not start or ts >= start) and (not end or ts <= end) and ts <= datetime.utcnow():
                records.append({"ts": pd.to_datetime(ts), "incoming": 0.0, "outgoing": float(r.fact_quantity or 0)})

    if not records:
        return pd.DataFrame(columns=["ds", "incoming", "outgoing", "net_outgoing"]).astype({"ds": "datetime64[ns]", "incoming": "float", "outgoing": "float", "net_outgoing": "float"})

    df = pd.DataFrame.from_records(records)
    df = df.set_index("ts").sort_index()
    agg = df.resample(freq).sum().fillna(0)
    agg["net_outgoing"] = agg["outgoing"] - agg["incoming"]
    agg = agg.reset_index().rename(columns={"ts": "ds"})
    if "ds" not in agg.columns:
        agg.insert(0, "ds", agg.index)
    return agg[["ds", "incoming", "outgoing", "net_outgoing"]]


def estimate_depletion_date(initial_stock: float, events_df: pd.DataFrame, freq: str = "D", horizon_days: int = 365):
    """Deterministic estimate: given initial stock and planned events (events_df with ds, incoming, outgoing),
    compute cumulative stock over horizon and return first date where stock <= 0.

    Returns datetime.date or None if not depleted within horizon.
    """
    if initial_stock is None:
        return None

    # Ensure events_df has ds and net_outgoing
    df = events_df.copy()
    if "net_outgoing" not in df.columns:
        df["net_outgoing"] = df.get("outgoing", 0) - df.get("incoming", 0)

    df = df.set_index(pd.to_datetime(df["ds"])).sort_index()
    # resample to ensure continuous timeline
    idx = pd.date_range(start=df.index.min(), periods=max(horizon_days, len(df)), freq=freq)
    daily = df["net_outgoing"].resample(freq).sum().reindex(idx, fill_value=0)

    cumulative = initial_stock - daily.cumsum()
    depleted = cumulative[cumulative <= 0]
    if depleted.empty:
        return None
    return depleted.index[0].to_pydatetime()


async def predict_depletion_from_snapshot(product_id: str, wharehouse_id: Optional[str], as_of: datetime,
                                         horizon_days: int = 365, freq: str = "D"):
    """Helper that returns deterministic depletion estimate using snapshot at `as_of` and planned events.

    Returns depletion datetime or None
    """
    initial = await fetch_snapshot_at(product_id, wharehouse_id, as_of)
    if initial is None:
        return None
    start = as_of
    end = as_of + timedelta(days=horizon_days)
    events = await build_event_timeseries(product_id, wharehouse_id, start, end, freq=freq, include_planned=True, include_actuals=False)
    return estimate_depletion_date(initial, events, freq=freq, horizon_days=horizon_days)
    