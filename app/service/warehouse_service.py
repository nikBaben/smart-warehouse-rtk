from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.repositories.warehouse_repo import WarehouseRepository
from app.models.warehouse import Warehouse
from psycopg.errors import ForeignKeyViolation, UniqueViolation, NotNullViolation  # psycopg3

from sqlalchemy.exc import IntegrityError

def pg_error_info(e: IntegrityError):
    orig = getattr(e, "orig", None)
    code = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
    diag = getattr(orig, "diag", None)
    detail = (
        getattr(diag, "message_detail", None)
        or getattr(diag, "message_primary", None)
        or getattr(orig, "pgerror", None)
        or str(e)
    )
    meta = {
        "table": getattr(diag, "table_name", None),
        "column": getattr(diag, "column_name", None),
        "constraint": getattr(diag, "constraint_name", None),
    }
    return code, detail, meta

class WarehouseService:
    def __init__(self, repo: WarehouseRepository):
        self.repo = repo

    async def create_warehouse(self, data: WarehouseCreate) -> Warehouse:
        Warehouse_id = str(uuid4())

        try:
            robot = await self.repo.create(
                id=Warehouse_id,
                name=data.name,
                address=data.address,
                max_products = data.max_products
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
        
    async def edit_warehouse(self, warehouse_id: str, data: WarehouseUpdate) -> Warehouse:
        try:
            updated = await self.repo.edit_by_id(
                id=warehouse_id,
                name=data.name,
                address=data.address,
                max_products=data.max_products,
            )
            return updated

        # Наш репозиторий бросает ValueError для бизнес-ошибок (не найден / дубль имени)
        except ValueError as e:
            msg = str(e)
            # Поддержим русские и англ. формулировки на всякий
            if "не найден" in msg or "not found" in msg:
                raise HTTPException(status_code=404, detail=msg)
            if "уже существует" in msg or "already exists" in msg:
                raise HTTPException(status_code=409, detail=msg)
            raise HTTPException(status_code=400, detail=msg)

        # Транслируем ошибки целостности БД в HTTP-статусы, аналогично create_warehouse
        except IntegrityError as e:
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or e.orig or e)

            if code == "23505":  # unique_violation
                raise HTTPException(status_code=409, detail="Warehouse with this unique field already exists")
            if code == "23502":  # not_null_violation
                raise HTTPException(status_code=400, detail="Missing required field (NOT NULL violation)")
            if code == "23503":  # foreign_key_violation
                raise HTTPException(status_code=422, detail="Related entity not found (FK violation)")
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")
    
    async def delete_warehouse(self, warehouse_id: str) -> dict:
        try:
            await self.repo.delete(warehouse_id)
            return {"detail": f"Склад с id '{warehouse_id}' успешно удалён."}

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        except IntegrityError as e:
            code, detail, meta = pg_error_info(e)
            # Превратите в понятный HTTP-ответ
            if code == "23503":  # foreign_key_violation
                tbl = meta.get("table") or "unknown_table"
                con = meta.get("constraint") or "unknown_constraint"
                raise HTTPException(
                    status_code=422,
                    detail=f"Невозможно удалить склад: на него ссылаются записи (table={tbl}, constraint={con}). {detail}"
                )
            if code == "23502":  # not_null_violation (бывает при ON DELETE SET NULL + NOT NULL колонка)
                col = meta.get("column") or "unknown"
                raise HTTPException(status_code=400, detail=f"Колонка '{col}' не может быть NULL при удалении.")
            raise HTTPException(status_code=500, detail=f"Integrity error: {detail}")


    
    async def get_warehouses(self, *, limit: int = 100, offset: int = 0) -> list[Warehouse]:
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)
        return await self.repo.get_all(limit=limit, offset=offset)
  


    