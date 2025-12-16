from typing import Any
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app.jobs.transcription import process_transcription
from app.orchestrator import process_message
from app.repos.conversations import ConversationsRepository
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient


router = APIRouter()
evolution_client = EvolutionClient()
conversation_service = ConversationService()
conversations_repo = ConversationsRepository()


class EvolutionMessage(BaseModel):
    mensagem_id: str
    contato: str
    tipo: str  # texto | audio | imagem | documento
    conteudo: str | None = None  # texto ou url de midia
    canal: str = "whatsapp"
    conversa_id: str | None = None


def parse_evolution_payload(raw: Any) -> EvolutionMessage:
    """
    Aceita payload direto (EvolutionMessage) ou payload do Evolution (body.data...).
    """
    # se vier como lista, pega o primeiro item
    if isinstance(raw, list) and raw:
        raw = raw[0]
    # se já está no formato esperado
    if isinstance(raw, dict) and all(k in raw for k in ["mensagem_id", "contato", "tipo"]):
        return EvolutionMessage(**raw)

    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="Payload invalido (nao eh JSON/objeto)")

    # aceita payload com ou sem body
    data = raw.get("data") or raw.get("body", {}).get("data", {}) or {}
    key = data.get("key") or {}
    message = data.get("message") or {}

    contato = key.get("remoteJid") or key.get("remoteJidAlt") or raw.get("sender") or ""
    if contato and "@s.whatsapp.net" in contato:
        contato = contato.replace("@s.whatsapp.net", "")
    mensagem_id = key.get("id") or ""
    message_type = data.get("messageType") or ""

    # mapeia tipos
    if message_type == "conversation":
        tipo = "texto"
        conteudo = message.get("conversation")
    else:
        # fallback genérico
        tipo = "texto"
        conteudo = message.get("conversation") or ""

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
        conversa_id=None,
    )


@router.post("/evolution")
async def evolution_webhook(request: Request, tasks: BackgroundTasks):
    try:
        payload = await request.json()
    except Exception as exc:
        body_bytes = await request.body()
        print(f"[webhook] JSON invalido: {exc}; body={body_bytes}")
        return {"status": "ignored", "reason": "json_invalid"}

    try:
        evo_msg = parse_evolution_payload(payload)
    except HTTPException as exc:
        print(f"[webhook] payload invalido: {exc.detail}; payload={payload}")
        return {"status": "ignored", "reason": exc.detail}
    except Exception as exc:
        print(f"[webhook] erro inesperado ao parsear payload: {exc}; payload={payload}")
        return {"status": "ignored", "reason": "parse_error"}

    conversa = await conversation_service.ensure_active_conversation(
        contato=evo_msg.contato, canal=evo_msg.canal, conversa_id=evo_msg.conversa_id
    )
    evo_msg.conversa_id = conversa["id"]

    # registra mensagem recebida
    logged = await conversations_repo.log_message(
        conversa_id=evo_msg.conversa_id,
        autor="lead",
        tipo=evo_msg.tipo,
        conteudo=evo_msg.conteudo,
    )

    if evo_msg.tipo == "audio":
        tasks.add_task(process_transcription, evo_msg, conversa, logged["id"])
        return {
            "status": "ack",
            "queued": "transcription",
            "conversa_id": conversa["id"],
            "mensagem_id": logged["id"],
        }
    try:
        response = await process_message(evo_msg)
    except Exception as exc:  # pragma: no cover - observability hook
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "response": response, "conversa_id": conversa["id"], "mensagem_id": logged["id"]}
