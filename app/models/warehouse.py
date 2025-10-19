from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer
from app.db.base import Base

class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adress: Mapped[str] = mapped_column(String(255), nullable=False)
    row_x:  Mapped[int] = mapped_column(Integer, default=0)
    row_y:  Mapped[int] = mapped_column(Integer, default=0)
    products_count: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship(
        back_populates="warehouse",
        lazy="selectin", 
        cascade="all, delete-orphan",  
        passive_deletes=True,         
    )

    robots: Mapped[list["Robot"]] = relationship(
        back_populates="warehouse",
        lazy="selectin", 
        cascade="all, delete-orphan", 
        passive_deletes=True,          
    )

