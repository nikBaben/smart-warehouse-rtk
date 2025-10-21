from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.product import ProductRead
from app.schemas.robot import RobotRead

class WarehouseBase(BaseModel):
    name: str = Field(..., max_length=255)
    address: str = Field(..., max_length=255)
    row_x: int = 0
    row_y: int = 0

class WarehouseCreate(WarehouseBase):
    id: Optional[str] = Field(None, description="Если не передашь — сгенерируем UUID")

class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    row_x: Optional[int] = None
    row_y: Optional[int] = None

class WarehouseResponse(WarehouseBase):
    products_count: int

    class Config:
        from_attributes = True 
