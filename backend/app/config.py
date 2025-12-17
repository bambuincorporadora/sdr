from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SDR-IA"
    environment: str = "dev"
    evolution_base_url: str = ""
    evolution_token: str = ""
    evolution_instance: str = ""
    evolution_webhook_secret: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"
    embeddings_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    redis_url: str = "redis://localhost:6379/0"
    webhook_rate_limit_per_minute: int = 120
    trusted_media_hosts_raw: str = Field(default="", alias="TRUSTED_MEDIA_HOSTS")
    text_buffer_delay_seconds: int = 4
    attachments_bucket: str = "attachments"
    document_max_bytes: int = 15 * 1024 * 1024
    config_cache_ttl_seconds: int = 60
    company_config_ttl_seconds: int = 300
    handoff_webhook_timeout_seconds: int = 5

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

    @property
    def trusted_media_hosts(self) -> list[str]:
        if not self.trusted_media_hosts_raw:
            return []
        hosts = [h.strip().lower() for h in self.trusted_media_hosts_raw.split(",") if h.strip()]
        return hosts


@lru_cache
def get_settings() -> Settings:
    return Settings()
