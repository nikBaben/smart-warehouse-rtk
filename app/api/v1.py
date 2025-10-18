from fastapi import APIRouter
from app.api.routers import robots

api_router = APIRouter()
api_router.include_router(robots.router)
