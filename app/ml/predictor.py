from __future__ import annotations
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone
import pandas as pd
from prophet import Prophet
from app.ml.model_store import load_model
from app.ml.data_access import fetch_snapshot_at, fetch_planned_incoming


def ensure_utc(dt: datetime) -> datetime:
    """Принудительно делает datetime timezone-aware в UTC."""
    if dt is None:
        return None
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def predict_depletion_with_model(
    initial_stock: float,
    planned_incoming_df: pd.DataFrame,
    predicted_outgoing_df: pd.DataFrame,
    freq: str = "D",
) -> Optional[datetime]:
    if initial_stock is None or initial_stock <= 0:
        return None

    def _normalize_df(df: pd.DataFrame, col: str) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)
        idx = pd.to_datetime(df["ds"], utc=True)
        return df.set_index(idx)[col]

    incoming = _normalize_df(planned_incoming_df, "incoming")
    outgoing = _normalize_df(predicted_outgoing_df, "yhat")

    if incoming.empty and outgoing.empty:
        return None

    all_dates = pd.concat([incoming, outgoing]).index.unique().sort_values()
    incoming = incoming.reindex(all_dates, fill_value=0)
    outgoing = outgoing.reindex(all_dates, fill_value=0).clip(lower=0)

    stock = float(initial_stock)
    for date in all_dates:
        stock += float(incoming.get(date, 0))
        stock -= float(outgoing.get(date, 0))
        if stock <= 0:
            return ensure_utc(date.to_pydatetime())
    return None


class Predictor:
    def __init__(self, model: Optional[Prophet] = None, model_path: Optional[str] = None):
        self.model: Optional[Prophet] = model
        self.model_path = model_path
        self.prediction: Optional[pd.DataFrame] = None
        if model_path:
            self.load(model_path)

    def load(self, model_path: str):
        self.model = load_model(model_path)
        self.model_path = model_path

    def predict_outgoing(self, horizon_days: int = 30) -> pd.DataFrame:
        if self.model is None:
            if self.model_path:
                self.load(self.model_path)
        if self.model is None:
            raise RuntimeError("Model not loaded")

        future = self.model.make_future_dataframe(periods=horizon_days, freq="D")
        forecast = self.model.predict(future)
        forecast["ds"] = pd.to_datetime(forecast["ds"], utc=True)
        self.prediction = forecast.tail(horizon_days)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        return self.prediction

    async def predict_depletion_date(
        self,
        product_id: str,
        warehouse_id: Optional[str] = None,
        horizon_days: int = 30,
        as_of: Optional[datetime] = None,
    ) -> Optional[datetime]:
        if as_of is None:
            as_of = datetime.now(timezone.utc)
        as_of = ensure_utc(as_of)

        initial_stock = await fetch_snapshot_at(product_id, warehouse_id, as_of)
        if initial_stock is None or initial_stock <= 0:
            return as_of

        start = as_of
        end = as_of + timedelta(days=horizon_days)

        planned_incoming = await fetch_planned_incoming(product_id, warehouse_id, start, end)
        predicted_outgoing = self.predict_outgoing(horizon_days)

        depletion = predict_depletion_with_model(initial_stock, planned_incoming, predicted_outgoing)
        return ensure_utc(depletion)

    def get_predict_as_list(self) -> List[Dict]:
        if self.prediction is None:
            raise RuntimeError("No prediction available. Call predict_outgoing() first.")
        return [
            {
                "ds": ensure_utc(pd.to_datetime(row["ds"])).isoformat(),
                "yhat": float(row["yhat"]),
                "yhat_lower": float(row["yhat_lower"]),
                "yhat_upper": float(row["yhat_upper"]),
            }
            for _, row in self.prediction.iterrows()
        ]

    def get_predict_as_dataframe(self) -> pd.DataFrame:
        if self.prediction is None:
            raise RuntimeError("No prediction available. Call predict_outgoing() first.")
        return self.prediction
