# app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from app.auth.service import auth_service
from app.auth.models import LoginRequest, AuthResponse, UserInfo, RefreshRequest, TokenResponse
from app.auth.dependencies import get_current_user, keycloak_auth_middleware

# Создаем роутер
router = APIRouter(prefix="/api/v1", tags=["auth"])


# Auth routes
@router.post("/auth/login", response_model=AuthResponse)
async def login(login_data: LoginRequest):
	"""Аутентификация пользователя"""
	auth_data = await auth_service.login(login_data.email, login_data.password)

	expires_at = datetime.now() + timedelta(seconds=auth_data['expires_in'])

	return AuthResponse(
		user_id=auth_data['user_id'],
		email=auth_data['email'],
		access_token=auth_data['access_token'],
		refresh_token=auth_data['refresh_token'],
		expires_in=auth_data['expires_in'],
		refresh_expires_in=auth_data['refresh_expires_in'],
		token_type=auth_data['token_type'],
		expires_at=expires_at.isoformat()
	)


# Используй существующую модель RefreshRequest
@router.post("/auth/logout")
async def logout(refresh_data: RefreshRequest):
    """Выход из системы"""
    success = await auth_service.logout(refresh_data.refresh_token)
    if not success:
        raise HTTPException(status_code=500, detail="Logout failed")
    return {"message": "Logout successful"}


@router.get("/auth/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
	"""Получение информации о текущем пользователе"""
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
	"""Обновление access токена"""
	token_data = await auth_service.refresh_token(refresh_data.refresh_token)
	return TokenResponse(**token_data)


@router.get("/auth/validate")
async def validate_token(token: str = Depends(keycloak_auth_middleware)):
    """Проверка access_token"""
    return {"message": "Token is valid"}


# System routes
@router.get("/health")
async def health_check():
	"""Проверка здоровья API"""
	return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/config")
async def get_config():
	"""Показать текущую конфигурацию (только для отладки)"""
	from app.core.config import settings
	return {
		"keycloak_url": settings.KEYCLOAK_URL,
		"keycloak_realm": settings.KEYCLOAK_REALM,
		"keycloak_client_id": settings.KEYCLOAK_CLIENT_ID,
		"keycloak_client_secret": "***" if settings.KEYCLOAK_CLIENT_SECRET else None,
		"debug": settings.DEBUG
	}


# Диагностические endpoints
@router.post("/auth/debug-token")
async def debug_token(token: str):
	"""Расширенная отладка токена"""
	try:
		is_valid = await auth_service.validate_token(token)
		user_info = await auth_service.get_user_info(token) if is_valid else None

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
	"""Полная диагностика аутентификации"""
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
		auth_data = await auth_service.login(login_data.email, login_data.password)
		diagnostics["steps"][-1]["end"] = time.time()
		diagnostics["steps"][-1]["success"] = True
		diagnostics["token"] = auth_data["access_token"][:50] + "..."

		# Шаг 2: Немедленная валидация
		diagnostics["steps"].append({"step": "immediate_validation", "start": time.time()})
		is_valid = await auth_service.validate_token(auth_data["access_token"])
		diagnostics["steps"][-1]["end"] = time.time()
		diagnostics["steps"][-1]["success"] = is_valid
		diagnostics["steps"][-1]["result"] = is_valid

		diagnostics["overall"] = all(step["success"] for step in diagnostics["steps"])

	except Exception as e:
		diagnostics["error"] = str(e)
		diagnostics["overall"] = False

	return diagnostics