from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models.scheduled_delivery import ScheduledDelivery


class ScheduledDeliveryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, *, id: str, product_id: Optional[str], warehouse_id: Optional[str],
                     scheduled_at, quantity: int, supplier: Optional[str] = None,
                     notes: Optional[str] = None) -> ScheduledDelivery:
        sd = ScheduledDelivery(
            id=id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            scheduled_at=scheduled_at,
            quantity=quantity,
            supplier=supplier,
            notes=notes
        )
        async with self.session.begin():
            self.session.add(sd)
            await self.session.refresh(sd)
        return sd
    
    async def get(self, id: str) -> Optional[ScheduledDelivery]:
        return await self.session.scalar(select(ScheduledDelivery)\
                                  .where(ScheduledDelivery.id == id))
    
    async def list_for_warehouse(self, warehouse_id: str, *,
                                 limit: int = 100, offset: int = 0) -> List[ScheduledDelivery]:
        result = await self.session.execute(
            select(ScheduledDelivery)\
            .where(ScheduledDelivery.warehouse_id == warehouse_id)\
            .limit(limit)\
            .offset(offset)
        )
        
        return list(result.scalars().all())
    
    