from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, conint, validator


class ScheduledDeliveryBase(BaseModel):
    product_id: Optional[str] = Field(None, description="product id")
    warehouse_id: Optional[str] = Field(None, description="Warehouse id")
    scheduled_at: datetime = Field(..., description="Запланированное время доставки")
    quantity: conint(ge=0) = Field(..., description="Запланированное количество доставляемого товара")
    supplier: Optional[str] = Field(None, description="Имя поставщика")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")
    
    # @validator("scheduled_at")
    # def scheduled_must_be_future(cls, time: datetime) -> datetime:
    #     if time.tzinfo is None:
    #         time = time.replace(tzinfo=timezone.utc)
    #     if time <= datetime.now(timezone.utc):
    #         raise ValueError(f"Время запланированной поставки должно быть будущим\n\
    #                          локальное время:")

class ScheduledDeliveryCreate(ScheduledDeliveryBase):
    id: Optional[str] = Field(None, description="Optional id")


class ScheduledDeliveryRead(ScheduledDeliveryBase):
    id: str
    status: str
    create_at: datetime
    
    class Config:
        from_attributes = True