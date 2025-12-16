from typing import Any

from app.chains.intention import intention_router
from app.chains.qa import qa_chain
from app.chains.summarizer import summarize_text
from app.repos.conversations import ConversationsRepository
from app.services.conversations import ConversationService
from app.services.evolution import EvolutionClient

evolution_client = EvolutionClient()
conversation_service = ConversationService()
conversations_repo = ConversationsRepository()


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

    if label == "pergunta":
        answer = await qa_chain.ainvoke({"input": texto})
        answer_text = answer.get("answer") or answer.get("result") or ""
        short_answer = await summarize_text(answer_text)
        await evolution_client.send_text(message.contato, short_answer)
        await conversations_repo.log_message(conversa["id"], "sdr", "texto", short_answer)
        await conversation_service.touch_conversation(conversa["id"], status="respondendo_pergunta")
        return {"intent": label, "answer": short_answer, "conversa_id": conversa["id"]}

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
