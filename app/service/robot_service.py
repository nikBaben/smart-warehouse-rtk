from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.schemas.robot import RobotCreate
from app.repositories.robot_repo import RobotRepository
from app.models.robot import Robot

class RobotService:
    def __init__(self, repo: RobotRepository):
        self.repo = repo

    async def create_robot(self, data: RobotCreate) -> Robot:
        robot_id = data.id or str(uuid4())

        if data.warehouse_id is None or data.warehouse_id == "":
            raise HTTPException(status_code=400, detail="warehouse_id is required")
        
        try:
            robot = await self.repo.create(
                id=robot_id,
                status=data.status,
                battery_level=data.battery_level,
                current_zone=data.current_zone,
                current_row=data.current_row,
                current_shelf=data.current_shelf,
                warehouse_id=data.warehouse_id, 
                check_warehouse_exists=True
            )
            return robot

        except IntegrityError as e:
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or e.orig or e)

            if code == "23505":  
                raise HTTPException(status_code=409, detail="Robot with this id already exists")
            if code == "23502": 
                raise HTTPException(status_code=400, detail="Missing required field (NOT NULL violation)")
            if code == "23503":  
                raise HTTPException(status_code=422, detail="Related entity not found (FK violation)")
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")
        
    async def get_robots_by_warehouse_id(self, warehouse_id: str):
        robots = await self.repo.get_all_by_warehouse_id(warehouse_id)
        if not robots:
            raise ValueError(f"Роботы на скалде id '{warehouse_id}' не найдены.")
        return robots
