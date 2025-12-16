from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.jobs.transcription import enqueue_transcription
from app.orchestrator import process_message
from app.repos.conversations import ConversationsRepository
from app.schemas.evolution import EvolutionMessage
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient
from app.utils.cache import delete_key, get_redis_client, set_if_absent


router = APIRouter()
evolution_client = EvolutionClient()
conversation_service = ConversationService()
conversations_repo = ConversationsRepository()
settings = get_settings()
logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 60 * 60


def _mask_contact(contact: str) -> str:
    if not contact:
        return ""
    return f"...{contact[-4:]}"


def _extract_text(message: dict[str, Any], data: dict[str, Any]) -> str:
    return (
        message.get("conversation")
        or message.get("text")
        or message.get("extendedTextMessage", {}).get("text")
        or data.get("text")
        or ""
    )


def _extract_media_payload(message_type: str, message: dict[str, Any]) -> tuple[str, str | None]:
    normalized_type = message_type.lower() if message_type else ""
    if "audioMessage" in message or normalized_type in {"audio", "ptt", "audiomessage"}:
        media = message.get("audioMessage") or message.get("pttMessage") or {}
        url = media.get("url") or media.get("directPath") or media.get("mediaKey") or None
        return "audio", url
    if "imageMessage" in message or normalized_type in {"image", "imagemessage"}:
        media = message.get("imageMessage") or {}
        url = media.get("url") or media.get("directPath") or None
        return "imagem", url
    if "documentMessage" in message or normalized_type in {"document", "documentmessage"}:
        media = message.get("documentMessage") or {}
        url = media.get("url") or media.get("directPath") or None
        return "documento", url
    return "texto", None


async def _enforce_rate_limit(request: Request) -> None:
    identifier = request.client.host or "unknown"
    key = f"evolution:webhook:rate:{identifier}"
    client = get_redis_client()
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 60)
        if count > settings.webhook_rate_limit_per_minute:
            logger.warning("Rate limit exceeded ip=%s count=%s", identifier, count)
            raise HTTPException(status_code=429, detail="rate_limited")
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Falha ao aplicar rate limit redis_error=%s", exc)


def parse_evolution_payload(raw: Any) -> EvolutionMessage:
    """
    Aceita payload direto (EvolutionMessage) ou payload do Evolution (body.data...).
    """
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict) and all(k in raw for k in ["mensagem_id", "contato", "tipo"]):
        return EvolutionMessage(**raw)

    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Payload invalido (nao eh JSON/objeto)")

    data = raw.get("data") or raw.get("body", {}).get("data", {}) or {}
    key = data.get("key") or {}
    message = data.get("message") or {}

    contato = key.get("remoteJid") or key.get("remoteJidAlt") or raw.get("sender") or ""
    if contato and "@s.whatsapp.net" in contato:
        contato = contato.replace("@s.whatsapp.net", "")
    mensagem_id = key.get("id") or data.get("id") or ""
    message_type = data.get("messageType") or ""
    nome = data.get("pushName") or raw.get("pushName") or None

    tipo, media_url = _extract_media_payload(message_type, message)
    conteudo = media_url if media_url else _extract_text(message, data)

    if not contato:
        raise HTTPException(status_code=422, detail="Campo contato ausente no payload Evolution")
    if not mensagem_id:
        mensagem_id = str(uuid.uuid4())

    return EvolutionMessage(
        mensagem_id=mensagem_id,
        contato=contato,
        tipo=tipo,
        conteudo=conteudo,
        canal="whatsapp",
        nome=nome,
        conversa_id=None,
    )


@router.post("/evolution")
async def evolution_webhook(request: Request):
    if settings.evolution_webhook_secret:
        provided = request.headers.get("x-evolution-secret")
        if provided != settings.evolution_webhook_secret:
            logger.warning("Invalid webhook secret ip=%s", request.client.host)
            raise HTTPException(status_code=401, detail="invalid_signature")

    await _enforce_rate_limit(request)

    try:
        payload = await request.json()
    except Exception as exc:
        body_bytes = await request.body()
        logger.error("JSON invalido error=%s body=%s", exc, body_bytes[:512])
        return {"status": "ignored", "reason": "json_invalid"}

    try:
        evo_msg = parse_evolution_payload(payload)
    except HTTPException as exc:
        logger.warning("Payload invalido reason=%s", exc.detail)
        return {"status": "ignored", "reason": exc.detail}
    except Exception as exc:
        logger.exception("Erro inesperado ao parsear payload: %s", exc)
        return {"status": "ignored", "reason": "parse_error"}

    dedupe_key: str | None = None
    if evo_msg.mensagem_id:
        dedupe_key = f"evolution:webhook:msg:{evo_msg.mensagem_id}"
        try:
            is_new = await set_if_absent(dedupe_key, "1", ttl_seconds=DEDUP_TTL_SECONDS)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Falha ao registrar dedupe redis_error=%s", exc)
            is_new = True
        if not is_new:
            logger.info(
                "Mensagem duplicada ignorada contato=%s mensagem_id=%s",
                _mask_contact(evo_msg.contato),
                evo_msg.mensagem_id,
            )
            return {"status": "ignored", "reason": "duplicate"}

    conversa = await conversation_service.ensure_active_conversation(
        contato=evo_msg.contato, canal=evo_msg.canal, conversa_id=evo_msg.conversa_id, nome=evo_msg.nome
    )
    evo_msg.conversa_id = conversa["id"]

    logged = await conversations_repo.log_message(
        conversa_id=evo_msg.conversa_id,
        autor="lead",
        tipo=evo_msg.tipo,
        conteudo=evo_msg.conteudo,
    )
    await conversation_service.touch_conversation(conversa["id"])

    try:
        if evo_msg.tipo == "audio":
            enqueue_transcription.delay(evo_msg.model_dump(), conversa["id"], logged["id"])
            logger.info(
                "Audio recebido contato=%s conversa=%s mensagem=%s",
                _mask_contact(evo_msg.contato),
                conversa["id"],
                logged["id"],
            )
            return {
                "status": "ack",
                "queued": "transcription",
                "conversa_id": conversa["id"],
                "mensagem_id": logged["id"],
            }
        response = await process_message(evo_msg)
    except Exception as exc:  # pragma: no cover - observability hook
        if dedupe_key:
            await delete_key(dedupe_key)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "Mensagem encaminhada contato=%s conversa=%s intent=%s",
        _mask_contact(evo_msg.contato),
        conversa["id"],
        response.get("intent"),
    )
    return {"status": "ok", "response": response, "conversa_id": conversa["id"], "mensagem_id": logged["id"]}
