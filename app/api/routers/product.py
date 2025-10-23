from fastapi import APIRouter, Depends, status
from app.schemas.product import ProductCreate, ProductRead
from app.service.product_service import ProductService
from app.api.deps import get_product_service  
from app.api.deps import keycloak_auth_middleware
  
router = APIRouter(prefix="/products", tags=["products"],dependencies=[Depends(keycloak_auth_middleware)])

@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать продукт",
)
async def create_product(
    payload: ProductCreate,
    service: ProductService = Depends(get_product_service),
):
    product = await service.create_product(payload)
    return product

@router.get(
    "/get_products_by_warehouse_id/{warehouse_id}",
    response_model=list[ProductRead],
    status_code=status.HTTP_200_OK,
    summary="Список товаров, привзяанных к складу",
)
async def get_products_by_warehouse_id(
    warehouse_id: str,
    service: ProductService = Depends(get_product_service),
):
    robots = await service.get_products_by_warehouse_id(warehouse_id)
    return robots

