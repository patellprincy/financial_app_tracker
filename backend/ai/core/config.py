from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"

    # Tries ai/.env first (when run from backend/), then falls back to .env.
    # In production use real environment variables — no .env file needed.
    model_config = {"env_file": ("ai/.env", ".env"), "env_file_encoding": "utf-8", "extra": "allow"}


settings = Settings()
