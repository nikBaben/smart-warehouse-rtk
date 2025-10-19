from fastapi import Depends, HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.robot_repo import RobotRepository
from app.service.robot_service import RobotService
from app.repositories.product_repo import ProductRepository
from app.service.product_service import ProductService
from app.repositories.warehouse_repo import WarehouseRepository
from app.service.warehouse_service import WarwehouseService
from app.db.session import get_session


def get_robot_repo(db: AsyncSession = Depends(get_session)) -> RobotRepository:
    return RobotRepository(db)

def get_robot_service(repo: RobotRepository = Depends(get_robot_repo)) -> RobotService:
    return RobotService(repo)

def get_product_repo(db: AsyncSession = Depends(get_session)) -> ProductRepository:
    return ProductRepository(db)

def get_product_service(repo: ProductRepository = Depends(get_product_repo)) -> ProductService:
    return ProductService(repo)

def get_warehouse_repo(db: AsyncSession = Depends(get_session)) -> WarehouseRepository:
    return WarehouseRepository(db)

def get_warehouse_service(repo: WarehouseRepository = Depends(get_warehouse_repo)) -> WarwehouseService:
    return WarwehouseService(repo)
