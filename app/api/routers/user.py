from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.service.user_service import create_user, get_user_by_id, update_user
from app.db.session import get_session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.service.user_service import get_user_by_id
from app.db.session import get_session

router = APIRouter(prefix="/user", tags=["users"])
security = HTTPBearer()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_handler(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    try:
        user = await create_user(session, user_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    return user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_handler(
    user_id: int,
    session: AsyncSession = Depends(get_session)
):
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user_handler(
    user_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_session)
):
    user = await update_user(session, user_id, user_update)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user
