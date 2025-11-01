from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.models.enums import DeliveryStatus, ShipmentStatus


class DeliveryShortResponse(BaseModel):
    id: str
    name: Optional[str]
    supplier: Optional[str]
    scheduled_at: datetime
    quantity: int
    status: DeliveryStatus
    warehouse_id: Optional[str]
    
    class Config:
        from_attributes = True


class ShipmentShortResponse(BaseModel):
    id: str
    name: Optional[str]
    customer: Optional[str]
    scheduled_at: datetime
    quantity: int
    status: ShipmentStatus
    warehouse_id: Optional[str]
    
    class Config:
        from_attributes = True


class AllOperationsResponse(BaseModel):
    deliveries: List[DeliveryShortResponse]
    shipments: List[ShipmentShortResponse]