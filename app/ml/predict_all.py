import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models import Product  # импорт своей модели
from app.ml.predictor import Predictor
from app.ml.data_access import fetch_all_product_ids
from app.db import async_session_maker


async def predict_all_for_warehouse(warehouse_id: str, horizon_days: int = 60):
    async with async_session_maker() as session:
        # 1️⃣ Получаем список всех product_id
        product_ids = await fetch_all_product_ids(session, warehouse_id)
        print(f"Всего товаров для прогноза: {len(product_ids)}")

        results = []
        for pid in product_ids:
            model_path = f"/app/models_store/{pid}.pkl"
            predictor = Predictor(model_path=model_path)
            try:
                depletion = await predictor.predict_depletion_date(
                    product_id=pid,
                    warehouse_id=warehouse_id,
                    horizon_days=horizon_days,
                    as_of=datetime.utcnow()
                )
                if depletion:
                    results.append((pid, warehouse_id, depletion))
                    print(f"✅ {pid}: истощение {depletion}")
                else:
                    print(f"⚠️ {pid}: не удалось рассчитать")
            except Exception as e:
                print(f"❌ Ошибка для {pid}: {e}")

        # 2️⃣ Сохраняем прогнозы в predict_at
        await save_predictions(session, results)


async def save_predictions(session: AsyncSession, results):
    if not results:
        print("Нет данных для сохранения")
        return

    await session.execute("DELETE FROM predict_at WHERE predicted_at < NOW() - INTERVAL '1 day'")
    for pid, wid, dt in results:
        await session.execute(
            """
            INSERT INTO predict_at (product_id, warehouse_id, depletion_at, predicted_at)
            VALUES (:pid, :wid, :dt, NOW())
            """,
            {"pid": pid, "wid": wid, "dt": dt}
        )
    await session.commit()
    print(f"💾 Сохранено {len(results)} записей в predict_at")


if __name__ == "__main__":
    asyncio.run(predict_all_for_warehouse("WH_001"))
