from fastapi import APIRouter, Depends, status, Body
from app.schemas.inventory_history import InventoryHistoryRead, InventoryHistoryFilters, FilteredInventoryHistoryResponse
from app.service.inventory_history_service import InventoryHistoryService
from app.api.deps import get_inventory_history_service  

router = APIRouter(prefix="/inventory_history", tags=["inventory_history"])


@router.get(
    "/get_inventory_history_by_warehouse_id/{warehouse_id}",
    response_model=list[InventoryHistoryRead],
    status_code=status.HTTP_200_OK,
    summary="История инвентаризации, привзяанная к складу",
)
async def get_inventory_history_by_warehouse_id(
    warehouse_id: str,
    service: InventoryHistoryService = Depends(get_inventory_history_service),
):
    inventory_history = await service.get_inventory_history_by_warehouse_id(warehouse_id)
    return inventory_history

@router.post(
    "/get_filtered_history/{warehouse_id}",
    response_model=FilteredInventoryHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить отфильтрованную историю инвентаризации",
    description="""
    Универсальный endpoint для фильтрации истории инвентаризации.
    """
)
async def get_filtered_inventory_history(
    warehouse_id: str,
    filters: InventoryHistoryFilters = Body(...),
    service: InventoryHistoryService = Depends(get_inventory_history_service),
):
    """
    Единственный endpoint для получения отфильтрованных данных
    """
    # Конвертируем фильтры в dict и убираем None значения
    filters_dict = {
        k: v for k, v in filters.dict().items() 
        if v is not None and v != ""
    }

    sort_by = filters_dict.pop('sort_by', None)
    sort_order = filters_dict.pop('sort_order', 'asc')
    page = filters_dict.pop('page', 1)
    page_size = filters_dict.pop('page_size', 50)
    
    inventory_history = await service.get_filtered_inventory_history(
        warehouse_id=warehouse_id,
        filters=filters_dict,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size
    )
    
    return FilteredInventoryHistoryResponse(
        data=inventory_history,
    )