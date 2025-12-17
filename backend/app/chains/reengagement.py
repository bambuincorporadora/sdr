from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.prompts.templates import MAIN_SYSTEM_PROMPT
from app.services.agent_config import AgentConfig, agent_config_service

settings = get_settings()

DEFAULT_CONFIG = AgentConfig(
    agent_key="reengagement",
    system_prompt=MAIN_SYSTEM_PROMPT
    + " Gere uma unica mensagem curta de reengajamento (max ~350 caracteres) "
    + "considerando o historico recente. Seja gentil, mencione se havia pergunta pendente "
    + "ou oferta de ajuda, e convide a responder. Nao repita a conversa inteira.",
    model=settings.llm_model,
    temperature=0.2,
    max_tokens=200,
)


async def build_reengagement_message(history: str, base_prompt: str) -> str:
    config = await agent_config_service.get_agent_config("reengagement", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            ("human", "Historico recente:\n{history}\nBase sugerida:\n{base_prompt}\nGere a mensagem:"),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    result = await (prompt | llm).ainvoke({"history": history, "base_prompt": base_prompt})
    return result.content
