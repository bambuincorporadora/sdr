from datetime import datetime
import logging
import uuid
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.chains.reengagement import build_reengagement_message
from app.prompts.templates import REENGAGEMENT_PROMPTS
from app.repos.conversations import ConversationsRepository
from app.services.evolution import EvolutionClient, EvolutionSendError
from app.utils.cache import get_redis_client

logger = logging.getLogger(__name__)
REENGAGEMENT_LOCK_KEY = "jobs:reengagement:lock"
REENGAGEMENT_LOCK_TTL = 60 * 10  # 10 minutos


def _mask_contact(number: str) -> str:
    return f"...{number[-4:]}" if number else ""


async def run_reengagement(conversas_repo=None) -> None:
    settings = get_settings()
    evo = EvolutionClient()
    repo = conversas_repo or ConversationsRepository()
    redis_client = get_redis_client()

    lock_value = uuid.uuid4().hex
    lock_acquired = False
    try:
        lock_acquired = await redis_client.set(REENGAGEMENT_LOCK_KEY, lock_value, ex=REENGAGEMENT_LOCK_TTL, nx=True)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Falha ao obter lock reengajamento error=%s", exc)
    if not lock_acquired:
        logger.info("Reengajamento ja em execucao, encerrando tentativa.")
        return

    now_brt = datetime.now(ZoneInfo("America/Sao_Paulo"))
    if not (8 <= now_brt.hour < 19):
        await _release_lock(redis_client, lock_value)
        return

    try:
        for minutes in settings.reengagement_minutes:
            if not await _renew_lock(redis_client, lock_value):
                logger.warning("Lock de reengajamento perdido (minutos=%s), abortando execucao.", minutes)
                return
            pendentes = await repo.list_inactive(minutes=minutes)
            base_prompt = REENGAGEMENT_PROMPTS.get(str(minutes), "Posso ajudar em algo mais?")
            for c in pendentes:
                last_touch = c.get("ultima_interacao_em")
                if await repo.has_reengagement_after(c["id"], minutes, last_touch):
                    continue
                history = await repo.get_history_text(c["id"], limit=20)
                msg = await build_reengagement_message(history, base_prompt)
                contato = (c.get("leads") or {}).get("contato", "")
                if not contato:
                    continue
                try:
                    await evo.send_text(contato, msg)
                except EvolutionSendError as exc:
                    logger.error(
                        "Falha ao enviar reengajamento minutos=%s conversa=%s destino=%s error=%s",
                        minutes,
                        c["id"],
                        _mask_contact(contato),
                        exc,
                    )
                    continue
                await repo.mark_reengaged(c["id"], minutes)
                if not await _renew_lock(redis_client, lock_value):
                    logger.warning("Lock de reengajamento perdido durante minutos=%s, abortando.", minutes)
                    return

        inativos_24h = await repo.list_inactive(hours=24)
        for c in inativos_24h:
            last_touch = c.get("ultima_interacao_em")
            if await repo.has_reengagement_after(c["id"], 1440, last_touch):
                continue
            resumo = await repo.build_summary(c["id"], status="sem_resposta_24h")
            await repo.send_to_broker(resumo)
            history = await repo.get_history_text(c["id"], limit=20)
            msg = await build_reengagement_message(history, REENGAGEMENT_PROMPTS["24h_handoff"])
            contato = (c.get("leads") or {}).get("contato", "")
            if not contato:
                continue
            try:
                await evo.send_text(contato, msg)
            except EvolutionSendError as exc:
                logger.error(
                    "Falha ao enviar handoff 24h conversa=%s destino=%s error=%s",
                    c["id"],
                    _mask_contact(contato),
                    exc,
                )
                continue
            await repo.mark_reengaged(c["id"], 1440)
            if not await _renew_lock(redis_client, lock_value):
                logger.warning("Lock de reengajamento perdido (24h), abortando execucao.")
                return
    finally:
        await _release_lock(redis_client, lock_value)


async def _release_lock(redis_client, lock_value: str) -> None:
    try:
        current_value = await redis_client.get(REENGAGEMENT_LOCK_KEY)
        if current_value == lock_value:
            await redis_client.delete(REENGAGEMENT_LOCK_KEY)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Falha ao liberar lock reengajamento error=%s", exc)


async def _renew_lock(redis_client, lock_value: str) -> bool:
    try:
        current_value = await redis_client.get(REENGAGEMENT_LOCK_KEY)
        if current_value != lock_value:
            logger.warning("Outro processo assumiu lock de reengajamento.")
            return False
        await redis_client.expire(REENGAGEMENT_LOCK_KEY, REENGAGEMENT_LOCK_TTL)
        return True
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Falha ao renovar lock reengajamento error=%s", exc)
        return True
