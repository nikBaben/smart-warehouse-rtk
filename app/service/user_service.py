from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional
from app.core.security import get_password_hash

async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    """Создать пользователя с хешированием пароля"""
    # Хешируем пароль перед сохранением
    hashed_password = get_password_hash(user_in.password)
    
    # Создаем данные для пользователя, исключая пароль
    user_data = user_in.model_dump(exclude={'password'})
    user_data['password_hash'] = hashed_password
    
    user = User(**user_data)
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise ValueError("User with this email already exists")
    return user

async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def update_user(
    session: AsyncSession,
    user_id: int,
    user_update: UserUpdate
) -> Optional[User]:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None

    update_data = user_update.model_dump(exclude_unset=True)
    
    # Если обновляется пароль - хешируем его
    if 'password' in update_data:
        update_data['password_hash'] = get_password_hash(update_data.pop('password'))
    
    for field, value in update_data.items():
        setattr(user, field, value)

    await session.commit()
    await session.refresh(user)
    return user