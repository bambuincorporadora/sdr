from __future__ import annotations

import asyncio
import hmac
import json
import logging
from hashlib import sha256
from typing import Any

import httpx

from app.chains.handoff_summary import generate_handoff_summary
from app.config import get_settings
from app.services.company import company_config_service
from app.services.events import conversation_events_service
from app.utils.db import get_supabase_client

logger = logging.getLogger(__name__)


class HandoffService:
    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.settings = get_settings()

    async def dispatch_handoff(
        self,
        *,
        conversa_id: str,
        history_text: str,
        lead: dict[str, Any],
        status: str,
    ) -> str | None:
        company = await company_config_service.get_profile()
        summary = await generate_handoff_summary(history_text, company.model_dump())
        payload = {
            "lead_nome": lead.get("nome"),
            "lead_contato": lead.get("contato"),
            "conversa_id": conversa_id,
            "resumo": summary,
            "status": status,
        }
        await conversation_events_service.record(
            conversa_id,
            "handoff_summary",
            payload={"status": status},
            agent_key="handoff_summary",
        )
        await self._save_handoff(conversa_id, summary, lead.get("destino"))
        await self._send_webhook(payload, company.handoff_webhook_url, company.handoff_webhook_secret)
        return summary

    async def _save_handoff(self, conversa_id: str, resumo: str, destino: str | None) -> None:
        def _insert():
            return (
                self.client.table("handoffs")
                .insert({"conversa_id": conversa_id, "resumo": resumo, "enviado_para": destino})
                .execute()
            )

        await asyncio.to_thread(_insert)

    async def _send_webhook(self, payload: dict[str, Any], url: str | None, secret: str | None) -> None:
        if not url:
            return
        headers = {"Content-Type": "application/json"}
        body = json.dumps(payload).encode("utf-8")
        if secret:
            signature = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
            headers["X-Handoff-Signature"] = signature
        timeout = httpx.Timeout(self.settings.handoff_webhook_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, content=body, headers=headers)
                resp.raise_for_status()
        except Exception as exc:  # pragma: no cover - rede externa
            logger.error("Webhook handoff falhou url=%s error=%s", url, exc)
            await conversation_events_service.record(
                payload.get("conversa_id", ""),
                "handoff_webhook_error",
                payload={"error": str(exc)},
            )


handoff_service = HandoffService()
