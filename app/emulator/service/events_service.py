from datetime import datetime, timezone
from app.events.bus import get_bus_for_current_loop, close_bus_for_current_loop, ROBOT_CH, COMMON_CH
from config import SEND_ROBOT_POSITION
from state_service import should_emit_position
from coords_service import shelf_num_to_str

async def emit(evt: dict) -> None:
    t = evt.get("type", "")
    ch = ROBOT_CH if t.startswith("robot.position") or t in {
        "robot.positions", "robot.positions.diff", "robot.positions.keepalive", "product.scan"
    } else COMMON_CH
    bus = await get_bus_for_current_loop()
    await bus.publish(ch, evt)

async def emit_position_if_needed(robot) -> None:
    if not SEND_ROBOT_POSITION or not should_emit_position(robot):
        return
    x = int(robot.current_shelf or 0)
    y = int(robot.current_row or 0)
    await emit({
        "type": "robot.position",
        "warehouse_id": robot.warehouse_id,
        "robot_id": robot.id,
        "x": x, "y": y,
        "shelf": shelf_num_to_str(x),
        "battery_level": round(float(robot.battery_level or 0.0), 1),
        "status": (robot.status or "idle"),
        "ts": datetime.now(timezone.utc).isoformat(),
    })


