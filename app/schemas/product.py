from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, conint, validator


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Название товара")
    category: str = Field(..., min_length=1, max_length=100, description="Категория товара")
    article:  str = Field(..., min_length=1, max_length=100, description="Артикул товара")
    stock: conint(ge=0) = Field(100, description="Всего товаров") # type: ignore
    #min_stock: conint(ge=0) = Field(20, description="Минимальный запас товара на складе") # type: ignore
    #optimal_stock: conint(ge=0) = Field(80, description="Оптимальный запас товара на складе") # type: ignore
    current_row: int = 0
    current_shelf: str = "A"


class ProductCreate(ProductBase):
    id: Optional[str] = Field(None, description="ID продукта (если не указать — сгенерируется UUID)")
    warehouse_id: Optional[str] = Field(None, description="ID склада, к которому привязан продукт")


class ProductRead(ProductBase):
    id: str
    status: str
    current_zone: str 
    status: str
    warehouse_id: Optional[str]
    created_at: datetime


    class Config:
        from_attributes = True  
