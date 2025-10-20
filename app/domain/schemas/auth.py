from pydantic import BaseModel, Field
from typing import Optional

class LoginRequest(BaseModel):
    email: str = Field(..., example="operator@warehouse.com")
    password: str = Field(..., example="operator123")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    token_type: str

class AuthResponse(TokenResponse):
    user_id: Optional[str] = None
    email: Optional[str] = None
    expires_at: Optional[str] = None

class UserInfo(BaseModel):
    sub: Optional[str] = None
    name: Optional[str] = None
    preferred_username: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    email_verified: Optional[bool] = None

class RefreshRequest(BaseModel):
    refresh_token: str