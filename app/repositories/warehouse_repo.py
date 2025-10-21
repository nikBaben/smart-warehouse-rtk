from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.models.warehouse import Warehouse


class WarehouseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        id: str,
        name: str,
        address: str,
        row_x: int,
        row_y: int,
    ) -> Warehouse:
        existing_warehouse = await self.session.scalar(
            select(Warehouse).where(Warehouse.name == name)
        )
        if existing_warehouse:
            raise ValueError(f"Склад с именем '{name}' уже существует.")

        warehouse = Warehouse(
            id=id,
            name=name,
            address=address,
            row_x=row_x,
            row_y=row_y,
            products_count = 0
        )

        self.session.add(warehouse)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise e

        await self.session.refresh(warehouse)
        return warehouse
    
    async def get_by_id(self, warehouse_id: str) -> Optional[Warehouse]:
        stmt = (
            select(Warehouse).where(Warehouse.id == warehouse_id)
        )
        return await self.session.scalar(stmt)

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Warehouse]:
        result = await self.session.execute(
            select(Warehouse).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
