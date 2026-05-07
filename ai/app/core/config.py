from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
