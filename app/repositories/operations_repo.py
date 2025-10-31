from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Tuple
from app.models.delivery import Delivery
from app.models.shipment import Shipment


class OperationsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_deliveries(self) -> List[Delivery]:
        """Получить все поставки"""
        result = await self.session.execute(
            select(Delivery).order_by(Delivery.scheduled_at.desc())
        )
        return result.scalars().all()

    async def get_all_shipments(self) -> List[Shipment]:
        """Получить все отгрузки"""
        result = await self.session.execute(
            select(Shipment).order_by(Shipment.scheduled_at.desc())
        )
        return result.scalars().all()

    async def get_all_operations(self) -> Tuple[List[Delivery], List[Shipment]]:
        """Получить все поставки и отгрузки в одном запросе"""
        deliveries = await self.get_all_deliveries()
        shipments = await self.get_all_shipments()
        return deliveries, shipments