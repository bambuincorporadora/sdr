from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.utils.db import get_supabase_client


class AgentConfig(BaseModel):
    agent_key: str
    system_prompt: str
    model: str
    temperature: float = 0.0
    max_tokens: int | None = None
    metadata: dict[str, Any] = {}


@dataclass
class _CacheEntry:
    value: AgentConfig
    expires_at: float


class AgentConfigService:
    """
    Le configuracoes dinâmicas de agentes (prompt/modelo) do Supabase com cache em memória.
    """

    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.settings = get_settings()
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get_agent_config(self, agent_key: str, fallback: AgentConfig | None = None) -> AgentConfig:
        now = time.monotonic()
        cached = self._cache.get(agent_key)
        if cached and cached.expires_at > now:
            return cached.value

        async with self._lock:
            cached = self._cache.get(agent_key)
            if cached and cached.expires_at > time.monotonic():
                return cached.value
            data = await asyncio.to_thread(self._fetch_config, agent_key)
            if not data and fallback:
                config = fallback
            elif not data:
                raise RuntimeError(f"Agent config not found for '{agent_key}'")
            else:
                config = AgentConfig(
                    agent_key=agent_key,
                    system_prompt=data.get("system_prompt") or (fallback.system_prompt if fallback else ""),
                    model=data.get("model") or self.settings.llm_model,
                    temperature=float(data.get("temperature") or 0),
                    max_tokens=data.get("max_tokens"),
                    metadata=data.get("metadata") or {},
                )
            self._cache[agent_key] = _CacheEntry(
                value=config,
                expires_at=time.monotonic() + self.settings.config_cache_ttl_seconds,
            )
            return config

    def _fetch_config(self, agent_key: str) -> dict[str, Any] | None:
        res = (
            self.client.table("ai_agent_configs")
            .select("system_prompt,model,temperature,max_tokens,metadata")
            .eq("agent_key", agent_key)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None


# Instancia global reutilizável
agent_config_service = AgentConfigService()
