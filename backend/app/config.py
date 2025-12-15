from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SDR-IA"
    environment: str = "dev"
    evolution_base_url: str = ""
    evolution_token: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"
    embeddings_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o-mini"
    redis_url: str = "redis://localhost:6379/0"
    reengagement_minutes: tuple[int, int, int] = (30, 180, 360)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
