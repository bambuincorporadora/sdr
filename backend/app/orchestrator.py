from __future__ import annotations

import logging
from typing import Any

from app.chains.intention import detect_intention
from app.chains.qa import run_qa
from app.repos.conversations import ConversationsRepository
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient
from app.services.events import conversation_events_service

evolution_client = EvolutionClient()
conversation_service = ConversationService()
conversations_repo = ConversationsRepository()
logger = logging.getLogger(__name__)


async def process_message(message: Any, override_text: str | None = None) -> dict[str, Any]:
    """
    Orquestra a mensagem: detectar intencao, responder QA ou seguir checklist,
    enviar midia se relevante e acionar reengajamento.
    """
    conversa = await conversation_service.ensure_active_conversation(
        contato=message.contato, canal=message.canal, conversa_id=message.conversa_id
    )
    texto = (override_text or message.conteudo or "").strip()
    intent = await detect_intention(texto)
    label = getattr(intent, "label", None) or intent.dict().get("label", "ruido")
    logger.info("Intent detectada=%s conversa=%s", label, conversa["id"])
    await conversation_events_service.record(
        conversa["id"],
        "intent_detected",
        payload={"label": label},
        agent_key="intention",
        mensagem_id=getattr(message, "mensagem_id", None),
    )
    if label not in {"pergunta", "seguir", "encerrar", "ruido"}:
        label = "pergunta" if "?" in texto else "seguir"

    if label == "pergunta":
        answer_text = await run_qa(texto)
        await evolution_client.send_text(message.contato, answer_text)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", answer_text)
        await conversation_service.touch_conversation(conversa["id"], status="respondendo_pergunta")
        await conversation_events_service.record(
            conversa["id"],
            "answer_sent",
            payload={"answer": answer_text},
            agent_key="qa",
        )
        return {"intent": label, "answer": answer_text, "conversa_id": conversa["id"]}

    if label == "seguir":
        prompt = "Posso seguir com algumas perguntas rapidas?"
        await evolution_client.send_text(message.contato, prompt)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", prompt)
        await conversation_service.touch_conversation(conversa["id"], status="qualificando")
        await conversation_events_service.record(
            conversa["id"],
            "qualifier_prompt",
            payload={"message": prompt},
        )
        return {"intent": label, "answer": prompt, "conversa_id": conversa["id"]}

    if label == "encerrar":
        closing = "Tudo bem, obrigado pelo retorno. Se mudar de ideia, e so chamar."
        await evolution_client.send_text(message.contato, closing)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", closing)
        await conversation_service.touch_conversation(conversa["id"], status="encerrar")
        await conversation_events_service.record(
            conversa["id"],
            "encerrar",
            payload={"message": closing},
        )
        return {"intent": label, "answer": closing, "conversa_id": conversa["id"]}

    reform = "Nao captei bem. Prefere saber sobre preco, plantas ou localizacao?"
    await evolution_client.send_text(message.contato, reform)
    await conversations_repo.log_message(conversa["id"], "sdr", "texto", reform)
    await conversation_service.touch_conversation(conversa["id"], status="aguardando_resposta")
    await conversation_events_service.record(
        conversa["id"],
        "ruido",
        payload={"message": reform},
    )
    return {"intent": label, "answer": reform, "conversa_id": conversa["id"]}
