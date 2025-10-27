from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.user import UserCreate, UserResponse
from app.repositories.user_repo import UserRepository
from app.repositories.kkid_user_repo import KkidUserRepository
from app.core.security import get_password_hash

class UserService:
    def __init__(self, session: AsyncSession):
        self.user_repo = UserRepository(session)
        self.kkid_user_repo = KkidUserRepository(session)

    async def get_or_create_user_from_keycloak(self, kkid: str, email: str, user_info: dict, password: str):
        """Получаем или создаем пользователя на основе данных из Keycloak"""
        # Пытаемся найти пользователя по Keycloak ID
        user = await self.user_repo.get_by_kkid(kkid)
        
        if not user:
            # Если не нашли по Keycloak ID, ищем по email
            user = await self.user_repo.get_by_email(email)
            
            if not user:
                # Создаем нового пользователя
                roles = user_info.get('realm_access', {}).get('roles', [])
                user_role = roles[3] if len(roles) > 3 else 'user'
                
                user_create = UserCreate(
                    email=email,
                    name=user_info.get('name', user_info.get('preferred_username', email)),
                    role=user_role,
                    password_hash=get_password_hash(password)  # пароль не используется при Keycloak аутентификации
                )
                user = await self.user_repo.create(user_create)
                print(f"✅ Created new user: {user.id}, email: {user.email}")
            
            # Создаем связь между Keycloak ID и User ID
            await self.kkid_user_repo.create(kkid, user.id)
            print(f"✅ Created kkid_userid link: kkid={kkid}, user_id={user.id}")
        else:
            print(f"✅ User found via kkid: {user.id}")
        
        return user

    async def create_user_with_keycloak(self, user_create: UserCreate, kkid: str):
        """Создать пользователя в БД и связать с Keycloak ID"""
        try:
            # Создаем пользователя в БД
            user = await self.user_repo.create(user_create)
            
            # Создаем связь с Keycloak
            await self.kkid_user_repo.create(kkid, user.id)
            
            return user
        except Exception as e:
            # Если произошла ошибка, откатываем сессию
            await self.session.rollback()
            raise e

    async def get_user_by_kkid(self, kkid: str):
        """Получить пользователя по Keycloak ID"""
        return await self.user_repo.get_by_kkid(kkid)

    async def get_user_by_email(self, email: str):
        """Получить пользователя по email"""
        return await self.user_repo.get_by_email(email)

    async def create_user(self, user_create: UserCreate):
        """Создать пользователя"""
        return await self.user_repo.create(user_create)