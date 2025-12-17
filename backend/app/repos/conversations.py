import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from postgrest import APIError

from app.chains.summarizer import summarize_text
from app.utils.db import get_supabase_client


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ConversationsRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.closed_statuses = {"encerrar", "handoff", "nutricao"}

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def log_message(
        self,
        conversa_id: str,
        autor: str,
        tipo: str,
        conteudo: str | None,
        evolution_mensagem_id: str | None = None,
    ) -> Any:
        def _insert():
            payload = {"conversa_id": conversa_id, "autor": autor, "tipo": tipo, "conteudo": conteudo}
            if evolution_mensagem_id:
                payload["evolution_mensagem_id"] = evolution_mensagem_id
            return (
                self.client.table("mensagens")
                .insert(payload)
                .execute()
            )

        res = await self._run(_insert)
        return res.data[0]

    async def register_incoming_message(self, mensagem_id: str) -> bool:
        if not mensagem_id:
            return True

        def _insert():
            return (
                self.client.table("evolution_webhook_events")
                .insert({"mensagem_id": mensagem_id})
                .execute()
            )

        try:
            await self._run(_insert)
            return True
        except APIError as exc:
            if exc.code == "23505":  # duplicate key
                return False
            raise

    async def release_incoming_message(self, mensagem_id: str) -> None:
        if not mensagem_id:
            return

        def _delete():
            return (
                self.client.table("evolution_webhook_events")
                .delete()
                .eq("mensagem_id", mensagem_id)
                .execute()
            )

        await self._run(_delete)

    async def list_inactive(self, minutes: int | None = None, hours: int | None = None) -> list[Any]:
        delta = timedelta(minutes=minutes) if minutes else timedelta(hours=hours or 0)
        threshold = _now_utc() - delta

        def _fetch():
            return (
                self.client.table("conversas")
                .select("id, lead_id, status, ultima_interacao_em, leads(nome,contato)")
                .lte("ultima_interacao_em", threshold.isoformat())
                .execute()
            )

        res = await self._run(_fetch)
        data = res.data or []
        return [
            c
            for c in data
            if c.get("status") not in self.closed_statuses and c.get("ultima_interacao_em")
        ]

    async def mark_reengaged(self, conversa_id: str, minutes: int) -> None:
        now_iso = _now_utc().isoformat()

        def _insert():
            return (
                self.client.table("reengajamentos")
                .insert(
                    {
                        "conversa_id": conversa_id,
                        "agendado_para": now_iso,
                        "disparo_minutos": minutes,
                        "executado_em": _now_utc().isoformat(),
                        "status": "enviado",
                    }
                )
                .execute()
            )

        await self._run(_insert)

    async def has_reengagement_after(self, conversa_id: str, minutes: int, since_iso: str | None) -> bool:
        def _fetch():
            return (
                self.client.table("reengajamentos")
                .select("executado_em")
                .eq("conversa_id", conversa_id)
                .eq("disparo_minutos", minutes)
                .order("executado_em", desc=True)
                .limit(1)
                .execute()
            )

        res = await self._run(_fetch)
        rows = res.data or []
        if not rows:
            return False
        executed = _parse_iso_datetime(rows[0].get("executado_em"))
        if not executed:
            return False
        if not since_iso:
            return True
        since_dt = _parse_iso_datetime(since_iso)
        if not since_dt:
            return True
        return executed >= since_dt

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
