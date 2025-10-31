from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import load_only

from app.models.product import Product
from app.emulator.service.coords_service import shelf_num_to_str, shelf_str_to_num
from app.emulator.config import FIELD_X, FIELD_Y

async def eligible_cells(session, warehouse_id: str, cutoff: datetime) -> List[Tuple[int, int]]:
    """
    Старый API: список клеток (X,Y), где есть товары, вышедшие из cooldown.
    Оставлен для совместимости.
    """
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

async def eligible_cells_with_staleness(
    session,
    warehouse_id: str,
    cutoff: datetime,
    top_k: Optional[int] = 200
) -> List[Tuple[int, int, float]]:
    """
    Возвращает (X, Y, staleness_seconds) по клеткам, где есть eligible-товары.
    staleness исчисляется как now - MIN(coalesce(last_scanned_at, epoch)) по клетке.
    Возвращает TOP-K самых "протухших" клеток (K по умолчанию 200).
    """
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    q = (
        select(
            Product.current_row.label("row"),
            func.upper(func.trim(Product.current_shelf)).label("shelf"),
            func.min(func.coalesce(Product.last_scanned_at, epoch)).label("oldest"),
        )
        .where(
            Product.warehouse_id == warehouse_id,
            func.upper(func.trim(Product.current_shelf)) != "0",
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
        .group_by("row", "shelf")
        .order_by(func.min(func.coalesce(Product.last_scanned_at, epoch)).asc())
    )
    if top_k:
        q = q.limit(top_k)

    rows = await session.execute(q)
    now = datetime.now(timezone.utc)
    out: List[Tuple[int, int, float]] = []
    for y_int, shelf_str, oldest_dt in rows.all():
        x = shelf_str_to_num(shelf_str)
        y = int(y_int or 0)
        if 1 <= x <= FIELD_X and 0 <= y <= FIELD_Y - 1:
            oldest_dt = oldest_dt or epoch
            out.append((x, y, (now - oldest_dt).total_seconds()))
    return out

async def eligible_products_in_cell(session, warehouse_id: str, x: int, y: int, cutoff: datetime):
    """
    Список eligible-товаров в клетке.
    """
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
    """
    Проверка, что в клетке всё ещё есть eligible-товары.
    """
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
