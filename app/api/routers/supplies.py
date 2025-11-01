from fastapi import APIRouter, Depends, HTTPException
from app.service.operations_service import OperationsService
from app.schemas.supplies import AllOperationsResponse
from app.api.deps import get_operations_service

router = APIRouter(prefix="/supplies", tags=["supplies"])


@router.get("/warehouse/{warehouse_id}", response_model=AllOperationsResponse)
async def get_all_operations_by_warehouse(
    warehouse_id: str,
    operations_service: OperationsService = Depends(get_operations_service)
):
    """
    Получить все поставки и отгрузки для конкретного склада
    """
    return await operations_service.get_all_operations_by_warehouse(warehouse_id)


@router.get("/warehouse/{warehouse_id}/deliveries")
async def get_all_deliveries_by_warehouse(
    warehouse_id: str,
    operations_service: OperationsService = Depends(get_operations_service)
):
    """Получить все поставки для конкретного склада"""
    return await operations_service.get_all_deliveries_by_warehouse(warehouse_id)


@router.get("/warehouse/{warehouse_id}/shipments")
async def get_all_shipments_by_warehouse(
    warehouse_id: str,
    operations_service: OperationsService = Depends(get_operations_service)
):
    """Получить все отгрузки для конкретного склада"""
    return await operations_service.get_all_shipments_by_warehouse(warehouse_id)