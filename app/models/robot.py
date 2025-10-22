from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Robot(Base):
    __tablename__ = "robots"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'RB-001'
    status: Mapped[str] = mapped_column(String(50), default="active")
    battery_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_update: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    current_zone: Mapped[str | None] = mapped_column(String(10), nullable=True)
    current_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_shelf: Mapped[int | None] = mapped_column(Integer, nullable=True)