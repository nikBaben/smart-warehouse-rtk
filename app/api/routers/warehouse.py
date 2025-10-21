from fastapi import APIRouter, Depends, status,HTTPException,Query
from app.schemas.warehouse import WarehouseCreate, WarehouseResponse
from app.service.warehouse_service import WarwehouseService
from app.api.deps import get_warehouse_service  


router = APIRouter(prefix="/warehouse", tags=["warehouse"])

@router.post(
        "",
        response_model=WarehouseResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Создать склад"
)
async def create_warehouse(
    payload: WarehouseCreate,
    service: WarwehouseService = Depends(get_warehouse_service)
):
    robot = await service.create_warehouse(payload)
    return robot

@router.get(
        "/all",
        response_model=list[WarehouseResponse],
        status_code=status.HTTP_200_OK,
        summary="Список всех складов"
)
async def get_warehouses(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: WarwehouseService = Depends(get_warehouse_service),
):
    return await service.get_warehouses(limit=limit, offset=offset)

@router.get(
        "/{warehouse_id}",
        response_model=WarehouseResponse,
        status_code=status.HTTP_200_OK,
        summary="Получить склад по ID"
)
async def get_warehouse(
    warehouse_id: str,
    service:WarwehouseService = Depends(get_warehouse_service)
):
    warehouse = await service.get_warehouse(warehouse_id)
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Склад с id '{warehouse_id}' не найден.",
        )
    return warehouse

