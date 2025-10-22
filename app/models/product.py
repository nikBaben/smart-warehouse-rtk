from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'TEL-4567'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_stock: Mapped[int] = mapped_column(Integer, default=10)
    optimal_stock: Mapped[int] = mapped_column(Integer, default=100)