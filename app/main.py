from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import api_router
from app.api.routers import ws as ws_router
from threading import Thread
import asyncio
from app.robot_emulator.emulator import run_robot_watcher 
from app.ws.ws_manager import robot_events_broadcaster 
from app.ws.products_events import continuous_product_snapshot_streamer
from app.ws.battery_events import continuous_robot_avg_streamer
from app.ws.inventory_scans_streamer import continuous_inventory_scans_streamer
from app.ws.inventory_critical_streamer import continuous_inventory_critical_streamer
from app.ws.inventory_status import continuous_inventory_status_avg_streamer
from app.ws.robot_status_count_streamer import continuous_robot_status_count_streamer
from app.ws.robot_activity_streamer import continuous_robot_activity_history_streamer

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

# Запускаем асинхронный watcher в фоне.
@app.on_event("startup")
async def start_robot_mover():
    asyncio.create_task(run_robot_watcher(interval=5.0, max_workers=8))
    asyncio.create_task(robot_events_broadcaster())
    asyncio.create_task(continuous_product_snapshot_streamer(interval=2.0))
    asyncio.create_task(continuous_robot_avg_streamer(interval=2.0))
    asyncio.create_task(continuous_inventory_scans_streamer(interval=2.0, hours=24)),
    asyncio.create_task(continuous_inventory_critical_streamer(interval=2.0)),
    asyncio.create_task(continuous_inventory_status_avg_streamer(interval=2.0)),
    asyncio.create_task(continuous_robot_status_count_streamer(interval=2.0)),  # ⬅️ новый
    asyncio.create_task(continuous_robot_activity_history_streamer(interval=600)),
    print("🤖 Robot watcher started as background async task.")

