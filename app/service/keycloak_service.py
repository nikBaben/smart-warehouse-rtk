import logging
import httpx
from typing import Dict, Any
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)

class KeycloakService:
    def __init__(self):
        logger.info(
            f"Initializing Keycloak: URL={settings.KEYCLOAK_URL}, "
            f"Realm={settings.KEYCLOAK_REALM}, "
            f"Client={settings.KEYCLOAK_CLIENT_ID}"
        )

        self.keycloak_openid = KeycloakOpenID(
            server_url=settings.KEYCLOAK_URL,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            realm_name=settings.KEYCLOAK_REALM,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
            verify=True
        )

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Аутентификация пользователя"""
        try:
            logger.info(f"Attempting login for: {email}")

            token = self.keycloak_openid.token(
                username=email,
                password=password,
                grant_type="password"
            )

            logger.info("Login successful")

            return {
                "user_id": token.get('sub'),
                "email": email,
                "access_token": token['access_token'],
                "refresh_token": token['refresh_token'],
                "expires_in": token['expires_in'],
                "refresh_expires_in": token['refresh_expires_in'],
                "token_type": token['token_type'],
            }

        except KeycloakError as e:
            logger.error(f"Login error: {e}")
            if "Invalid user credentials" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            elif "Account is not fully set up" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account is not fully set up"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed"
                )
        except Exception as e:
            logger.error(f"Unexpected login error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during authentication"
            )

    async def logout(self, refresh_token: str) -> bool:
        """Выход из системы"""
        try:
            self.keycloak_openid.logout(refresh_token)
            logger.info("Logout successful")
            return True
        except KeycloakError as e:
            logger.error(f"Logout error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected logout error: {e}")
            return False

    async def get_user_info(self, token: str) -> Dict[str, Any]:
        """Получение информации о пользователе"""
        try:
            user_info = self.keycloak_openid.userinfo(token)
            logger.debug(f"User info retrieved: {user_info.get('sub')}")
            return user_info
        except KeycloakError as e:
            logger.warning(f"Direct userinfo failed: {e}, attempting token exchange")
            exchanged = await self._exchange_token(token)
            exchanged_token = exchanged['access_token']
            user_info = self.keycloak_openid.userinfo(exchanged_token)
            return user_info
        except Exception as e:
            logger.error(f"Unexpected error in get_user_info: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user information"
            )

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Обновление токена"""
        try:
            token_data = self.keycloak_openid.refresh_token(refresh_token)
            logger.info("Token refreshed successfully")
            return token_data
        except KeycloakError as e:
            logger.error(f"Refresh token error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        except Exception as e:
            logger.error(f"Unexpected refresh token error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to refresh token"
            )

    async def validate_token(self, token: str) -> bool:
        """Проверка валидности токена"""
        try:
            result = self.keycloak_openid.introspect(token)
            is_active = result.get('active', False)

            if is_active:
                logger.debug("Token is active")
                return True
            else:
                logger.warning("Token is not active, attempting token exchange")
                exchanged = await self._exchange_token(token)
                exchanged_token = exchanged['access_token']
                result = self.keycloak_openid.introspect(exchanged_token)
                return result.get('active', False)

        except KeycloakError as e:
            logger.error(f"Token validation error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected token validation error: {e}")
            return False

    async def _exchange_token(self, subject_token: str) -> Dict[str, Any]:
        """Обмен токена"""
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
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Token exchange request failed: {str(e)}"
                )