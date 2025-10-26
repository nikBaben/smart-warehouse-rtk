from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserCreate

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_kkid(self, kkid: str) -> Optional[User]:
        from app.models.keycloak_user import KeycloakUser
        result = await self.session.execute(
            select(User)
            .join(KeycloakUser, User.id == KeycloakUser.user_id)
            .where(KeycloakUser.kkid == kkid)
        )
        return result.scalar_one_or_none()

    async def create(self, user_create: UserCreate) -> User:
        user = User(
            email=user_create.email,
            name=user_create.name,
            role=user_create.role
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user