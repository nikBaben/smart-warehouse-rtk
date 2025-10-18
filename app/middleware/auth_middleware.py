# app/middleware.py
from fastapi import Request, HTTPException, status
import re

# Публичные пути, не требующие аутентификации
PUBLIC_PATHS = [
	r"^/docs",
	r"^/redoc",
	r"^/openapi\.json",
	r"^/auth/login",
	r"^/auth/refresh",
	r"^/auth/validate",
	r"^/api/robots/data",
	r"^/health",
	r"^/$"
]


async def auth_middleware(request: Request, call_next):
	"""Глобальный middleware аутентификации"""
	path = request.url.path

	# Пропускаем публичные пути
	if any(re.match(pattern, path) for pattern in PUBLIC_PATHS):
		return await call_next(request)

	# Проверяем Authorization header
	auth_header = request.headers.get("Authorization")
	if not auth_header or not auth_header.startswith("Bearer "):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Missing or invalid authorization header"
		)

	token = auth_header.replace("Bearer ", "")

	# Проверяем токен
	from app.auth.service import auth_service
	if not await auth_service.validate_token_for_middleware(token):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired token"
		)

	response = await call_next(request)
	return response


# Добавление middleware в приложение
from app.main import app

app.middleware("http")(auth_middleware)