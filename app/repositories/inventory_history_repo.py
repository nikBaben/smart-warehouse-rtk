from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, Date, or_
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from io import BytesIO
import pandas as pd
import xlsxwriter

from app.models.inventory_history import InventoryHistory


class InventoryHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session


    async def get(self, id: str) -> Optional[InventoryHistory]:
        return await self.session.scalar(
            select(InventoryHistory).where(InventoryHistory.id == id)
        )
    
    async def get_all_by_warehouse_id(self, warehosue_id: str):
        result = await self.session.execute(
            select(InventoryHistory).where(InventoryHistory.warehouse_id == warehosue_id)
        )
        return list(result.scalars().all())
    

    async def get_filtered_inventory_history(
        self, 
        warehouse_id: str,
        filters: Dict[str, Any], 
        sort_by: str, 
        sort_order: str,
        page: int,
        page_size: int
    ) -> List[InventoryHistory]:
        query = select(InventoryHistory).filter(
            InventoryHistory.warehouse_id == warehouse_id
        )
        
        if zone_filter := filters.get('zone_filter'):
            query = query.filter(InventoryHistory.current_zone.in_(zone_filter))
        
        # Фильтр по категории
        if category_filter := filters.get('category_filter'):
            query = query.filter(InventoryHistory.category.in_(category_filter))
        
        # Фильтр по статусу
        if status_filter := filters.get('status_filter'):
            query = query.filter(InventoryHistory.status.in_(status_filter))

        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        if date_from:
            query = query.filter(cast(InventoryHistory.created_at, Date) >= date_from)
        if date_to:
            query = query.filter(cast(InventoryHistory.created_at, Date) <= date_to)

                # Фильтр по поисковой строке (name и article)
        if search_string := filters.get('search_string'):
            search_pattern = f"%{search_string}%"
            query = query.filter(
                or_(
                    InventoryHistory.name.ilike(search_pattern),
                    InventoryHistory.article.ilike(search_pattern)
                )
            )

                # Обработка периодов (кнопки)
        period_filters = []
        period_buttons = filters.get('period_buttons', [])
        
        if 'today' in period_buttons:
            today = datetime.now().date()
            period_filters.append(cast(InventoryHistory.created_at, Date) == today)
        
        if 'yesterday' in period_buttons:
            yesterday = datetime.now().date() - timedelta(days=1)
            period_filters.append(cast(InventoryHistory.created_at, Date) == yesterday)
        
        if 'week' in period_buttons:
            week_ago = datetime.now().date() - timedelta(days=7)
            period_filters.append(cast(InventoryHistory.created_at, Date) >= week_ago)
        
        if 'month' in period_buttons:
            month_ago = datetime.now().date() - timedelta(days=30)
            period_filters.append(cast(InventoryHistory.created_at, Date) >= month_ago)

        # Применяем фильтры периода (OR логика между разными периодами)
        if period_filters:
            query = query.filter(or_(*period_filters))

        if sort_by:
            sort_column = getattr(InventoryHistory, sort_by, None)
            if sort_column is not None:
                if sort_order.lower() == "desc":
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
    
        # Пагинация
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def inventory_history_export_to_xl(
        self,
        warehouse_id: str,
        record_ids: List[str]  
        ) -> BytesIO:

        query = select(InventoryHistory).filter(
        InventoryHistory.warehouse_id == warehouse_id,
        InventoryHistory.id.in_(record_ids)
        )
    
        result = await self.session.execute(query)
        data = list(result.scalars().all())

        # Преобразуем данные в список словарей
        data_list = []
        for item in data:
            data_list.append({
                'Дата и время проверки': item.created_at,
                'ID робота': item.robot_id,
                'Зона': item.current_zone,
                'Артикул': item.article,
                'Название': item.name,
                'Категория': item.category,
                'Статус': item.status,
                'Количество': item.stock,
                'Склад': item.warehouse_id
            })

        # Создаем DataFrame и Excel файл
        df = pd.DataFrame(data_list)
        df['Дата и время проверки'] = df['Дата и время проверки'].dt.tz_localize(None)
        output = BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='История инвентаря', index=False)
            
            # Форматирование
            workbook = writer.book
            worksheet = writer.sheets['История инвентаря']
            
            header_format = workbook.add_format({
                'bold': True,
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Авто-ширина колонок
            for i, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
                worksheet.set_column(i, i, min(max_len, 50))

        output.seek(0)
        return output