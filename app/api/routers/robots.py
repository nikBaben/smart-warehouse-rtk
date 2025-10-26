from fastapi import APIRouter, Depends, status
from app.schemas.robot import RobotCreate, RobotRead
from app.service.robot_service import RobotService
from app.service.auth_service import AuthService
from app.api.deps import get_robot_service,get_auth_service,get_token
from app.api.deps import keycloak_auth_middleware,get_current_user
import logging

router = APIRouter(prefix="/robot", tags=["robots"],dependencies=[Depends(keycloak_auth_middleware)])

logger = logging.getLogger(__name__)
@router.post(
    "",
    response_model=RobotRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать робота",
)
async def create_robot(
    payload: RobotCreate,
    service: RobotService = Depends(get_robot_service),
    user_service: AuthService = Depends(get_auth_service),
    token: str = Depends(get_token)
):
    user_info = await user_service.get_current_user(token)
    print(user_info)
    logger.info(f"✅ User info: {user_info}")

    # 4️⃣ Создаём робота, связываем с user_id
    robot = await service.create_robot(payload, owner_id=user_info)
    return robot



@router.delete(
        "/{robot_id}",
        summary="Удалить робота",
)
async def delete_warehouse(
    robot_id: str,
    service: RobotService = Depends(get_robot_service),
):
    return await service.delete_robot(robot_id)

@router.get(
    "/get_robots_by_warehouse_id/{warehouse_id}",
    response_model=list[RobotRead],
    status_code=status.HTTP_200_OK,
    summary="Список роботов, привязанных к складу",
)
async def get_robots_by_warehouse_id(
    warehouse_id: str,
    service: RobotService = Depends(get_robot_service),
):
    robots = await service.get_robots_by_warehouse_id(warehouse_id)
    return robots
