from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str
    API_V1_PREFIX: str 
    DB_URL: str 
    JWT_SECRET: str 
    JWT_ALG: str 
    ACCESS_TOKEN_EXPIRES_MINUTES: int
    CORS_ORIGINS: list[str] 

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()
