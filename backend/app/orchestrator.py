import logging
from typing import Any

from app.chains.intention import intention_router
from app.chains.qa import qa_chain
from app.repos.conversations import ConversationsRepository
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient

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
    texto = override_text or message.conteudo or ""
    intent = await intention_router.ainvoke({"input": texto})
    label = getattr(intent, "label", None) or intent.get("label", "ruido")  # suporta BaseModel/dict
    logger.info("Intent detectada=%s conversa=%s", label, conversa["id"])
    if label not in {"pergunta", "seguir", "encerrar", "ruido"}:
        # fallback: se tem interrogação, trata como pergunta, senão como seguir
        label = "pergunta" if "?" in texto else "seguir"

    if label == "pergunta":
        answer = await qa_chain.ainvoke(texto)
        answer_text = answer if isinstance(answer, str) else answer.get("answer") or answer.get("result") or ""
        await evolution_client.send_text(message.contato, answer_text)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", answer_text)
        await conversation_service.touch_conversation(conversa["id"], status="respondendo_pergunta")
        return {"intent": label, "answer": answer_text, "conversa_id": conversa["id"]}

    if label == "seguir":
        prompt = "Posso seguir com algumas perguntas rapidas?"
        await evolution_client.send_text(message.contato, prompt)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", prompt)
        await conversation_service.touch_conversation(conversa["id"], status="qualificando")
        return {"intent": label, "answer": prompt, "conversa_id": conversa["id"]}

    if label == "encerrar":
        closing = "Tudo bem, obrigado pelo retorno. Se mudar de ideia, e so chamar."
        await evolution_client.send_text(message.contato, closing)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", closing)
        await conversation_service.touch_conversation(conversa["id"], status="encerrar")
        return {"intent": label, "answer": closing, "conversa_id": conversa["id"]}

    reform = "Nao captei bem. Prefere saber sobre preco, plantas ou localizacao?"
    await evolution_client.send_text(message.contato, reform)
    await conversations_repo.log_message(conversa["id"], "sdr", "texto", reform)
    await conversation_service.touch_conversation(conversa["id"], status="aguardando_resposta")
    return {"intent": label, "answer": reform, "conversa_id": conversa["id"]}
