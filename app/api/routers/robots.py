from fastapi import APIRouter, Depends, status
from app.schemas.robot import RobotCreate, RobotRead
from app.service.robot_service import RobotService
from app.api.deps import get_robot_service  
from app.api.deps import keycloak_auth_middleware  

router = APIRouter(prefix="/robot", tags=["robots"])#,dependencies=[Depends(keycloak_auth_middleware)]

@router.post(
    "",
    response_model=RobotRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать робота",
)
async def create_robot(
    payload: RobotCreate,
    service: RobotService = Depends(get_robot_service),
):
    robot = await service.create_robot(payload)
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
    summary="Список роботов, привзяанных к складу",
)
async def get_robots_by_warehouse_id(
    warehouse_id: str,
    service: RobotService = Depends(get_robot_service),
):
    robots = await service.get_robots_by_warehouse_id(warehouse_id)
    return robots
