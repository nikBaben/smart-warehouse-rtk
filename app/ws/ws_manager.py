import asyncio
import json
from collections import defaultdict
from typing import Dict, Set, Any
import janus
from fastapi import WebSocket

EVENTS: janus.Queue[Dict[str, Any]] = janus.Queue(maxsize=2000)

class WSManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, warehouse_id: str):
        await ws.accept()
        async with self._lock:
            self.rooms[warehouse_id].add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            for room in self.rooms.values():
                room.discard(ws)

    async def broadcast_json(self, warehouse_id: str, data: Dict[str, Any]):
        async with self._lock:
            dead = []
            for ws in self.rooms.get(warehouse_id, []):
                try:
                    await ws.send_text(json.dumps(data))
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.rooms[warehouse_id].discard(ws)

manager = WSManager()

#Фоновая задача: пересылает события из очереди WS-подписчикам
async def robot_events_broadcaster():
    try:
        while True:
            event = await EVENTS.async_q.get()
            wh = event.get("warehouse_id")
            if not wh:
                continue
            await manager.broadcast_json(wh, event)
    except asyncio.CancelledError:
        pass
