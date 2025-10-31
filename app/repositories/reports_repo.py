from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract, and_
from typing import List, Tuple
from datetime import datetime
from app.models.delivery import Delivery
from app.models.shipment import Shipment


class ReportsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_deliveries_by_month(self, year: int, month: int) -> List[Delivery]:
        """Получить поставки за конкретный месяц"""
        result = await self.session.execute(
            select(Delivery)
            .where(
                and_(
                    extract('year', Delivery.scheduled_at) == year,
                    extract('month', Delivery.scheduled_at) == month
                )
            )
            .order_by(Delivery.scheduled_at)
        )
        return result.scalars().all()

    async def get_shipments_by_month(self, year: int, month: int) -> List[Shipment]:
        """Получить отгрузки за конкретный месяц"""
        result = await self.session.execute(
            select(Shipment)
            .where(
                and_(
                    extract('year', Shipment.scheduled_at) == year,
                    extract('month', Shipment.scheduled_at) == month
                )
            )
            .order_by(Shipment.scheduled_at)
        )
        return result.scalars().all()

    async def get_operations_by_year(self, year: int) -> Tuple[List[Delivery], List[Shipment]]:
        """Получить все поставки и отгрузки за год"""
        deliveries_result = await self.session.execute(
            select(Delivery)
            .where(extract('year', Delivery.scheduled_at) == year)
            .order_by(Delivery.scheduled_at)
        )
        
        shipments_result = await self.session.execute(
            select(Shipment)
            .where(extract('year', Shipment.scheduled_at) == year)
            .order_by(Shipment.scheduled_at)
        )
        
        return deliveries_result.scalars().all(), shipments_result.scalars().all()