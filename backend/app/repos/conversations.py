import asyncio
from datetime import datetime, timedelta
from typing import Any

from app.chains.summarizer import summarize_text
from app.utils.db import get_supabase_client


class ConversationsRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.closed_statuses = {"encerrar", "handoff", "nutricao"}

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def log_message(self, conversa_id: str, autor: str, tipo: str, conteudo: str | None) -> Any:
        def _insert():
            return (
                self.client.table("mensagens")
                .insert({"conversa_id": conversa_id, "autor": autor, "tipo": tipo, "conteudo": conteudo})
                .execute()
            )

        res = await self._run(_insert)
        return res.data[0]

    async def list_inactive(self, minutes: int | None = None, hours: int | None = None) -> list[Any]:
        delta = timedelta(minutes=minutes) if minutes else timedelta(hours=hours or 0)
        threshold = datetime.utcnow() - delta

        def _fetch():
            return (
                self.client.table("conversas")
                .select("id, lead_id, status, leads(contato)")
                .lte("ultima_interacao_em", threshold.isoformat())
                .execute()
            )

        res = await self._run(_fetch)
        data = res.data or []
        return [c for c in data if c.get("status") not in self.closed_statuses]

    async def mark_reengaged(self, conversa_id: str, minutes: int) -> None:
        agendado_para = datetime.utcnow().isoformat()

        def _insert():
            return (
                self.client.table("reengajamentos")
                .insert(
                    {
                        "conversa_id": conversa_id,
                        "agendado_para": agendado_para,
                        "disparo_minutos": minutes,
                        "executado_em": datetime.utcnow().isoformat(),
                        "status": "enviado",
                    }
                )
                .execute()
            )

        await self._run(_insert)

    async def get_history_text(self, conversa_id: str, limit: int = 20) -> str:
        def _fetch():
            return (
                self.client.table("mensagens")
                .select("autor,conteudo,recebido_em")
                .eq("conversa_id", conversa_id)
                .order("recebido_em", desc=True)
                .limit(limit)
                .execute()
            )

        res = await self._run(_fetch)
        if not res.data:
            return ""
        ordered = list(sorted(res.data, key=lambda x: x["recebido_em"]))
        return "\n".join(f'{m["autor"]}: {m["conteudo"] or ""}' for m in ordered)

    async def build_summary(self, conversa_id: str, status: str = "sem_resposta_24h") -> str:
        history = await self.get_history_text(conversa_id, limit=50)
        summary = await summarize_text(history)
        return f"Status: {status}\nResumo: {summary}"

    async def send_to_broker(self, resumo: str) -> None:
        # Placeholder para integração com corretor/CRM.
        return None
