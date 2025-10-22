from pydantic import BaseModel, Field
from typing import Optional
from app.schemas.product import ProductRead
from app.schemas.robot import RobotRead

class WarehouseBase(BaseModel):
    name: str = Field(..., max_length=255)
    address: str = Field(..., max_length=255)
    max_products: int 

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=255)
    row_x: Optional[int] = None
    row_y: Optional[int] = None

class WarehouseResponse(WarehouseBase):
    id: str
    products_count: int

    class Config:
        from_attributes = True 
