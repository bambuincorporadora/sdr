from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.orchestrator import process_message
from app.jobs.transcription import process_transcription
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient
from app.repos.conversations import ConversationsRepository


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


@router.post("/evolution")
async def evolution_webhook(payload: EvolutionMessage, tasks: BackgroundTasks):
    conversa = await conversation_service.ensure_active_conversation(
        contato=payload.contato, canal=payload.canal, conversa_id=payload.conversa_id
    )
    payload.conversa_id = conversa["id"]

    # registra mensagem recebida
    logged = await conversations_repo.log_message(
        conversa_id=payload.conversa_id,
        autor="lead",
        tipo=payload.tipo,
        conteudo=payload.conteudo,
    )

    if payload.tipo == "audio":
        tasks.add_task(process_transcription, payload, conversa, logged["id"])
        return {"status": "ack", "queued": "transcription", "conversa_id": conversa["id"], "mensagem_id": logged["id"]}
    try:
        response = await process_message(payload)
    except Exception as exc:  # pragma: no cover - observability hook
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", "response": response, "conversa_id": conversa["id"], "mensagem_id": logged["id"]}
