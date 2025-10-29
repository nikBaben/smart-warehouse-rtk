# app/main.py
from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import api_router
from app.api.routers import ws as ws_router

# Новое: loop-local EventBus через фабрику + форвардер в WS
from app.events.bus import get_bus_for_current_loop, close_bus_for_current_loop
from app.ws.redis_forwarder import start_redis_forwarder

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP и WS роутеры
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router.router, prefix="/api")

# Держим ссылку на фон.таску форвардера, чтобы корректно её останавливать
_redis_forwarder_task: asyncio.Task | None = None


@app.on_event("startup")
async def _startup() -> None:
    # Инициализируем Bus для ТЕКУЩЕГО loop'а (это же и connect)
    await get_bus_for_current_loop()

    # Стартуем форвардер: Redis (Pub/Sub) → WS-подписчики
    global _redis_forwarder_task
    _redis_forwarder_task = asyncio.create_task(start_redis_forwarder())
    print("🌐 API started. Redis→WS forwarder is running.")


@app.on_event("shutdown")
async def _shutdown() -> None:
    # Останавливаем форвардер
    global _redis_forwarder_task
    if _redis_forwarder_task:
        _redis_forwarder_task.cancel()
        with suppress(asyncio.CancelledError):
            await _redis_forwarder_task
        _redis_forwarder_task = None

    # Закрываем loop-local Bus
    await close_bus_for_current_loop()
    print("🛑 API stopped. Redis connection closed.")
