from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.service.auth_service import auth_service
from app.schemas.auth import LoginRequest, AuthResponse, UserInfo, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.api.deps import get_current_user, keycloak_auth_middleware
from app.service.user_service import get_user_by_email, create_user
from app.service.kkid_user_service import get_user_by_kkid, create_kkid_user  # Импортируем новые сервисы
from app.db.session import get_session
import secrets

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session)
):
    """Аутентификация пользователя с автоматическим созданием в БД и связью с Keycloak"""
    try:
        # Аутентификация в Keycloak
        auth_data = await auth_service.login(login_data.email, login_data.password)
        
        # Получаем информацию о пользователе из Keycloak
        user_info = await auth_service.get_user_info(auth_data['access_token'])
        kkid = user_info.get('sub')  # Keycloak ID
        
        if not kkid:
            raise HTTPException(status_code=400, detail="Invalid user info from Keycloak")
        
        # Пытаемся найти пользователя по Keycloak ID
        user = await get_user_by_kkid(session, kkid)
        
        if not user:
            # Если не нашли по Keycloak ID, ищем по email
            user = await get_user_by_email(session, login_data.email)
            
            if not user:
                # Создаем нового пользователя
                roles = user_info.get('realm_access', {}).get('roles', [])
                user_role = roles[3] if len(roles) > 3 else 'user'
                
                user_create = UserCreate(
                    email=login_data.email,
                    password=login_data.password,
                    name=user_info.get('name', user_info.get('preferred_username', login_data.email)),
                    role=user_role
                )
                user = await create_user(session, user_create)
                print(f"✅ Created new user: {user.id}, email: {user.email}")
            
            # Создаем связь между Keycloak ID и User ID
            await create_kkid_user(session, kkid, user.id)
            print(f"✅ Created kkid_userid link: kkid={kkid}, user_id={user.id}")
        else:
            print(f"✅ User found via kkid: {user.id}")
        
        # Формируем ответ - ВАЖНО: создаем словарь для UserResponse
        return AuthResponse(
            token=auth_data['access_token'],
            user={
                "id": user.id,
                "name": user.name,
                "role": user.role
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error in login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



# System routes
@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/config")
async def get_config():
    from app.core.config import settings
    return {
        "keycloak_url": settings.KEYCLOAK_URL,
        "keycloak_realm": settings.KEYCLOAK_REALM,
        "keycloak_client_id": settings.KEYCLOAK_CLIENT_ID,
        "keycloak_client_secret": "***" if settings.KEYCLOAK_CLIENT_SECRET else None,
        "debug": settings.DEBUG
    }

