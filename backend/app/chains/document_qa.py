from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.agent_config import AgentConfig, agent_config_service

settings = get_settings()

DEFAULT_PROMPT = (
    "Voce e uma assistente que responde usando exclusivamente o documento fornecido. "
    "Se a informacao nao estiver no documento, diga que nao encontrou e sugira verificar com o corretor."
)

DEFAULT_CONFIG = AgentConfig(
    agent_key="document_qa",
    system_prompt=DEFAULT_PROMPT,
    model=settings.llm_model,
    temperature=0.1,
    max_tokens=400,
)


async def run_document_qa(question: str, document_markdown: str, company_profile: dict) -> str:
    config = await agent_config_service.get_agent_config("document_qa", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            (
                "human",
                "Perfil da empresa:\n{company}\n\nDocumento:\n{document}\n\nPergunta: {question}",
            ),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    chain = prompt | llm
    response = await chain.ainvoke(
        {
            "company": company_profile,
            "document": document_markdown,
            "question": question,
        }
    )
    if hasattr(response, "content"):
        return response.content
    return str(response)
