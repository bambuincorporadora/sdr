from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.prompts.templates import MAIN_SYSTEM_PROMPT

settings = get_settings()

llm = ChatOpenAI(model=settings.llm_model, temperature=0.2)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            MAIN_SYSTEM_PROMPT
            + " Gere uma unica mensagem curta de reengajamento (max ~350 caracteres) "
            + "considerando o historico recente. Seja gentil, mencione se havia pergunta pendente "
            + "ou oferta de ajuda, e convide a responder. Nao repita a conversa inteira.",
        ),
        (
            "human",
            "Historico recente:\n{history}\nBase sugerida:\n{base_prompt}\nGere a mensagem:",
        ),
    ]
)


async def build_reengagement_message(history: str, base_prompt: str) -> str:
    result = await (prompt | llm).ainvoke({"history": history, "base_prompt": base_prompt})
    return result.content
