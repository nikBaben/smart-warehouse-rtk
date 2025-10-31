from sqlalchemy import select
from app.models.robot import Robot

async def get_robot_ids_in_warehouse(session, warehouse_id: str):
    r = await session.execute(select(Robot.id).where(Robot.warehouse_id == warehouse_id))
    return list(r.scalars().all())
