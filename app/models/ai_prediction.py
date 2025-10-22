from sqlalchemy import String, Integer, Date, Numeric, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(String(50), ForeignKey("products.id"), nullable=False)
    prediction_date: Mapped[Date] = mapped_column(Date, nullable=False)
    days_until_stockout: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_order: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())