from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, func, ForeignKey, Index
from datetime import datetime
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100))
    min_stock: Mapped[int] = mapped_column(Integer, default=10)
    optimal_stock: Mapped[int] = mapped_column(Integer, default=100)

    warehouse_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("warehouses.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    warehouse: Mapped["Warehouse"] = relationship( # type: ignore
        back_populates="products",
        lazy="joined",  
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_products_warehouse_id_name", "warehouse_id", "name"),
    )
