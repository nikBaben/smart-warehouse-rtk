from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.service.auth_service import auth_service
from app.domain.schemas.auth import LoginRequest, AuthResponse, UserInfo, RefreshRequest, TokenResponse
from app.domain.schemas.user import UserCreate, UserResponse
from app.api.dependencies import get_current_user, keycloak_auth_middleware
from app.service.user_service import get_user_by_email, create_user
from app.service.kkid_user_service import get_user_by_kkid, create_kkid_user  # Импортируем новые сервисы
from app.db.session import get_session
import secrets

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login", response_model=AuthResponse)
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

"""
@router.post("/auth/logout")
async def logout(refresh_data: RefreshRequest):
    success = await auth_service.logout(refresh_data.refresh_token)  # Используем экземпляр
    if not success:
        raise HTTPException(status_code=500, detail="Logout failed")
    return {"message": "Logout successful"}


@router.get("/auth/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return UserInfo(
        sub=current_user.get('sub'),
        name=current_user.get('name'),
        preferred_username=current_user.get('preferred_username'),
        given_name=current_user.get('given_name'),
        family_name=current_user.get('family_name'),
        email=current_user.get('email'),
        email_verified=current_user.get('email_verified')
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: RefreshRequest):
    token_data = await auth_service.refresh_token(refresh_data.refresh_token)  # Используем экземпляр
    return TokenResponse(**token_data)


@router.get("/auth/validate")
async def validate_token(
    token: str = Depends(keycloak_auth_middleware),
    session: AsyncSession = Depends(get_session)
):
    
    # Получаем информацию о пользователе из токена
    user_info = await auth_service.get_user_info(token)
    
    if user_info and user_info.get('email'):
        # Проверяем существование пользователя в БД
        user = await get_user_by_email(session, user_info['email'])
        if not user:
            # Создаем пользователя в нашей БД
            roles = user_info.get('realm_access', {}).get('roles', [])
            user_role = roles[3] if len(roles) > 3 else 'user'
            
            # Генерируем случайный пароль для пользователя
            import secrets
            random_password = secrets.token_urlsafe(32)
            
            user_create = UserCreate(
                email=user_info['email'],
                password=random_password,  # Случайный пароль, будет захэширован
                name=user_info.get('name', user_info.get('preferred_username', user_info['email'])),
                role=user_role
            )
            user = await create_user(session, user_create)
            return {
                "message": "Token is valid", 
                "user_created": True,
                "user_id": user.id
            }
        else:
            return {
                "message": "Token is valid", 
                "user_created": False,
                "user_id": user.id
            }
    
    return {
        "message": "Token is valid", 
        "user_created": False
    }

    """

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

"""
# Диагностические endpoints
@router.post("/auth/debug-token")
async def debug_token(token: str):
    try:
        is_valid = await auth_service.validate_token(token)  # Используем экземпляр
        user_info = await auth_service.get_user_info(token) if is_valid else None  # Используем экземпляр

        return {
            "valid": is_valid,
            "user_info": user_info
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


@router.post("/auth/diagnose")
async def diagnose_auth(login_data: LoginRequest):
    import time
    from datetime import datetime

    diagnostics = {
        "timestamp": datetime.now().isoformat(),
        "server_time": time.time(),
        "steps": []
    }

    try:
        # Шаг 1: Логин
        diagnostics["steps"].append({"step": "login", "start": time.time()})
        auth_data = await auth_service.login(login_data.email, login_data.password)  # Используем экземпляр
        diagnostics["steps"][-1]["end"] = time.time()
        diagnostics["steps"][-1]["success"] = True
        diagnostics["token"] = auth_data["access_token"][:50] + "..."

        # Шаг 2: Немедленная валидация
        diagnostics["steps"].append({"step": "immediate_validation", "start": time.time()})
        is_valid = await auth_service.validate_token(auth_data["access_token"])  # Используем экземпляр
        diagnostics["steps"][-1]["end"] = time.time()
        diagnostics["steps"][-1]["success"] = is_valid
        diagnostics["steps"][-1]["result"] = is_valid

        diagnostics["overall"] = all(step["success"] for step in diagnostics["steps"])

    except Exception as e:
        diagnostics["error"] = str(e)
        diagnostics["overall"] = False

    return diagnostics

"""