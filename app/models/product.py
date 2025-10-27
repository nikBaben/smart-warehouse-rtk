from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer,String, DateTime, func, ForeignKey, Index
from datetime import datetime
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100))
    article: Mapped[str] = mapped_column(String(100))
    stock: Mapped[int] = mapped_column(Integer, default=100,nullable=False)
    min_stock: Mapped[int] = mapped_column(Integer, default=20)
    optimal_stock: Mapped[int] = mapped_column(Integer, default=80)
    current_zone: Mapped[str] = mapped_column(String, default="Храненние")
    current_row: Mapped[int] = mapped_column(Integer, default=0)
    current_shelf: Mapped[str] = mapped_column(String, default="A")
    status: Mapped[str] = mapped_column(String, default="ок")

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

    history: Mapped[list["InventoryHistory"]] = relationship(
        back_populates="product",
        lazy="selectin",
        cascade="save-update, merge",  # или вообще убрать параметр cascade
        passive_deletes=True,          # БД сама проставит NULL, ORM не трогает
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_products_warehouse_id_name", "warehouse_id", "name"),
    )
