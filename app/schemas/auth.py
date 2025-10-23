from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    email: str  # Просто str вместо EmailStr
    password: str

class AuthResponse(BaseModel):
    token: str
    user: 'UserResponse'

class UserResponse(BaseModel):
    id: int
    name: str
    role: str

class UserInfo(BaseModel):
    sub: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None  # Просто str вместо EmailStr
    email_verified: Optional[bool] = None

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    token_type: str

# Для решения циклических ссылок
AuthResponse.update_forward_refs()