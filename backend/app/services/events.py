from __future__ import annotations

import asyncio
from typing import Any

from app.utils.db import get_supabase_client


class ConversationEventsService:
    def __init__(self) -> None:
        self.client = get_supabase_client()

    async def record(
        self,
        conversa_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        agent_key: str | None = None,
        mensagem_id: str | None = None,
    ) -> None:
        if not conversa_id or not event_type:
            return

        def _insert():
            return (
                self.client.table("conversation_events")
                .insert(
                    {
                        "conversa_id": conversa_id,
                        "event_type": event_type,
                        "payload": payload or {},
                        "agent_key": agent_key,
                        "mensagem_id": mensagem_id,
                    }
                )
                .execute()
            )

        await asyncio.to_thread(_insert)


conversation_events_service = ConversationEventsService()
