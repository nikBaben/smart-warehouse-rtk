from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from datetime import datetime
from app.service.reports_service import ReportsService
from app.schemas.reports import MonthlyReportRequest
from app.api.deps import get_reports_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/monthly-excel")
async def generate_monthly_excel_report(
    request: MonthlyReportRequest,
    reports_service: ReportsService = Depends(get_reports_service)
):
    """
    Генерация Excel отчета по месяцам
    
    - Каждый лист - отдельный месяц
    - Столбцы - дни месяца
    - Строки - поставщики/заказчики
    - ОТ (оранжевый) - отгрузки
    - ДТ (желтый) - поставки
    """
    try:
        excel_data = await reports_service.generate_monthly_report(
            year=request.year,
            months=request.months
        )
        
        current_year = datetime.now().year
        filename = f"operations_report_{request.year}.xlsx"
        
        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации отчета: {str(e)}")


@router.get("/monthly-excel/{year}")
async def generate_monthly_excel_report_simple(
    year: int,
    reports_service: ReportsService = Depends(get_reports_service)
):
    """Упрощенная версия - только год"""
    try:
        excel_data = await reports_service.generate_monthly_report(year=year)
        
        filename = f"operations_report_{year}.xlsx"
        
        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации отчета: {str(e)}")