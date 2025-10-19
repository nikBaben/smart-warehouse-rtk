from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.schemas.product import ProductCreate
from app.repositories.product_repo import ProductRepository
from app.models.product import Product


class ProductService:
    def __init__(self, repo: ProductRepository):
        self.repo = repo

    async def create_product(self, data: ProductCreate) -> Product:
        product_id = data.id or str(uuid4())

        if data.warehouse_id is None or data.warehouse_id == "":
            raise HTTPException(status_code=400, detail="warehouse_id is required")
        if data.optimal_stock < data.min_stock:
            raise HTTPException(status_code=400, detail="optimal_stock must be >= min_stock")

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
                warehouse_id=data.warehouse_id,   
                check_warehouse_exists=True,    
            )
            return product

        except IntegrityError as e:
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or getattr(e, "orig", e))

            if code == "23505": 
                raise HTTPException(status_code=409, detail="Product with this id already exists")
            if code == "23502":  
                raise HTTPException(status_code=400, detail="Missing required field (NOT NULL violation)")
            if code == "23503":  
                raise HTTPException(status_code=422, detail="Related entity not found (FK violation)")
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")
