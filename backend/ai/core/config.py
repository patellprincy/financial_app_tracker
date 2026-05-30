from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instantb"

    # Tries ai/.env first (when run from backend/), then falls back to .env.
    # In production use real environment variables — no .env file needed.
    model_config = {"env_file": ("ai/.env", ".env"), "env_file_encoding": "utf-8", "extra": "allow"}


settings = Settings()
