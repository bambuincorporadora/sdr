from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
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
    reengagement_minutes: List[int] = Field(default_factory=lambda: [30, 180, 360])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def compute_reengagement_minutes(self):
        raw = self.reengagement_minutes_raw
        if isinstance(raw, str):
            cleaned = raw.replace("[", "").replace("]", "")
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            try:
                self.reengagement_minutes = [int(p) for p in parts]
            except ValueError:
                self.reengagement_minutes = [30, 180, 360]
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
