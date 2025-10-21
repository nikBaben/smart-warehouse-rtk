from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import api_router
from app.api.routers import ws as ws_router
from threading import Thread
import asyncio
from app.robot_emulator.emulator import run_robot_watcher 
from app.ws.ws_manager import robot_events_broadcaster 
app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router.router, prefix="/api") 


@app.on_event("startup")
async def start_robot_mover():
    """
    Запускаем асинхронный watcher в фоне.
    """
    asyncio.create_task(run_robot_watcher(interval=5.0, max_workers=8))
    asyncio.create_task(robot_events_broadcaster())
    print("🤖 Robot watcher started as background async task.")

