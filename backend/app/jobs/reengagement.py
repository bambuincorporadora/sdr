from datetime import datetime, timedelta

from app.config import get_settings
from app.chains.reengagement import build_reengagement_message
from app.prompts.templates import REENGAGEMENT_PROMPTS
from app.repos.conversations import ConversationsRepository
from app.services.evolution import EvolutionClient


async def run_reengagement(conversas_repo=None, now: datetime | None = None) -> None:
    settings = get_settings()
    now = now or datetime.utcnow()
    evo = EvolutionClient()
    repo = conversas_repo or ConversationsRepository()

    for minutes in settings.reengagement_minutes:
        pendentes = await repo.list_inactive(minutes=minutes)
        base_prompt = REENGAGEMENT_PROMPTS.get(str(minutes), "Posso ajudar em algo mais?")
        for c in pendentes:
            history = await repo.get_history_text(c["id"], limit=20)
            msg = await build_reengagement_message(history, base_prompt)
            contato = (c.get("leads") or {}).get("contato", "")
            await evo.send_text(contato, msg)
            await repo.mark_reengaged(c["id"], minutes)

    inativos_24h = await repo.list_inactive(hours=24)
    for c in inativos_24h:
        resumo = await repo.build_summary(c["id"], status="sem_resposta_24h")
        await repo.send_to_broker(resumo)
        history = await repo.get_history_text(c["id"], limit=20)
        msg = await build_reengagement_message(history, REENGAGEMENT_PROMPTS["24h_handoff"])
        contato = (c.get("leads") or {}).get("contato", "")
        await evo.send_text(contato, msg)
