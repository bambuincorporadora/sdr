import asyncio
from datetime import datetime, timezone
from typing import Any

from app.utils.db import get_supabase_client


class ConversationService:
    """
    Gerencia lead e conversa: se ultima conversa estiver encerrada/handoff/nutricao,
    cria nova conversa para novo contato, preservando memoria por contato/lead.
    """

    CLOSED_STATUSES = {"encerrar", "handoff", "nutricao"}

    def __init__(self) -> None:
        self.client = get_supabase_client()

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def get_or_create_lead(self, contato: str, canal: str = "whatsapp", nome: str | None = None) -> Any:
        def _get_or_create():
            existing = (
                self.client.table("leads")
                .select("id,nome")
                .eq("contato", contato)
                .limit(1)
                .execute()
            )
            if existing.data:
                lead = existing.data[0]
                # atualiza nome se estava vazio e recebemos agora
                if nome and not lead.get("nome"):
                    self.client.table("leads").update({"nome": nome}).eq("id", lead["id"]).execute()
                return lead
            created = (
                self.client.table("leads")
                .insert({"contato": contato, "canal": canal, "nome": nome})
                .execute()
            )
            return created.data[0]

        return await self._run(_get_or_create)

    async def get_conversation_by_id(self, conversa_id: str) -> Any:
        def _get():
            return (
                self.client.table("conversas")
                .select("*")
                .eq("id", conversa_id)
                .limit(1)
                .execute()
            )

        res = await self._run(_get)
        return res.data[0] if res.data else None

    async def get_latest_conversation(self, lead_id: str) -> Any:
        def _get():
            return (
                self.client.table("conversas")
                .select("*")
                .eq("lead_id", lead_id)
                .order("ultima_interacao_em", desc=True)
                .limit(1)
                .execute()
            )

        res = await self._run(_get)
        return res.data[0] if res.data else None

    async def create_conversation(self, lead_id: str, status: str = "iniciar") -> Any:
        timestamp = datetime.now(timezone.utc).isoformat()

        def _create():
            return (
                self.client.table("conversas")
                .insert({"lead_id": lead_id, "status": status, "ultima_interacao_em": timestamp})
                .execute()
            )

        res = await self._run(_create)
        return res.data[0]

    async def ensure_active_conversation(
        self, contato: str, canal: str = "whatsapp", conversa_id: str | None = None, nome: str | None = None
    ) -> Any:
        lead = await self.get_or_create_lead(contato, canal, nome)
        lead_id = lead["id"]

        if conversa_id:
            existing = await self.get_conversation_by_id(conversa_id)
            if existing and existing.get("status") not in self.CLOSED_STATUSES:
                return existing
            return await self.create_conversation(lead_id)

        latest = await self.get_latest_conversation(lead_id)
        if not latest or latest.get("status") in self.CLOSED_STATUSES:
            return await self.create_conversation(lead_id)
        return latest

    async def touch_conversation(self, conversa_id: str, status: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def _update():
            payload: dict[str, Any] = {"ultima_interacao_em": now}
            if status:
                payload["status"] = status
            return (
                self.client.table("conversas")
                .update(payload)
                .eq("id", conversa_id)
                .execute()
            )

        await self._run(_update)
