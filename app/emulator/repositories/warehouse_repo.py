from sqlalchemy import select
from app.models.warehouse import Warehouse
from app.models.robot import Robot

async def list_active_warehouses(session):
    rows = await session.execute(
        select(Warehouse.id).join(Robot, Robot.warehouse_id == Warehouse.id).distinct()
    )
    return set(rows.scalars().all())
