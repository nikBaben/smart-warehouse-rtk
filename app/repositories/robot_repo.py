from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.robot import Robot
from app.models.warehouse import Warehouse


class RobotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        id: str,
        status: str,
        battery_level: int,
        current_zone: str,
        current_row: int,
        current_shelf: str,
        warehouse_id: str,
        check_warehouse_exists: bool = True,
    ) -> Robot:
        if check_warehouse_exists:
            exists = await self.session.scalar(
                select(Warehouse.id).where(Warehouse.id == warehouse_id)
            )
            if not exists:
                raise ValueError(f"Склад '{warehouse_id}' не найден")
        
        robot = Robot(
            id=id,
            status=status,
            battery_level=battery_level,
            current_zone=current_zone,
            current_row=current_row,
            current_shelf=current_shelf,
            warehouse_id = warehouse_id
        )

        self.session.add(robot)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise e
        await self.session.refresh(robot)
        return robot

    async def get(self, id: str) -> Optional[Robot]:
        return await self.session.scalar(
            select(Robot).where(Robot.id == id)
        )
    
    async def get_all_by_warehouse_id(self, warehosue_id: str):
        result = await self.session.execute(
            select(Robot).where(Robot.warehouse_id == warehosue_id)
        )
        return list(result.scalars().all())
