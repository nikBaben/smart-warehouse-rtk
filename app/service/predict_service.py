from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.repositories.predict_repo import PredictRepository


class PredictService:
    def __init__(self, repo: PredictRepository):
        self.repo = repo

    async def get_top5_depletion(self, warehouse_id: str):
        """
        Возвращает 5 ближайших товаров по дате истощения для указанного склада.
        """
        try:
                rows = await self.repo.get_top5_soon_depleted(session, warehouse_id)

                if not rows:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Для склада {warehouse_id} нет прогнозов истощения."
                    )

                return rows

        except IntegrityError as e:
            code = getattr(getattr(e, "orig", None), "pgcode", None) or getattr(getattr(e, "orig", None), "sqlstate", None)
            detail = str(getattr(getattr(e, "orig", None), "diag", None) or e.orig or e)

            if code == "23503":  # FK violation
                raise HTTPException(
                    status_code=422,
                    detail=f"Связанный склад {warehouse_id} не найден (FK violation)."
                )
            raise HTTPException(status_code=500, detail=f"Database integrity error: {detail}")

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при получении данных: {str(e)}"
            )
