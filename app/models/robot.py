from sqlalchemy.orm import Mapped, mapped_column,relationship
from sqlalchemy import Integer, String, DateTime, func,ForeignKey
from datetime import datetime

from app.db.base import Base

class Robot(Base):
    __tablename__ = "robots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    battery_level: Mapped[int] = mapped_column(Integer, default=0)  
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    current_zone: Mapped[str] = mapped_column(String)
    current_row: Mapped[int] = mapped_column(Integer, default=0)
    current_shelf: Mapped[int] = mapped_column(Integer, default=0)

    warehouse_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("warehouses.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    warehouse: Mapped["Warehouse"] = relationship(
        back_populates="robots",
        lazy="joined", 
    )

    history: Mapped[list["InventoryHistory"]] = relationship(  # type: ignore
        back_populates="robot",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
