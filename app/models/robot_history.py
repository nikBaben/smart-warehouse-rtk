# app/models/robot_history.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class RobotHistory(Base):
    __tablename__ = "robot_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    robot_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("robots.id", ondelete="CASCADE", onupdate="CASCADE"), index=True
    )
    warehouse_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("warehouses.id", ondelete="RESTRICT", onupdate="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # idle/scan/charge/offline/...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    robot = relationship("Robot", lazy="joined")

# Рекомендуемые индексы (в Alembic):
# 1) по сквозной временной фильтрации
Index("ix_rh_wh_created", RobotHistory.warehouse_id, RobotHistory.created_at)
# 2) для fast подсчёта активных в окне
Index("ix_rh_wh_status_created", RobotHistory.warehouse_id, RobotHistory.status, RobotHistory.created_at)
# 3) при анализе по роботу
Index("ix_rh_robot_created", RobotHistory.robot_id, RobotHistory.created_at)
