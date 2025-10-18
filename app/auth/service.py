# app/auth/service.py
import logging
import httpx
import uuid
from typing import Dict, Any, Optional
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)


class KeycloakAuthService:
	def __init__(self):
		logger.info(
			f"Initializing Keycloak: URL={settings.KEYCLOAK_URL}, Realm={settings.KEYCLOAK_REALM}, Client={settings.KEYCLOAK_CLIENT_ID}")

		self.keycloak_openid = KeycloakOpenID(
			server_url=settings.KEYCLOAK_URL,
			client_id=settings.KEYCLOAK_CLIENT_ID,
			realm_name=settings.KEYCLOAK_REALM,
			client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
			verify=True
		)

	async def login(self, email: str, password: str) -> Dict[str, Any]:
		"""Аутентификация пользователя - аналог Go Login"""
		try:
			logger.info(f"Attempting login for: {email}")

			token = self.keycloak_openid.token(
				username=email,
				password=password,
				grant_type="password"
			)

			logger.info("Login successful")

			# Получаем информацию о пользователе - как в Go
			user_info = await self.get_user_info(token['access_token'])

			return {
				"user_id": user_info.get('sub'),
				"email": user_info.get('email'),
				"access_token": token['access_token'],
				"refresh_token": token['refresh_token'],
				"expires_in": token['expires_in'],
				"refresh_expires_in": token['refresh_expires_in'],
				"token_type": token['token_type'],
			}

		except KeycloakError as e:
			logger.error(f"Login error: {e}")
			raise HTTPException(status_code=401, detail="Invalid credentials")

	async def logout(self, refresh_token: str) -> bool:
		"""Выход из системы - аналог Go Logout"""
		try:
			self.keycloak_openid.logout(refresh_token)
			return True
		except KeycloakError as e:
			logger.error(f"Logout error: {e}")
			return False

	async def get_user_info(self, token: str) -> Dict[str, Any]:
		"""Получение информации о пользователе - аналог Go GetUserInfo"""
		try:
			# Try to fetch user info directly
			user_info = self.keycloak_openid.userinfo(token)
			return user_info
		except KeycloakError as e:
			logger.warning(f"Direct userinfo failed: {e}, attempting token exchange")

			# Attempt token exchange - как в Go
			exchanged = await self._exchange_token(token)
			exchanged_token = exchanged['access_token']

			# Try again with exchanged token
			user_info = self.keycloak_openid.userinfo(exchanged_token)
			return user_info

	async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
		"""Обновление токена - аналог Go RefreshToken"""
		try:
			return self.keycloak_openid.refresh_token(refresh_token)
		except KeycloakError as e:
			logger.error(f"Refresh token error: {e}")
			raise HTTPException(status_code=401, detail="Invalid refresh token")

	async def validate_token_internal(self, token: str) -> bool:
		"""Проверка валидности токена - аналог Go ValidateToken"""
		try:
			# Try backend client introspection - как в Go RetrospectToken
			result = self.keycloak_openid.introspect(token)
			is_active = result.get('active', False)

			if is_active:
				logger.info("Token is active")
				return True
			else:
				logger.warning("Token is not active, attempting token exchange")

				# Attempt token exchange - как в Go
				exchanged = await self._exchange_token(token)
				exchanged_token = exchanged['access_token']

				# Validate again with backend client
				result = self.keycloak_openid.introspect(exchanged_token)
				return result.get('active', False)

		except KeycloakError as e:
			logger.error(f"Token validation error: {e}")
			return False

	async def validate_token_for_middleware(self, token: str) -> bool:
		"""Проверка токена для middleware - аналог Go ValidateTokenForMiddleware"""
		logger.info("Starting middleware token validation")

		try:
			# Try backend client introspection
			result = self.keycloak_openid.introspect(token)

			if result and result.get('active', False):
				logger.info("Token is active in middleware")
				return True
			else:
				logger.warning("Token not active in middleware, attempting exchange")

				# Attempt token exchange
				exchanged = await self._exchange_token(token)
				exchanged_token = exchanged['access_token']

				# Validate again with backend client
				result = self.keycloak_openid.introspect(exchanged_token)
				is_active = result and result.get('active', False)

				if is_active:
					logger.info("Exchanged token is active in middleware")
					return True
				else:
					logger.error("Exchanged token is also not active")
					return False

		except Exception as e:
			logger.error(f"Middleware validation failed: {e}")
			return False

	async def _exchange_token(self, subject_token: str) -> Dict[str, Any]:
		"""Обмен токена - аналог Go ExchangeToken"""
		logger.info("Attempting token exchange")

		async with httpx.AsyncClient() as client:
			data = {
				"grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
				"subject_token": subject_token,
				"subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
				"client_id": settings.KEYCLOAK_CLIENT_ID,
				"client_secret": settings.KEYCLOAK_CLIENT_SECRET,
				"scope": "openid"
			}

			url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
			logger.info(f"Exchanging token at: {url}")

			try:
				response = await client.post(url, data=data, timeout=10.0)

				if response.status_code == 200:
					token_data = response.json()
					logger.info("Token exchange successful")
					return token_data
				else:
					logger.error(f"Token exchange failed with status {response.status_code}: {response.text}")
					raise HTTPException(
						status_code=response.status_code,
						detail=f"Token exchange failed: {response.text}"
					)

			except httpx.TimeoutException:
				logger.error("Token exchange timeout")
				raise HTTPException(status_code=408, detail="Token exchange timeout")
			except Exception as e:
				logger.error(f"Token exchange request failed: {e}")
				raise HTTPException(status_code=500, detail=f"Token exchange request failed: {str(e)}")


auth_service = KeycloakAuthService()