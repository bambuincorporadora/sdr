from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.agent_config import AgentConfig, agent_config_service

settings = get_settings()

DEFAULT_PROMPT = (
    "Gere um resumo estruturado para o corretor com base no historico abaixo. "
    "Inclua: contexto geral, dores/objetivos, orcamento aproximado, status atual e proximos passos sugeridos. "
    "Se houver riscos (desinteresse, preocupacoes), destaque. Seja conciso (ate 5 topicos) e use bullet points."
)

DEFAULT_CONFIG = AgentConfig(
    agent_key="handoff_summary",
    system_prompt=DEFAULT_PROMPT,
    model=settings.llm_model,
    temperature=0.1,
    max_tokens=500,
)


async def generate_handoff_summary(history_text: str, company_profile: dict) -> str:
    config = await agent_config_service.get_agent_config("handoff_summary", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            (
                "human",
                "Perfil da empresa:\n{company}\n\nHistorico da conversa:\n{history}\n\nResuma para o corretor:",
            ),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    response = await (prompt | llm).ainvoke({"history": history_text, "company": company_profile})
    if hasattr(response, "content"):
        return response.content
    return str(response)
