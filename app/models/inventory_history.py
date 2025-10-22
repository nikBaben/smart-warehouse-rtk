from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InventoryHistory(Base):
    __tablename__ = "inventory_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # ссылки на объекты
    product_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("products.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    robot_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        ForeignKey("robots.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    warehouse_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("warehouses.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    product: Mapped[Optional["Product"]] = relationship(
        back_populates="history",
        lazy="joined",
    )
    robot: Mapped[Optional["Robot"]] = relationship(
        back_populates="history",
        lazy="joined",
    )
    warehouse: Mapped["Warehouse"] = relationship(
        back_populates="inventory_history",
        lazy="joined",
    )

    # снимок координат/зоны на момент события
    current_zone: Mapped[str] = mapped_column(String, default="Храненние")
    current_row: Mapped[int] = mapped_column(Integer, default=0)
    current_shelf: Mapped[str] = mapped_column(String, default="A")

    # (опционально) денормализованные данные товара на момент сканирования
    name: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    category: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    article: Mapped[str] = mapped_column(String(100))
    stock: Mapped[Optional[int]] = mapped_column(Integer)
    min_stock: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    optimal_stock: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    status: Mapped[Optional[str]] = mapped_column(String(100), default=None)

    # meta
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

