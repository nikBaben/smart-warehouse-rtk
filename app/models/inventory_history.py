from sqlalchemy import String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class InventoryHistory(Base):
    __tablename__ = "inventory_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    robot_id: Mapped[str] = mapped_column(String(50), ForeignKey("robots.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(50), ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    zone: Mapped[str] = mapped_column(String(10), nullable=False)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shelf_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50))  # 'OK', 'LOW_STOCK', 'CRITICAL'
    scanned_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())