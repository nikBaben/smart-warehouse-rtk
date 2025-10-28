from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import DeliveryStatus

from app.db.base import Base

class Delivery(Base):
    __tablename__ = "Delivery"
    
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    warehouse_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("warehouse.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status", native_enum=False),
        nullable=False,
        default=DeliveryStatus.scheduled,
    )
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    warehouse: Mapped[Optional["Warehouse"]] = relationship("Warehouse", lazy="joined")