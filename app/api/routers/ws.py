from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from app.ws.ws_manager import manager
from app.db.session import async_session
from app.ws.battery_events import publish_robot_avg_snapshot
from app.ws.inventory_critical_streamer import publish_critical_unique_articles_snapshot
from app.ws.inventory_scans_streamer import publish_inventory_scanned_24h_snapshot
from app.ws.inventory_status import publish_status_avg_snapshot
from app.ws.products_events import publish_product_snapshot
from app.ws.robot_activity_streamer import publish_robot_activity_series_from_history
from app.ws.robot_status_count_streamer import publish_robot_status_count_snapshot

router = APIRouter()

@router.websocket("/ws/warehouses/{warehouse_id}")
async def ws_warehouse(ws: WebSocket, warehouse_id: str = Path(...)):
    await manager.connect(ws, warehouse_id)
    try:
        async with async_session() as session:
            await publish_robot_avg_snapshot(session, warehouse_id)
            await publish_critical_unique_articles_snapshot(session, warehouse_id)
            await publish_inventory_scanned_24h_snapshot(session, warehouse_id)
            await publish_status_avg_snapshot(session, warehouse_id)
            await publish_product_snapshot(session, warehouse_id)
            await publish_robot_activity_series_from_history(session, warehouse_id)
            await publish_robot_status_count_snapshot(session, warehouse_id)
        while True:
            await ws.receive_text()  # держим соединение
    except WebSocketDisconnect:
        await manager.disconnect(ws)
