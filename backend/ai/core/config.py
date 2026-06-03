from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required — must be set in .env or environment
    groq_api_key: str

    # Optional with sensible defaults
    groq_model: str = "llama-3.1-8b-instant"
    ai_service_name: str = "finsight-ai-service"
    ai_env: str = "development"

    # Load from ai/.env (when run from backend/) or .env (when run from inside ai/)
    model_config = {
        "env_file": ("ai/.env", ".env"),
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }


settings = Settings()
