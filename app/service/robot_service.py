# app/service/robot_service.py
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

        # Мягкая проверка, если id прислали явно (снимет 99% ложных конфликтов по PK)
        if data.id:
            existing = await self.repo.get(robot_id)
            if existing:
                raise HTTPException(status_code=409, detail="Robot with this id already exists")

        try:
            robot = await self.repo.create(
                id=robot_id,
                status=data.status,
                battery_level=data.battery_level,
                current_zone=data.current_zone,
                current_row=data.current_row,
                current_shelf=data.current_shelf,
            )
            return robot

        except IntegrityError as e:
            # Попробуем вытащить SQLSTATE (psycopg2 и asyncpg через SA обычно дают .orig)
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or e.orig or e)

            if code == "23505":  # unique_violation
                raise HTTPException(status_code=409, detail="Robot with this id already exists")
            if code == "23502":  # not_null_violation
                raise HTTPException(status_code=400, detail="Missing required field (NOT NULL violation)")
            if code == "23503":  # fk_violation
                raise HTTPException(status_code=422, detail="Related entity not found (FK violation)")
            # по умолчанию — 500, но с коротким описанием чтобы дебажить
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")
