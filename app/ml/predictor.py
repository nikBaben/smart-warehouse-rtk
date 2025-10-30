from typing import Optional, List, Dict
from datetime import datetime, timedelta
import pandas as pd
from app.ml.model_store import load_model
from app.ml.data_access import (
    fetch_snapshot_at,
    fetch_planned_incoming,
    predict_depletion_with_model
)
from prophet import Prophet


class Predictor:
    """Predictor for stock depletion using trained Prophet model.
    
    Full pipeline:
    1. Load trained model (trained on historical outgoing shipments)
    2. Get current stock snapshot
    3. Get planned incoming deliveries
    4. Predict future outgoing (demand)
    5. Calculate depletion date: stock + incoming - predicted_outgoing
    """
    
    def __init__(self, model: Optional[Prophet] = None, model_path: Optional[str] = None):
        self.model = model
        self.model_path = model_path
        self.prediction = None
        if model_path:
            self.load(model_path)

    def load(self, model_path: str):
        """Load trained Prophet model from disk."""
        self.model = load_model(model_path)
        self.model_path = model_path

    def predict_outgoing(self, horizon_days: int = 30) -> pd.DataFrame:
        """Predict future outgoing shipments (demand) for next horizon_days.
        
        Returns:
            DataFrame with columns: ds, yhat, yhat_lower, yhat_upper
        """
        if self.model is None:
            if self.model_path:
                self.load(self.model_path)
        if self.model is None:
            raise RuntimeError("Model not loaded")

        future = self.model.make_future_dataframe(periods=horizon_days, freq="D")
        forecast = self.model.predict(future)

        self.prediction = forecast.tail(horizon_days)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        return self.prediction
    
    async def predict_depletion_date(self,
                                    product_id: str,
                                    warehouse_id: Optional[str] = None,
                                    horizon_days: int = 30,
                                    as_of: Optional[datetime] = None) -> Optional[datetime]:
        """Predict when stock will deplete to zero.
        
        Args:
            product_id: Product ID
            warehouse_id: Optional warehouse filter
            horizon_days: Prediction horizon (days)
            as_of: Reference time (default: now)
        
        Returns:
            datetime when stock <= 0, or None if no depletion in horizon
        """
        if as_of is None:
            as_of = datetime.utcnow()
        
        initial_stock = await fetch_snapshot_at(product_id, warehouse_id, as_of)
        if initial_stock is None or initial_stock <= 0:
            return as_of
        
        start = as_of
        end = as_of + timedelta(days=horizon_days)
        planned_incoming = await fetch_planned_incoming(product_id, warehouse_id, start, end)

        predicted_outgoing = self.predict_outgoing(horizon_days)
        
        depletion_date = predict_depletion_with_model(
            initial_stock,
            planned_incoming,
            predicted_outgoing
        )
        
        return depletion_date
    
    def get_predict_as_list(self) -> List[Dict]:
        """Get prediction as list of dicts (for JSON serialization)."""
        if self.prediction is None:
            raise RuntimeError("No prediction available. Call predict_outgoing() first.")
        
        out_list = []
        for _, row in self.prediction.iterrows():
            out_list.append({
                "ds": pd.to_datetime(row["ds"]).isoformat(),
                "yhat": float(row["yhat"]),
                "yhat_lower": float(row["yhat_lower"]),
                "yhat_upper": float(row["yhat_upper"]),
            })
        return out_list

    def get_predict_as_dataframe(self) -> pd.DataFrame:
        """Get prediction as DataFrame."""
        if self.prediction is None:
            raise RuntimeError("No prediction available. Call predict_outgoing() first.")
        return self.prediction