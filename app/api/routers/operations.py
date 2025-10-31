from fastapi import APIRouter, Depends
from app.service.operations_service import OperationsService
from app.schemas.operations import AllOperationsResponse
from app.api.deps import get_operations_service

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=AllOperationsResponse)
async def get_all_operations(
    operations_service: OperationsService = Depends(get_operations_service)
):
    """
    Получить все поставки и отгрузки
    
    Возвращает краткую информацию о всех поставках и отгрузках в системе,
    отсортированных по дате планирования (сначала новые)
    """
    return await operations_service.get_all_operations()


@router.get("/deliveries")
async def get_all_deliveries(
    operations_service: OperationsService = Depends(get_operations_service)
):
    """Получить все поставки"""
    return await operations_service.get_all_deliveries()


@router.get("/shipments")
async def get_all_shipments(
    operations_service: OperationsService = Depends(get_operations_service)
):
    """Получить все отгрузки"""
    return await operations_service.get_all_shipments()