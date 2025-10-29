# app/ws/ws_manager.py
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Set, Any
from fastapi import WebSocket


class WSManager:
    """
    Простой менеджер WS-комнат:
      - connect(ws, warehouse_id)   — принять соединение и привязать к комнате склада
      - list_rooms()                — список активных комнат (складов)
      - disconnect(ws)              — убрать сокет из всех комнат
      - broadcast_json(warehouse_id, data) — отправить JSON всем в комнате
      - broadcast_all_json(data)    — (отладка) отправить JSON всем подключённым
    НИКАКИХ локальных очередей: события прилетают через redis_forwarder и сразу рассылаются.
    """

    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, warehouse_id: str) -> None:
        await ws.accept()
        async with self._lock:
            self.rooms[warehouse_id].add(ws)
            print(f"✅ WS connected: room={warehouse_id} size={len(self.rooms[warehouse_id])}", flush=True)

    async def list_rooms(self) -> list[str]:
        async with self._lock:
            return list(self.rooms.keys())

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            empty_rooms = []
            for room_id, sockets in self.rooms.items():
                sockets.discard(ws)
                if not sockets:
                    empty_rooms.append(room_id)
            for r in empty_rooms:
                self.rooms.pop(r, None)

    async def broadcast_json(self, warehouse_id: str, data: Dict[str, Any]) -> int:
        """
        Рассылает сообщение в комнату склада. Возвращает число реально отправленных.
        Удаляет «мертвые» сокеты.
        """
        async with self._lock:
            recipients = list(self.rooms.get(warehouse_id, []))
        if not recipients:
            return 0

        dead = []
        sent = 0
        for ws in recipients:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                room = self.rooms.get(warehouse_id)
                if room is not None:
                    for ws in dead:
                        room.discard(ws)
                    if not room:
                        self.rooms.pop(warehouse_id, None)
        return sent

    async def broadcast_all_json(self, data: Dict[str, Any]) -> int:
        """
        (Для отладки) Рассылает сообщение всем подключённым сокетам вне зависимости от комнаты.
        """
        async with self._lock:
            recipients = [ws for sockets in self.rooms.values() for ws in sockets]
        if not recipients:
            return 0

        dead = []
        sent = 0
        for ws in recipients:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                # чистим все комнаты от умерших сокетов
                empty_rooms = []
                for room_id, sockets in self.rooms.items():
                    for ws in dead:
                        sockets.discard(ws)
                    if not sockets:
                        empty_rooms.append(room_id)
                for r in empty_rooms:
                    self.rooms.pop(r, None)
        return sent


manager = WSManager()
