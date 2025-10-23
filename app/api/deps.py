from fastapi import Depends, HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.robot_repo import RobotRepository
from app.service.robot_service import RobotService
from app.repositories.product_repo import ProductRepository
from app.service.product_service import ProductService
from app.repositories.warehouse_repo import WarehouseRepository
from app.service.warehouse_service import WarwehouseService
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.service.auth_service import auth_service
from app.db.session import get_session
import logging

logger = logging.getLogger(__name__)
security = HTTPBearer()



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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
	"""Зависимость для получения текущего пользователя"""
	token = credentials.credentials

	logger.info("Getting current user from token")

	if not await auth_service.validate_token(token):
		logger.error("Token validation failed in get_current_user")
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired token"
		)

	try:
		user_info = await auth_service.get_user_info(token)
		logger.info(f"User authenticated: {user_info.get('email')}")
		return user_info
	except Exception as e:
		logger.error(f"Failed to get user info: {e}")
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Failed to get user information"
		)


async def keycloak_auth_middleware(credentials: HTTPAuthorizationCredentials = Depends(security)):
	"""Middleware для проверки аутентификации - аналог Go middleware"""
	token = credentials.credentials

	logger.info("Middleware token validation")

	# Используем validate_token_for_middleware
	if not await auth_service.validate_token_for_middleware(token):
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