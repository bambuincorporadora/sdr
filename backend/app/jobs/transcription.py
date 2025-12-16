from __future__ import annotations

import asyncio
import logging
import tempfile

import httpx
from openai import AsyncOpenAI

from app.celery_app import celery_app
from app.config import get_settings
from app.orchestrator import process_message
from app.repos.conversations import ConversationsRepository
from app.schemas.evolution import EvolutionMessage

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task(name="transcription.process_audio", bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def enqueue_transcription(self, payload: dict, conversa_id: str, mensagem_id: str) -> None:
    """
    Celery task wrapper: executa a transcricao em um event loop isolado.
    """
    try:
        asyncio.run(_process_transcription(payload, conversa_id, mensagem_id))
    except Exception as exc:
        logger.error(
            "Transcricao falhou conversa=%s mensagem=%s error=%s", conversa_id, mensagem_id, exc
        )
        raise


async def _process_transcription(payload: dict, conversa_id: str, mensagem_id: str) -> None:
    """
    Baixa audio do Evolution, transcreve via Whisper, salva transcricao e reprocessa mensagem com o texto.
    """
    message = EvolutionMessage(**payload)
    audio_url = message.conteudo
    if not audio_url:
        logger.warning("Payload sem URL de audio conversa=%s mensagem=%s", conversa_id, mensagem_id)
        return

    repo = ConversationsRepository()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(audio_url)
        resp.raise_for_status()
        audio_bytes = resp.content

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        with open(tmp.name, "rb") as f:
            transcript = await client.audio.transcriptions.create(
                file=f, model=settings.whisper_model, response_format="text"
            )

    texto = transcript or ""
    await repo.log_message(conversa_id=conversa_id, autor="lead", tipo="texto", conteudo=f"[transcricao] {texto}")
    message.conteudo = texto
    message.tipo = "texto"
    message.conversa_id = conversa_id
    logger.info("Transcricao concluida conversa=%s mensagem=%s", conversa_id, mensagem_id)
    await process_message(message, override_text=texto)
