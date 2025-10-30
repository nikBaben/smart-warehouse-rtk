from __future__ import annotations
from datetime import datetime
from typing import List, Tuple
from coords_service import shelf_num_to_str, shelf_str_to_num
from config import FIELD_X, FIELD_Y
from app.models.product import Product
from sqlalchemy import select, func
from sqlalchemy.orm import load_only

async def eligible_cells(session, warehouse_id: str, cutoff: datetime) -> List[Tuple[int, int]]:
    rows = await session.execute(
        select(Product.current_row, func.upper(func.trim(Product.current_shelf)))
        .where(
            Product.warehouse_id == warehouse_id,
            func.upper(func.trim(Product.current_shelf)) != "0",
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
        .distinct()
    )
    cells: List[Tuple[int, int]] = []
    for y_int, shelf_str in rows.all():
        x = shelf_str_to_num(shelf_str)
        y = int(y_int or 0)
        if 1 <= x <= FIELD_X and 0 <= y <= FIELD_Y - 1:
            cells.append((x, y))
    return cells

async def eligible_products_in_cell(session, warehouse_id: str, x: int, y: int, cutoff: datetime):
    from app.models.product import Product
    res = await session.execute(
        select(Product)
        .options(
            load_only(
                Product.id, Product.name, Product.category, Product.article,
                Product.stock, Product.min_stock, Product.optimal_stock,
                Product.current_zone, Product.current_row, Product.current_shelf,
            )
        )
        .where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == y,
            func.upper(func.trim(Product.current_shelf)) == shelf_num_to_str(x),
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
    )
    return list(res.scalars().all())

async def cell_still_eligible(session, warehouse_id: str, cell: Tuple[int, int], cutoff: datetime) -> bool:
    from app.models.product import Product
    x, y = cell
    shelf = shelf_num_to_str(x)
    row = await session.execute(
        select(Product.id).where(
            Product.warehouse_id == warehouse_id,
            Product.current_row == y,
            func.upper(func.trim(Product.current_shelf)) == shelf,
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        ).limit(1)
    )
    return row.first() is not None
