from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer
from app.db.base import Base

class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    max_products: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_x:  Mapped[int] = mapped_column(Integer, default=26)
    row_y:  Mapped[int] = mapped_column(Integer, default=50)
    products_count: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship( # type: ignore
        back_populates="warehouse",
        lazy="selectin", 
        cascade="all, delete-orphan",  
        passive_deletes=True,         
    )

    robots: Mapped[list["Robot"]] = relationship( # type: ignore
        back_populates="warehouse",
        lazy="selectin", 
        cascade="all, delete-orphan", 
        passive_deletes=True,          
    )

    inventory_history: Mapped[list["InventoryHistory"]] = relationship(  # type: ignore
        back_populates="warehouse",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
