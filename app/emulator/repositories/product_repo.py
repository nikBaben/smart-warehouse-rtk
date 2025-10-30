from sqlalchemy import select, func
from sqlalchemy.orm import load_only
from app.models.product import Product

async def products_for_cell(session, warehouse_id: str, shelf: str, row: int, cutoff):
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
            Product.current_row == row,
            func.upper(func.trim(Product.current_shelf)) == shelf,
            (Product.last_scanned_at.is_(None)) | (Product.last_scanned_at < cutoff),
        )
    )
    return list(res.scalars().all())
