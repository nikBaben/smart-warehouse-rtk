from fastapi import APIRouter, Depends, status
from app.schemas.product import ProductCreate, ProductRead
from app.service.product_service import ProductService
from app.api.deps import get_product_service  

router = APIRouter(prefix="/products", tags=["products"])

@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать продукт",
    response_description="Информация о созданном продукте",
)
async def create_product(
    payload: ProductCreate,
    service: ProductService = Depends(get_product_service),
):
    product = await service.create_product(payload)
    return product


