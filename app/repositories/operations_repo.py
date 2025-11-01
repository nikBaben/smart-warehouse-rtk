from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Tuple
from app.models.delivery import Delivery
from app.models.shipment import Shipment


class OperationsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_deliveries_by_warehouse(self, warehouse_id: str) -> List[Delivery]:
        """Получить все поставки для конкретного склада"""
        result = await self.session.execute(
            select(Delivery)
            .where(Delivery.warehouse_id == warehouse_id)
            .order_by(Delivery.scheduled_at.desc())
        )
        return result.scalars().all()

    async def get_all_shipments_by_warehouse(self, warehouse_id: str) -> List[Shipment]:
        """Получить все отгрузки для конкретного склада"""
        result = await self.session.execute(
            select(Shipment)
            .where(Shipment.warehouse_id == warehouse_id)
            .order_by(Shipment.scheduled_at.desc())
        )
        return result.scalars().all()

    async def get_all_operations_by_warehouse(self, warehouse_id: str) -> Tuple[List[Delivery], List[Shipment]]:
        """Получить все поставки и отгрузки для конкретного склада"""
        deliveries = await self.get_all_deliveries_by_warehouse(warehouse_id)
        shipments = await self.get_all_shipments_by_warehouse(warehouse_id)
        return deliveries, shipments