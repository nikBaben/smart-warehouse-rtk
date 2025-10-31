from __future__ import annotations
from sqlalchemy import Column, String, DateTime, Integer, func
from sqlalchemy.orm import declarative_base
from app.db.base import Base

class PredictAt(Base):
    """
    Таблица прогнозов истощения запасов.
    Содержит результаты ML-предсказаний для конкретных товаров на складе.
    """

    __tablename__ = "predict_at"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    warehouse_id = Column(String, nullable=False, index=True)
    depletion_at = Column(DateTime(timezone=True), nullable=True)
    predicted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return (
            f"<PredictAt(product_id={self.product_id}, "
            f"warehouse_id={self.warehouse_id}, depletion_at={self.depletion_at})>"
        )
