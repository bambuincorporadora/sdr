from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.utils.db import get_supabase_client


class CompanyProfile(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    contatos: dict[str, Any] | None = None
    policy_text: str | None = None
    allowed_topics: list[str] | None = None
    handoff_webhook_url: str | None = None
    handoff_webhook_secret: str | None = None


class CompanyConfigService:
    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.settings = get_settings()
        self._cache: CompanyProfile | None = None
        self._expires_at: float = 0
        self._lock = asyncio.Lock()

    async def get_profile(self) -> CompanyProfile:
        if self._cache and self._expires_at > time.monotonic():
            return self._cache
        async with self._lock:
            if self._cache and self._expires_at > time.monotonic():
                return self._cache
            data = await asyncio.to_thread(self._fetch_profile)
            profile = CompanyProfile(**data) if data else CompanyProfile()
            self._cache = profile
            self._expires_at = time.monotonic() + self.settings.company_config_ttl_seconds
            return profile

    def _fetch_profile(self) -> dict[str, Any] | None:
        res = (
            self.client.table("empresa_config")
            .select("*")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        allowed = row.get("allowed_topics")
        if isinstance(allowed, str):
            allowed_topics = [topic.strip() for topic in allowed.split(",") if topic.strip()]
        else:
            allowed_topics = allowed
        row["allowed_topics"] = allowed_topics
        return row


company_config_service = CompanyConfigService()
