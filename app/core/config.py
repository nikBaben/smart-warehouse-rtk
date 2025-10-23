from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str
    API_V1_PREFIX: str 
    DB_URL: str 
    KEYCLOAK_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str
    CORS_ORIGINS: list[str] 

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()

