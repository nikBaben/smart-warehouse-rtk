from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["WebSocket Docs"])

@router.get("/ws/docs", include_in_schema=False)
async def get_asyncapi_spec():
    """Возвращает спецификацию WebSocket API (AsyncAPI)."""
    return FileResponse("docs/asyncapi.yaml")
