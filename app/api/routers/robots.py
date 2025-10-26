from fastapi import APIRouter, Depends, status
from app.schemas.robot import RobotCreate, RobotRead
from app.service.robot_service import RobotService
from app.service.user_service import UserService
from app.api.deps import get_robot_service,get_user_service
from app.api.deps import keycloak_auth_middleware,get_current_user

router = APIRouter(prefix="/robot", tags=["robots"],dependencies=[Depends(keycloak_auth_middleware)])

@router.post(
    "",
    response_model=RobotRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать робота",
)
async def create_robot(
    payload: RobotCreate,
    service: RobotService = Depends(get_robot_service),
    user_info: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    # 1️⃣ Извлекаем идентификаторы из токена
    kkid = user_info.get("sub") or user_info.get("sid")
    email = user_info.get("email")

    # 2️⃣ Получаем/создаём пользователя в БД
    user = await user_service.get_or_create_user_from_keycloak(
        kkid=kkid,
        email=email,
        user_info=user_info
    )

    # 3️⃣ ID из твоей таблицы User
    user_id = user.id
    print(f"✅ User from DB: {user.email} (id={user_id})")

    # 4️⃣ Создаём робота, связываем с user_id
    robot = await service.create_robot(payload, owner_id=user_id)
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
