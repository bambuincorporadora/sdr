from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from app.chains.document_guardrail import run_guardrail
from app.chains.document_qa import run_document_qa
from app.config import get_settings
from app.jobs.transcription import enqueue_transcription
from app.orchestrator import process_message
from app.repos.conversations import ConversationsRepository
from app.schemas.evolution import EvolutionMedia, EvolutionMessage
from app.services.attachments import AttachmentProcessingError, attachment_service
from app.services.company import company_config_service
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient
from app.services.events import conversation_events_service
from app.utils.cache import delete_key, get_redis_client, set_if_absent

router = APIRouter()
evolution_client = EvolutionClient()
conversation_service = ConversationService()
conversations_repo = ConversationsRepository()
settings = get_settings()
logger = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 60 * 60
TEXT_BUFFER_DATA: dict[str, dict[str, Any]] = {}
TEXT_BUFFER_TASKS: dict[str, asyncio.Task] = {}
TEXT_BUFFER_LOCK = asyncio.Lock()


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


def _sanitize_media_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    return url


def _extract_media_payload(message_type: str, message: dict[str, Any]) -> tuple[str, str | None, dict[str, Any] | None]:
    normalized_type = message_type.lower() if message_type else ""
    if "audioMessage" in message or normalized_type in {"audio", "ptt", "audiomessage"}:
        media = message.get("audioMessage") or message.get("pttMessage") or {}
        url = _sanitize_media_url(media.get("url"))
        payload = {
            "url": url,
            "media_key": media.get("mediaKey"),
            "direct_path": media.get("directPath"),
            "message_type": "audio",
            "mime_type": media.get("mimetype") or media.get("mimeType"),
        }
        return "audio", url, payload
    if "imageMessage" in message or normalized_type in {"image", "imagemessage"}:
        media = message.get("imageMessage") or {}
        url = _sanitize_media_url(media.get("url"))
        payload = {
            "url": url,
            "media_key": media.get("mediaKey"),
            "direct_path": media.get("directPath"),
            "message_type": "image",
            "mime_type": media.get("mimetype") or media.get("mimeType"),
            "caption": media.get("caption") or media.get("captionText") or message.get("caption"),
        }
        return "imagem", url, payload
    if "documentMessage" in message or normalized_type in {"document", "documentmessage"}:
        media = message.get("documentMessage") or {}
        url = _sanitize_media_url(media.get("url"))
        payload = {
            "url": url,
            "media_key": media.get("mediaKey"),
            "direct_path": media.get("directPath"),
            "message_type": "document",
            "mime_type": media.get("mimetype") or media.get("mimeType"),
            "caption": media.get("caption") or media.get("captionText") or message.get("caption"),
        }
        return "documento", url, payload
    return "texto", None, None


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

    tipo, media_url, media_payload = _extract_media_payload(message_type, message)
    conteudo = media_url if media_url else _extract_text(message, data)

    if not contato:
        raise HTTPException(status_code=422, detail="Campo contato ausente no payload Evolution")
    if not mensagem_id:
        mensagem_id = str(uuid.uuid4())

    media_model = EvolutionMedia(**media_payload) if media_payload else None

    return EvolutionMessage(
        mensagem_id=mensagem_id,
        contato=contato,
        tipo=tipo,
        conteudo=conteudo,
        canal="whatsapp",
        nome=nome,
        conversa_id=None,
        media=media_model,
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
    db_lock_acquired = False
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
        try:
            inserted = await conversations_repo.register_incoming_message(evo_msg.mensagem_id)
        except Exception:
            if dedupe_key:
                await delete_key(dedupe_key)
            raise
        if not inserted:
            logger.info(
                "Mensagem duplicada (db) ignorada contato=%s mensagem_id=%s",
                _mask_contact(evo_msg.contato),
                evo_msg.mensagem_id,
            )
            return {"status": "ignored", "reason": "duplicate"}
        db_lock_acquired = True

    conversa = await conversation_service.ensure_active_conversation(
        contato=evo_msg.contato, canal=evo_msg.canal, conversa_id=evo_msg.conversa_id, nome=evo_msg.nome
    )
    evo_msg.conversa_id = conversa["id"]

    try:
        logged = await conversations_repo.log_message(
            conversa_id=evo_msg.conversa_id,
            autor="lead",
            tipo=evo_msg.tipo,
            conteudo=evo_msg.conteudo,
            evolution_mensagem_id=evo_msg.mensagem_id,
        )
        await conversation_service.touch_conversation(conversa["id"])
        await conversation_events_service.record(
            conversa["id"],
            "incoming_message",
            payload={"tipo": evo_msg.tipo},
            mensagem_id=logged["id"],
        )
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
        if evo_msg.tipo == "documento":
            asyncio.create_task(_process_document_message(evo_msg, conversa, logged["id"]))
            return {
                "status": "ack",
                "queued": "document_processing",
                "conversa_id": conversa["id"],
                "mensagem_id": logged["id"],
            }
        if evo_msg.tipo == "texto" and await _buffer_text_message(evo_msg, conversa["id"]):
            return {
                "status": "buffered",
                "conversa_id": conversa["id"],
                "mensagem_id": logged["id"],
            }
        response = await process_message(evo_msg, override_text=evo_msg.conteudo)
    except Exception as exc:  # pragma: no cover - observability hook
        if dedupe_key:
            await delete_key(dedupe_key)
        if db_lock_acquired and evo_msg.mensagem_id:
            await conversations_repo.release_incoming_message(evo_msg.mensagem_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "Mensagem encaminhada contato=%s conversa=%s intent=%s",
        _mask_contact(evo_msg.contato),
        conversa["id"],
        response.get("intent"),
    )
    return {"status": "ok", "response": response, "conversa_id": conversa["id"], "mensagem_id": logged["id"]}


async def _buffer_text_message(evo_msg: EvolutionMessage, conversa_id: str) -> bool:
    if settings.text_buffer_delay_seconds <= 0:
        return False
    texto = (evo_msg.conteudo or "").strip()
    if not texto:
        return False

    async with TEXT_BUFFER_LOCK:
        data = TEXT_BUFFER_DATA.get(conversa_id)
        if not data:
            data = {"texts": [], "payload": evo_msg.model_dump()}
            TEXT_BUFFER_DATA[conversa_id] = data
        else:
            data["payload"] = evo_msg.model_dump()
        data["texts"].append(texto)
        task = TEXT_BUFFER_TASKS.get(conversa_id)
        if task:
            task.cancel()
        TEXT_BUFFER_TASKS[conversa_id] = asyncio.create_task(_flush_text_buffer(conversa_id))
        count = len(data["texts"])
    await conversation_events_service.record(
        conversa_id,
        "text_buffered",
        payload={"count": count},
        mensagem_id=evo_msg.mensagem_id,
    )
    return True


async def _flush_text_buffer(conversa_id: str) -> None:
    try:
        await asyncio.sleep(settings.text_buffer_delay_seconds)
        async with TEXT_BUFFER_LOCK:
            data = TEXT_BUFFER_DATA.pop(conversa_id, None)
            TEXT_BUFFER_TASKS.pop(conversa_id, None)
        if not data:
            return
        texts = data["texts"]
        payload = data["payload"]
        aggregated = " ".join(t.strip() for t in texts if t.strip()).strip()
        if not aggregated:
            return
        await conversation_events_service.record(
            conversa_id,
            "text_buffer_flushed",
            payload={"count": len(texts)},
        )
        evo_data = payload.copy()
        evo_data["conteudo"] = aggregated
        evo_msg = EvolutionMessage(**evo_data)
        await process_message(evo_msg, override_text=aggregated)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("Erro ao processar buffer da conversa=%s error=%s", conversa_id, exc)


async def _process_document_message(evo_msg: EvolutionMessage, conversa: dict[str, Any], mensagem_id: str) -> None:
    try:
        extraction = await attachment_service.process_document(
            conversa_id=conversa["id"],
            mensagem_id=mensagem_id,
            media=evo_msg.media,
            conteudo=evo_msg.conteudo,
            caption=getattr(evo_msg.media, "caption", None),
        )
    except AttachmentProcessingError as exc:
        msg = "Nao consegui abrir o documento. Pode reenviar em PDF (ate 15MB) ou em formato DOCX?"
        await evolution_client.send_text(evo_msg.contato, msg)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", msg)
        await conversation_events_service.record(
            conversa["id"],
            "document_error",
            payload={"error": str(exc)},
        )
        return

    question = (extraction.caption or "").strip()
    if not question:
        follow_up = "Recebi o documento! Me conta qual duvida devo analisar nele."
        await evolution_client.send_text(evo_msg.contato, follow_up)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", follow_up)
        await conversation_events_service.record(
            conversa["id"],
            "document_missing_question",
            payload={},
        )
        return

    company = await company_config_service.get_profile()
    decision = await run_guardrail(question, extraction.summary, company.model_dump())
    if not decision.allowed:
        policy_message = decision.policy_message or "Consigo ajudar apenas com assuntos relacionados aos nossos empreendimentos."
        await evolution_client.send_text(evo_msg.contato, policy_message)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", policy_message)
        await conversation_events_service.record(
            conversa["id"],
            "document_blocked",
            payload={"reason": decision.reason},
        )
        return

    answer = await run_document_qa(question, extraction.markdown, company.model_dump())
    await evolution_client.send_text(evo_msg.contato, answer)
    await conversations_repo.log_message(conversa["id"], "sdr", "texto", answer)
    await conversation_events_service.record(
        conversa["id"],
        "document_answer",
        payload={"question": question},
        agent_key="document_qa",
    )
