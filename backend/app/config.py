from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    reengagement_minutes_raw: str = Field(
        default="30,180,360", alias="REENGAGEMENT_MINUTES"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def reengagement_minutes(self) -> list[int]:
        raw = self.reengagement_minutes_raw
        if isinstance(raw, str):
            cleaned = raw.replace("[", "").replace("]", "")
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            try:
                return [int(p) for p in parts]
            except ValueError:
                return [30, 180, 360]
        return [30, 180, 360]


@lru_cache
def get_settings() -> Settings:
    return Settings()
