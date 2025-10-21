from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from app.ws.ws_manager import manager

router = APIRouter()

@router.websocket("/ws/warehouses/{warehouse_id}")
async def ws_warehouse(ws: WebSocket, warehouse_id: str = Path(...)):
    await manager.connect(ws, warehouse_id)
    try:
        while True:
            await ws.receive_text()  # держим соединение
    except WebSocketDisconnect:
        await manager.disconnect(ws)
