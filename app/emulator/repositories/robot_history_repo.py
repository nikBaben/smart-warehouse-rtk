from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import insert
from app.models.robot_history import RobotHistory

async def log_robot_status(session, robot_id: str, warehouse_id: str, status: str):
    await session.execute(
        insert(RobotHistory).values(
            id=str(uuid4()),
            robot_id=robot_id,
            warehouse_id=warehouse_id,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
    )
