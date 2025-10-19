from fastapi import APIRouter
from app.api.routers import robots
from app.api.routers import product

api_router = APIRouter()
api_router.include_router(robots.router)
api_router.include_router(product.router)
