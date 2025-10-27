import asyncio
import json
from collections import defaultdict
from typing import Dict, Set, Any
import janus
from fastapi import WebSocket

# --- ДВЕ ОЧЕРЕДИ ВМЕСТО ОДНОЙ ---
EVENTS_COMMON: janus.Queue[Dict[str, Any]] = janus.Queue(maxsize=2000)  # «важные» и прочие события
EVENTS_ROBOT:  janus.Queue[Dict[str, Any]] = janus.Queue(maxsize=2000)  # телеметрия роботов (позиции/сканы)

#затычка для запуска ИСПРАВИТЬ!!!!
EVENTS = {
    "ROBOT_ACTIVITY": "robot_activity",
    "ROBOT_STATUS": "robot_status", 
    "TASK_UPDATE": "task_update",
    "SYSTEM_ALERT": "system_alert",
    "ROBOT_POSITION": "robot.position",
    "PRODUCT_SCAN": "product.scan"
}

class WSManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, warehouse_id: str):
        await ws.accept()
        async with self._lock:
            self.rooms[warehouse_id].add(ws)

    async def list_rooms(self) -> list[str]:
        async with self._lock:
            return list(self.rooms.keys())

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            for room in self.rooms.values():
                room.discard(ws)

    async def broadcast_json(self, warehouse_id: str, data: Dict[str, Any]):
        async with self._lock:
            recipients = list(self.rooms.get(warehouse_id, []))
        if not recipients:
            return

        dead = []
        for ws in recipients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                room = self.rooms.get(warehouse_id, set())
                for ws in dead:
                    room.discard(ws)
                if not room:
                    self.rooms.pop(warehouse_id, None)

manager = WSManager()

# --- ВСПОМОГАТЕЛЬНО: безопасно положить в очередь с вытеснением самого старого ---
def _put_drop_oldest(q: janus.Queue[Dict[str, Any]], item: Dict[str, Any]) -> None:
    try:
        q.sync_q.put_nowait(item)
    except Exception:
        # переполнено — вытесняем старый элемент той же очереди
        try:
            q.sync_q.get_nowait()
        except Exception:
            pass
        try:
            q.sync_q.put_nowait(item)
        except Exception:
            pass

# --- ПУБЛИКАТОРЫ ДЛЯ ДВУХ КАНАЛОВ (вызывать из вашей бизнес-логики) ---
def publish_common(event: Dict[str, Any]) -> None:
    _put_drop_oldest(EVENTS_COMMON, event)

def publish_robot(event: Dict[str, Any]) -> None:
    _put_drop_oldest(EVENTS_ROBOT, event)

# Пример: в робот-вотчере замените _emit(...) на:
#   if event["type"] in ("robot.position", "product.scan"):
#       publish_robot(event)
#   else:
#       publish_common(event)

# --- МУЛЬТИПЛЕКСИРОВАННЫЙ БРОДКАСТЕР ---
# Политика: всегда стараемся отправлять общие события; между ними — по одному роботному (fair round-robin).
ROBOT_RATIO = 1  # сколько роботных допускаем между двумя общими (0 => строгий приоритет общих)

async def robot_events_broadcaster():
    try:
        robot_allow = ROBOT_RATIO
        while True:
            event = None

            # 1) Пытаемся мгновенно взять «общее»
            try:
                event = EVENTS_COMMON.async_q.get_nowait()
            except asyncio.QueueEmpty:
                event = None

            # 2) Если общих нет — иногда разрешаем роботное
            if event is None and robot_allow > 0:
                try:
                    event = EVENTS_ROBOT.async_q.get_nowait()
                    robot_allow -= 1
                except asyncio.QueueEmpty:
                    event = None

            # 3) Если нет ни одного — ждём первое доступное из двух (без busy-wait)
            if event is None:
                common_task = asyncio.create_task(EVENTS_COMMON.async_q.get())
                robot_task  = asyncio.create_task(EVENTS_ROBOT.async_q.get())
                done, pending = await asyncio.wait(
                    {common_task, robot_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                task = done.pop()
                event = task.result()
                # отменяем невыполненную
                for t in pending:
                    t.cancel()

                # если пришло общее — сбрасываем квоту роботных, чтобы вновь дать приоритет общим
                if task is common_task:
                    robot_allow = ROBOT_RATIO
                else:
                    robot_allow = max(0, robot_allow - 1)

            # 4) Отправляем
            wh = event.get("warehouse_id")
            if wh:
                await manager.broadcast_json(wh, event)
    except asyncio.CancelledError:
        pass
