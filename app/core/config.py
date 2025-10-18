# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "warehouse")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "smart-warehouse")
    KEYCLOAK_CLIENT_SECRET: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "GQgCDvuuKhBtuWU01bjZX2po0pSjUs39")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")  # Важно: 0.0.0.0 для Docker
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()