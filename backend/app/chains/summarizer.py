from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.agent_config import AgentConfig, agent_config_service

settings = get_settings()

DEFAULT_CONFIG = AgentConfig(
    agent_key="summarizer",
    system_prompt="Resuma o texto a seguir em no maximo 300 tokens, mantendo fatos-chave e tom neutro.",
    model=settings.llm_model,
    temperature=0.0,
    max_tokens=300,
)


async def summarize_text(text: str) -> str:
    config = await agent_config_service.get_agent_config("summarizer", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            ("human", "{texto}"),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    result = await (prompt | llm).ainvoke({"texto": text})
    return result.content
