from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.ws_manager import ws_manager

router = APIRouter(tags=["ws"])

@router.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text() 
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
