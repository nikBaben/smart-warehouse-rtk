from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.schemas.warehouse import WarehouseCreate
from app.repositories.warehouse_repo import WarehouseRepository
from app.models.warehouse import Warehouse

class WarwehouseService:
    def __init__(self, repo: WarehouseRepository):
        self.repo = repo

    async def create_warehouse(self, data: WarehouseCreate) -> Warehouse:
        Warehouse_id = data.id or str(uuid4())

        try:
            robot = await self.repo.create(
                id=Warehouse_id,
                name=data.name,
                address=data.address,
                row_x=data.row_x,
                row_y=data.row_y
            )
            return robot

        except IntegrityError as e:
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or e.orig or e)

            if code == "23505":  
                raise HTTPException(status_code=409, detail="Robot with this id already exists")
            if code == "23502": 
                raise HTTPException(status_code=400, detail="Missing required field (NOT NULL violation)")
            if code == "23503":  
                raise HTTPException(status_code=422, detail="Related entity not found (FK violation)")
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")
    
    async def get_warehouse(self, warehouse_id: str):
        warehouse = await self.repo.get_by_id(warehouse_id)
        if not warehouse:
            raise ValueError(f"Склад с id '{warehouse_id}' не найден.")
        return warehouse
    
    async def get_warehouses(self, *, limit: int = 100, offset: int = 0) -> list[Warehouse]:
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)
        return await self.repo.get_all(limit=limit, offset=offset)
  


    