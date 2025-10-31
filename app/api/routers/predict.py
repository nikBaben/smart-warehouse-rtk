from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime
from app.ml.predictor import Predictor
import os

router = APIRouter(prefix="/ml", tags=["ml"])

@router.get("/depletion")
async def get_depletion(
    product_id: str = Query(...),
    warehouse_id: Optional[str] = None,
    horizon_days: int = 60
):
    model_path = f"/app/models_store/{product_id}.pkl"
    if not os.path.exists(model_path):
        # Если нет индивидуальной модели — используем дефолтную
        default_model = "/app/models_store/PROD_DEMO.pkl"
        if os.path.exists(default_model):
            model_path = default_model
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Модель не найдена: {model_path}. Сначала обучи через train.py",
            )

    predictor = Predictor(model_path=model_path)
    dt = await predictor.predict_depletion_date(
        product_id=product_id,
        warehouse_id=warehouse_id,
        horizon_days=horizon_days,
        as_of=datetime.utcnow()
    )
    return {
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "horizon_days": horizon_days,
        "depletion_at": dt.isoformat() if dt else None,
        "model_used": os.path.basename(model_path),
    }
