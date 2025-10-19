from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, conint, validator


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    min_stock: int = 0
    optimal_stock: int = 0


class ProductCreate(ProductBase):
    id: Optional[str] = Field(None, description="Если не передашь — сгенерируем UUID")
  


class ProductRead(ProductBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True  
