from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, conint, validator


RobotStatus = Literal["idle", "busy", "charging", "error"] 


class RobotBase(BaseModel):
    status: RobotStatus = "idle"
    battery_level: int
    current_zone: str = Field(..., min_length=1)
    current_row: int = 0
    current_shelf: int = 0


class RobotCreate(RobotBase):
    id: Optional[str] = Field(None, description="Если не передашь — сгенерируем UUID")
  


class RobotRead(RobotBase):
    id: str
    created_at: datetime
    last_update: Optional[datetime] = None

    class Config:
        from_attributes = True  
