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

    #Вернёт список warehouse_id, на которые сейчас есть подписчики.
    async def list_rooms(self) -> list[str]:
        async with self._lock:
            return list(self.rooms.keys())

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            for room in self.rooms.values():
                room.discard(ws)

    async def broadcast_json(self, warehouse_id: str, data: Dict[str, Any]):
        # снимок получателей под локом
        async with self._lock:
            recipients = list(self.rooms.get(warehouse_id, []))
        if not recipients:
            return

        dead = []
        for ws in recipients:          # отправляем уже без локапа
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        if dead:                        # чистим «мёртвых» под локом
            async with self._lock:
                room = self.rooms.get(warehouse_id, set())
                for ws in dead:
                    room.discard(ws)
                if not room:
                    self.rooms.pop(warehouse_id, None)

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
