# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.core.config import settings
from app.api.routers.auth import router as api_router

app = FastAPI(
	title="Smart Warehouse API",
	version="1.0.0",
	description="API для системы управления складской логистикой",
	docs_url="/docs",
	redoc_url="/redoc",
	openapi_url="/openapi.json",
)

# CORS middleware ДОЛЖЕН быть первым
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:8000",
		"http://localhost:3000",
		"http://127.0.0.1:8000",
		"http://127.0.0.1:3000",
		"http://0.0.0.0:8000",
		# Добавь другие origins если нужно
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
	expose_headers=["*"],
)

# Подключаем роутер
app.include_router(api_router)


# Корневой endpoint
@app.get("/")
async def root():
	return {
		"message": "Smart Warehouse API",
		"version": "1.0.0",
		"docs": "/docs",
		"health": "/api/v1/health"
	}


@app.get("/health")
async def health_check():
	"""Простой health check для тестирования CORS"""
	return {"status": "healthy", "service": "smart-warehouse"}


# Кастомная OpenAPI схема для корректного отображения в Swagger
def custom_openapi():
	if app.openapi_schema:
		return app.openapi_schema

	openapi_schema = get_openapi(
		title="Smart Warehouse API",
		version="1.0.0",
		description="API для системы управления складской логистикой",
		routes=app.routes,
	)

	# Добавляем сервер для Swagger UI
	openapi_schema["servers"] = [
		{
			"url": "http://localhost:8000",
			"description": "Development server"
		}
	]

	app.openapi_schema = openapi_schema
	return app.openapi_schema


app.openapi = custom_openapi

if __name__ == "__main__":
	import uvicorn

	uvicorn.run(
		"app.main:app",
		host=settings.HOST,
		port=settings.PORT,
		reload=settings.DEBUG
	)