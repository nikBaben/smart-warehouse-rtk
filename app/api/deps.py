from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Repositories
from app.repositories.robot_repo import RobotRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.warehouse_repo import WarehouseRepository
from app.repositories.user_repo import UserRepository
from app.repositories.kkid_user_repo import KkidUserRepository
from app.repositories.inventory_history_repo import InventoryHistoryRepository
from app.repositories.alarm_repo import AlarmRepository

# Services
from app.service.robot_service import RobotService
from app.service.product_service import ProductService
from app.service.warehouse_service import WarehouseService 
from app.service.auth_service import AuthService
from app.service.keycloak_service import KeycloakService
from app.service.user_service import UserService
from app.service.inventory_history_service import InventoryHistoryService
from app.service.alarm_service import AlarmService

# DB
from app.db.session import get_session

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()


# --- Repositories ---
def get_robot_repo(db: AsyncSession = Depends(get_session)) -> RobotRepository:
    return RobotRepository(db)

def get_product_repo(db: AsyncSession = Depends(get_session)) -> ProductRepository:
    return ProductRepository(db)

def get_warehouse_repo(db: AsyncSession = Depends(get_session)) -> WarehouseRepository:
    return WarehouseRepository(db)

def get_user_repo(db: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(db)

def get_kkid_user_repo(db: AsyncSession = Depends(get_session)) -> KkidUserRepository:
    return KkidUserRepository(db)

def get_alarm_repo(db: AsyncSession = Depends(get_session)) -> AlarmRepository:
    return AlarmRepository(db)

# --- Services ---
def get_robot_service(repo: RobotRepository = Depends(get_robot_repo)) -> RobotService:
    return RobotService(repo)

def get_product_service(repo: ProductRepository = Depends(get_product_repo)) -> ProductService:
    return ProductService(repo)

def get_warehouse_service(repo: WarehouseRepository = Depends(get_warehouse_repo)) -> WarehouseService:
    return WarehouseService(repo)

async def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    keycloak_service = KeycloakService()
    user_service = UserService(session)
    return AuthService(keycloak_service, user_service)

def get_user_service(repo: UserRepository = Depends(get_user_repo)) -> UserService:
    return UserService(repo)

def get_keycloak_service() -> KeycloakService:
    return KeycloakService()

def get_inventory_history_repo(db: AsyncSession = Depends(get_session)) -> InventoryHistoryRepository:
    return InventoryHistoryRepository(db)

def get_inventory_history_service(repo: InventoryHistoryRepository = Depends(get_inventory_history_repo)) -> InventoryHistoryService:
    return InventoryHistoryService(repo)

def  get_alarm_service(repo: AlarmRepository = Depends(get_alarm_repo)) -> AlarmService:
    return AlarmService(repo)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_svc: KeycloakService = Depends(get_keycloak_service)
):
    """Зависимость для получения текущего пользователя"""
    token = credentials.credentials
    logger.info("Getting current user from token")

    if not await auth_svc.validate_token(token):
        logger.error("Token validation failed in get_current_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    try:
        user_info = await auth_svc.get_user_info(token)
        logger.info(f"User authenticated: {user_info.get('email')}")
        return user_info
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to get user information"
        )


async def keycloak_auth_middleware(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_svc: KeycloakService = Depends(get_keycloak_service)
):
    """Middleware для проверки аутентификации — аналог Go middleware"""
    token = credentials.credentials
    logger.info("Middleware token validation")

    # Используем validate_token_for_middleware (предполагается, что он есть в AuthService)
    if not await auth_svc.validate_token(token):
        logger.error("Middleware token validation failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    logger.info("Middleware token validation successful")
    return token


async def get_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Получение токена из заголовка Authorization"""
    return credentials.credentials