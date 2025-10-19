from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, conint, validator


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Название товара")
    category: str = Field(..., min_length=1, max_length=100, description="Категория товара")
    min_stock: conint(ge=0) = Field(0, description="Минимальный запас товара на складе") # type: ignore
    optimal_stock: conint(ge=0) = Field(100, description="Оптимальный запас товара на складе") # type: ignore

    @validator("optimal_stock")
    def validate_stock(cls, v, values):
        if "min_stock" in values and v < values["min_stock"]:
            raise ValueError("optimal_stock должен быть не меньше, чем min_stock")
        return v


class ProductCreate(ProductBase):
    id: Optional[str] = Field(None, description="ID продукта (если не указать — сгенерируется UUID)")
    warehouse_id: Optional[str] = Field(None, description="ID склада, к которому привязан продукт")


class ProductRead(ProductBase):
    id: str
    warehouse_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True  
