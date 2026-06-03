from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    APP_ENV: str = "development"
    AI_BACKEND_URL: str = "http://localhost:8001"
    ML_SERVICE_URL: str = "http://localhost:8002"
    # Statement cleanup via AI microservice
    AI_CLEANUP_ENABLED: bool = False
    AI_CLEANUP_TIMEOUT_SECONDS: int = 15

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "allow"}


settings = Settings()
