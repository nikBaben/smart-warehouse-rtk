from typing import List, Dict
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text


class PredictRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # 🔹 Получить топ-5 ближайших товаров к истощению
    async def get_top5_soon_depleted(self, warehouse_id: str) -> List[Dict]:
        """
        Возвращает 5 товаров с ближайшей датой истощения на складе.
        """
        try:
            query = text("""
                SELECT product_id, warehouse_id, depletion_at
                FROM predict_at
                WHERE warehouse_id = :wid
                  AND depletion_at IS NOT NULL
                ORDER BY depletion_at ASC
                LIMIT 5
            """)
            result = await self.session.execute(query, {"wid": warehouse_id})
            rows = [dict(r) for r in result.mappings().all()]
            return rows

        except IntegrityError as e:
            await self.session.rollback()
            code = getattr(getattr(e, "orig", None), "pgcode", None)
            if code == "23503":
                raise HTTPException(
                    status_code=422,
                    detail=f"Ошибка связей (FK violation) при запросе склада {warehouse_id}"
                )
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка целостности данных: {str(e)}"
            )

        except SQLAlchemyError as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка базы данных при получении прогнозов: {str(e)}"
            )

        except Exception as e:
            await self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Неожиданная ошибка при работе с прогнозами: {str(e)}"
            )
