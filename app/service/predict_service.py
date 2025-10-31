from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.repositories.predict_repo import PredictRepository


class PredictService:
    def __init__(self, repo: PredictRepository):
        self.repo = repo

    async def get_top5_depletion(self, warehouse_id: str):
        """
        Возвращает 5 ближайших товаров по дате истощения для склада.
        """
        try:
            rows = await self.repo.get_top5_soon_depleted(warehouse_id)

            if not rows:
                raise HTTPException(
                    status_code=404,
                    detail=f"Для склада {warehouse_id} нет прогнозов истощения."
                )

            return rows

        except IntegrityError as e:
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
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка базы данных при получении прогнозов: {str(e)}"
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении данных: {str(e)}"
            )
