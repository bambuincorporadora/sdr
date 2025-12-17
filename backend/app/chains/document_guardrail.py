from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.services.agent_config import AgentConfig, agent_config_service

settings = get_settings()


class GuardrailDecision(BaseModel):
    allowed: bool
    reason: str | None = None
    policy_message: str | None = None


DEFAULT_PROMPT = (
    "Voce e um filtro de seguranca. Permita apenas perguntas ou documentos relacionados a empresa, "
    "imoveis, empreendimentos ou atendimento descritos no perfil abaixo. "
    "Se a pergunta ou documento nao estiver relacionado, retorne allowed=false e uma mensagem amigavel "
    "explicando que so pode ajudar sobre os temas permitidos."
)

DEFAULT_CONFIG = AgentConfig(
    agent_key="document_guardrail",
    system_prompt=DEFAULT_PROMPT,
    model=settings.llm_model,
    temperature=0.0,
    max_tokens=200,
)


async def run_guardrail(question: str, document_summary: str, company_profile: dict) -> GuardrailDecision:
    config = await agent_config_service.get_agent_config("document_guardrail", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            (
                "human",
                "Perfil da empresa:\n{company}\n\nResumo do documento:\n{document}\n\nPergunta do lead:\n{question}\n"
                "Responda em JSON indicando se deve permitir ou nao.",
            ),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    chain = prompt | llm.with_structured_output(schema=GuardrailDecision)
    return await chain.ainvoke({"question": question, "document": document_summary, "company": company_profile})
