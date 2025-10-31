from sqlalchemy import insert
from app.models.inventory_history import InventoryHistory

async def bulk_insert_inventory_history(session, rows: list[dict]):
    await session.execute(insert(InventoryHistory), rows)
