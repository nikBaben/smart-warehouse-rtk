RTK-smart-warehouse — ML-пайплайн для предсказания исчерпания запасов
====================================================================

Эта папка содержит ML-пайплайн для предсказания даты, когда запас товара на складе достигнет нуля.

## Архитектура

Пайплайн состоит из трёх основных этапов:

### 1. **Сбор данных** (`data_access.py`)
- `fetch_outgoing_timeseries()` — исторические отгрузки со склада для обучения
- `fetch_snapshot_at()` — текущий уровень запаса на момент времени
- `fetch_planned_incoming()` — запланированные будущие поставки
- `predict_depletion_with_model()` — расчёт исчерпания: запас + поступления - предсказанные отгрузки

### 2. **Обучение модели** (`train.py`)
Обучает модель Prophet только на **исторических отгрузках** (без учёта поступлений).
Модель изучает паттерны спроса для предсказания будущих отгрузок.

### 3. **Предсказание** (`predictor.py`)
Использует обученную модель для предсказания даты исчерпания запаса:
```
запас(t) = запас(t-1) + запланированные_поступления(t) - предсказанные_отгрузки(t)
```

## Файлы

- `data_access.py` — получение данных из БД (inventory_history, delivery_items, shipment_items)
- `train.py` — скрипт для обучения модели Prophet
- `predictor.py` — класс Predictor для инференса
- `model_store.py` — сохранение/загрузка моделей через `joblib`

## Установка

```bash
pip install pandas prophet joblib sqlalchemy asyncpg
```

## Использование

### Обучение модели

```powershell
# Обучить модель для конкретного товара
python -m app.ml.train `
  --product-id <PRODUCT_ID> `
  --model-path models/product_<PRODUCT_ID>.pkl `
  --warehouse-id <WAREHOUSE_ID> `
  --freq D
```

### Предсказание даты исчерпания

```python
import asyncio
from datetime import datetime
from app.ml.predictor import Predictor

async def predict_example():
    # Загрузить обученную модель
    predictor = Predictor(model_path='models/product_123.pkl')
    
    # Предсказать дату исчерпания
    depletion_date = await predictor.predict_depletion_date(
        product_id='123',
        warehouse_id='warehouse_1',
        horizon_days=30,
        as_of=datetime.utcnow()
    )
    
    if depletion_date:
        print(f"Запас закончится: {depletion_date}")
    else:
        print("Запаса хватит на следующие 30 дней")
    
    # Получить детали прогноза
    forecast = predictor.get_predict_as_list()
    print(f"Предсказанные отгрузки на следующие 30 дней: {forecast}")

asyncio.run(predict_example())
```

### Пример интеграции с API

```python
from fastapi import APIRouter
from app.ml.predictor import Predictor

router = APIRouter()

@router.get("/predict-depletion/{product_id}")
async def predict_depletion(product_id: str, warehouse_id: str = None):
    predictor = Predictor(model_path=f'models/product_{product_id}.pkl')
    
    depletion_date = await predictor.predict_depletion_date(
        product_id=product_id,
        warehouse_id=warehouse_id,
        horizon_days=30
    )
    
    return {
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "depletion_date": depletion_date.isoformat() if depletion_date else None,
        "forecast": predictor.get_predict_as_list()
    }
```

## Поток данных

```
Обучение:
  ShipmentItems (исторические отгрузки) 
    → fetch_outgoing_timeseries() 
    → Prophet.fit()
    → Обученная модель

Предсказание:
  1. InventoryHistory → fetch_snapshot_at() → текущий_запас
  2. DeliveryItems (будущие запланированные) → fetch_planned_incoming() → запланированные_поставки
  3. Обученная модель → predict_outgoing() → предсказанный_спрос
  4. predict_depletion_with_model(текущий_запас, запланированные_поставки, предсказанный_спрос) → дата_исчерпания
```

## Примечания

- **Данные для обучения**: Только исторические отгрузки (ShipmentItems). Модель изучает паттерны спроса.
- **Предсказание**: Комбинирует текущий запас + запланированные поступления - предсказанные отгрузки.
- **Частота**: По умолчанию агрегация по дням. Настройте параметр `freq` для других интервалов.
- **Горизонт**: По умолчанию 30 дней. Увеличьте для долгосрочного планирования.

## Рекомендации для production

1. **Хранение моделей**: Храните модели в S3/облачном хранилище вместо локальных файлов
2. **Переобучение**: Настройте периодическое переобучение (еженедельно/ежемесячно) при поступлении новых данных
3. **Мониторинг**: Отслеживайте точность прогнозов (MAE, RMSE) относительно фактических отгрузок
4. **Детекция дрифта**: Мониторьте распределения признаков и переобучайте при обнаружении дрифта
5. **Множественные модели**: Обучайте отдельные модели для каждого товара или категории товаров
6. **Страховой запас**: Добавьте буфер в расчёты исчерпания (например, оповещение при достижении уровня страхового запаса, а не нуля)
