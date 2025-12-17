from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI

from app.celery_app import celery_app
from app.config import get_settings
from app.orchestrator import process_message
from app.repos.conversations import ConversationsRepository
from app.schemas.evolution import EvolutionMessage
from app.services.evolution import EvolutionClient, EvolutionMediaError

settings = get_settings()
logger = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB safety cap
DOWNLOAD_CHUNK_SIZE = 64 * 1024
ALLOWED_AUDIO_SCHEMES = {"https"}
evolution_client = EvolutionClient()


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
    if not (message.conteudo or message.media):
        logger.warning("Payload sem referencia de audio conversa=%s mensagem=%s", conversa_id, mensagem_id)
        return

    repo = ConversationsRepository()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        tmp_path = await _prepare_audio_file(message)
    except (ValueError, EvolutionMediaError) as exc:
        logger.warning(
            "Audio rejeitado conversa=%s mensagem=%s reason=%s", conversa_id, mensagem_id, exc
        )
        return

    transcript = ""
    try:
        with open(tmp_path, "rb") as f:
            transcript = await client.audio.transcriptions.create(
                file=f, model=settings.whisper_model, response_format="text"
            )
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass

    texto = transcript or ""
    await repo.log_message(conversa_id=conversa_id, autor="lead", tipo="texto", conteudo=f"[transcricao] {texto}")
    message.conteudo = texto
    message.tipo = "texto"
    message.conversa_id = conversa_id
    logger.info("Transcricao concluida conversa=%s mensagem=%s", conversa_id, mensagem_id)
    await process_message(message, override_text=texto)


def _validate_audio_url(audio_url: str) -> None:
    parsed = urlparse(audio_url)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_AUDIO_SCHEMES:
        raise ValueError("url_invalida")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("url_invalida")
    allowed_hosts = [h for h in settings.trusted_media_hosts if h]
    if allowed_hosts and host not in allowed_hosts:
        raise ValueError("host_nao_permitido")


async def _download_audio(audio_url: str) -> str:
    _validate_audio_url(audio_url)
    timeout = httpx.Timeout(10.0, read=30.0)
    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    tmp_path = tmp.name
    total = 0
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as http:
            async with http.stream("GET", audio_url, headers={"Accept": "audio/*"}) as resp:
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                if content_length:
                    try:
                        length = int(content_length)
                    except (TypeError, ValueError):
                        logger.debug("Header content-length inesperado url=%s value=%s", audio_url, content_length)
                    else:
                        if length > MAX_AUDIO_BYTES:
                            raise ValueError("audio_grande_demais")
                async for chunk in resp.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_AUDIO_BYTES:
                        raise ValueError("audio_grande_demais")
                    tmp.write(chunk)
        tmp.flush()
        tmp.close()
        return tmp_path
    except Exception:
        tmp.close()
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


async def _prepare_audio_file(message: EvolutionMessage) -> str:
    media = message.media
    candidate_urls: list[str] = []
    if media and media.url:
        candidate_urls.append(media.url)
    if message.conteudo and isinstance(message.conteudo, str):
        candidate_urls.append(message.conteudo)
    for url in candidate_urls:
        try:
            return await _download_audio(url)
        except ValueError:
            continue
    if media and media.media_key:
        resolved_url = await evolution_client.resolve_media_url(
            media_key=media.media_key,
            direct_path=media.direct_path,
            message_type=media.message_type or message.tipo,
            message_id=message.mensagem_id,
        )
        return await _download_audio(resolved_url)
    raise ValueError("origem_audio_indisponivel")
