from typing import Optional
import pandas as pd
from datetime import datetime
from sqlalchemy import select
from app.db.session import async_session
from app.models.inventory_history import InventoryHistory


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
    out = pd.DataFrame({"ds": regular.index, "y": consumption.values})
    
    return out
    