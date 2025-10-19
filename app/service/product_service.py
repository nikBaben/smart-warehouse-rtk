# app/service/robot_service.py
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.schemas.product import ProductCreate
from app.repositories.product_repo import ProductRepository
from app.models.product import Product

class ProductService:
    def __init__(self, repo: ProductRepository):
        self.repo = repo

    async def create_product(self, data: ProductCreate) -> Product:
        product_id = data.id or str(uuid4())

        # Мягкая проверка, если id прислали явно (снимет 99% ложных конфликтов по PK)
        if data.id:
            existing = await self.repo.get(product_id)
            if existing:
                raise HTTPException(status_code=409, detail="Product with this id already exists")

        try:
            product = await self.repo.create(
                id=product_id,
                name=data.name,
                category=data.category,
                min_stock=data.min_stock,
                optimal_stock=data.optimal_stock,
            )
            return product

        except IntegrityError as e:
            # Попробуем вытащить SQLSTATE (psycopg2 и asyncpg через SA обычно дают .orig)
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or e.orig or e)

            if code == "23505":  # unique_violation
                raise HTTPException(status_code=409, detail="Productt with this id already exists")
            if code == "23502":  # not_null_violation
                raise HTTPException(status_code=400, detail="Missing required field (NOT NULL violation)")
            if code == "23503":  # fk_violation
                raise HTTPException(status_code=422, detail="Related entity not found (FK violation)")
            # по умолчанию — 500, но с коротким описанием чтобы дебажить
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")
