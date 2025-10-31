from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MonthlyReportRequest(BaseModel):
    year: int
    months: Optional[list[int]] = None  # Если None - все месяцы года