import tempfile

import httpx
from openai import AsyncOpenAI

from app.config import get_settings
from app.orchestrator import process_message
from app.repos.conversations import ConversationsRepository

settings = get_settings()


async def process_transcription(payload, conversa, mensagem_id: str) -> None:
    """
    Baixa audio do Evolution, transcreve via Whisper, salva transcricao e reprocessa mensagem com o texto.
    """
    audio_url = payload.conteudo
    if not audio_url:
        return

    repo = ConversationsRepository()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # baixar audio temporariamente
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
    await repo.log_message(conversa_id=conversa["id"], autor="lead", tipo="texto", conteudo=f"[transcricao] {texto}")
    payload.conteudo = texto
    await process_message(payload, override_text=texto)
