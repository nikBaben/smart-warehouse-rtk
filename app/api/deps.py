from fastapi import Depends, HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.robot_repo import RobotRepository
from app.service.robot_service import RobotService
from app.db.session import get_session


def get_robot_repo(db: AsyncSession = Depends(get_session)) -> RobotRepository:
    return RobotRepository(db)

def get_robot_service(repo: RobotRepository = Depends(get_robot_repo)) -> RobotService:
    return RobotService(repo)
