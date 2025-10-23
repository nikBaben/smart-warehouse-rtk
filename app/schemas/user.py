from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    email: str
    name: str
    role: str = "user"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    name: str
    role: str

class UserInDB(UserBase):
    id: int
    password_hash: str

    class Config:
        from_attributes = True