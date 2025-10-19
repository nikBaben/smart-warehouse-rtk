from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        id: str,
        name: str,
        category: int,
        min_stock: str,
        optimal_stock: int,
    ) -> Product:
        product = Product(
            id=id,
            name=name,
            category=category,
            min_stock=min_stock,
            optimal_stock=optimal_stock,
        )
        self.session.add(product)
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            raise e
        await self.session.refresh(product)
        return product

    async def get(self, id: str) -> Optional[Product]:
        res = await self.session.execute(select(Product).where(Product.id == id))
        return res.scalar_one_or_none()
