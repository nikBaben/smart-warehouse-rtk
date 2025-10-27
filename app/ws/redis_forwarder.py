# app/ws/redis_forwarder.py
from __future__ import annotations

import asyncio
import json
import contextlib
from typing import Any, Dict, Optional

from app.events.bus import get_bus_for_current_loop, ROBOT_CH, COMMON_CH
from app.ws.ws_manager import manager


async def _dispatch_to_ws(event: Dict[str, Any]) -> None:
    wh: Optional[str] = event.get("warehouse_id")
    if not wh:
        return
    try:
        await manager.broadcast_json(wh, event)
    except Exception as e:
        print(f"⚠️ redis_forwarder: broadcast error: {e}", flush=True)


async def start_redis_forwarder(
    retry_initial_delay: float = 1.0,
    retry_max_delay: float = 30.0,
) -> None:
    """
    Подписка на Redis Pub/Sub и форвардинг событий в WebSocket-комнаты.
    Автоматически переподключается при ошибках. Работает в ТЕКУЩЕМ event loop'е.
    """
    delay = retry_initial_delay

    while True:
        pubsub = None
        try:
            # Берем loop-local EventBus (фабрика сама подключит клиент при первом вызове)
            bus = await get_bus_for_current_loop()
            pubsub = await bus.pubsub()
            await pubsub.subscribe(ROBOT_CH, COMMON_CH)
            print(f"🔌 redis_forwarder: subscribed to {ROBOT_CH}, {COMMON_CH}", flush=True)

            # Сбрасываем бэкофф после успешной подписки
            delay = retry_initial_delay

            # Основной цикл чтения Pub/Sub
            async for msg in pubsub.listen():
                # redis-py asyncio возвращает dict вида:
                # {"type": "message", "channel": "<ch>", "data": "<json string>"}
                if not isinstance(msg, dict) or msg.get("type") != "message":
                    continue
                raw = msg.get("data")
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except Exception:
                    continue

                await _dispatch_to_ws(event)

        except asyncio.CancelledError:
            # Корректный shutdown — пробрасываем дальше, cleanup в finally
            raise
        except Exception as e:
            print(
                f"❌ redis_forwarder: connection loop error: {e}. "
                f"Reconnecting in {delay:.1f}s",
                flush=True,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, retry_max_delay)
        finally:
            # Пытаемся аккуратно отписаться/закрыть pubsub при реконнекте/остановке
            if pubsub is not None:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe(ROBOT_CH, COMMON_CH)
                with contextlib.suppress(Exception):
                    await pubsub.close()
            print("🔚 redis_forwarder: pubsub closed", flush=True)
