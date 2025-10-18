# app/models/robot.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, func
from datetime import datetime

from app.db.base import Base

class Robot(Base):
    __tablename__ = "robots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    battery_level: Mapped[int] = mapped_column(Integer, default=0)  # ok
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    current_zone: Mapped[str] = mapped_column(String)
    current_row: Mapped[int] = mapped_column(Integer, default=0)
    current_shelf: Mapped[int] = mapped_column(Integer, default=0)

    # <-- ВАЖНО: дефолт на стороне БД и NOT NULL
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
