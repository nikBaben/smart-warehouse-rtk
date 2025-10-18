from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.robot import Robot


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
        current_shelf: int,
    ) -> Robot:
        robot = Robot(
            id=id,
            status=status,
            battery_level=battery_level,
            current_zone=current_zone,
            current_row=current_row,
            current_shelf=current_shelf,
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
        res = await self.session.execute(select(Robot).where(Robot.id == id))
        return res.scalar_one_or_none()
