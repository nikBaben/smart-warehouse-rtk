from fastapi import APIRouter
from app.api.routers import robots
from app.api.routers import product
from app.api.routers import warehouse
from app.api.routers import auth
from app.api.routers import user
from app.api.routers import inventory_history

api_router = APIRouter()
api_router.include_router(robots.router)
api_router.include_router(product.router)
api_router.include_router(warehouse.router)
api_router.include_router(inventory_history.router)
api_router.include_router(auth.router)
api_router.include_router(user.router)

