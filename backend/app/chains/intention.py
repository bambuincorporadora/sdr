from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.prompts.templates import MAIN_SYSTEM_PROMPT
from app.services.agent_config import AgentConfig, agent_config_service

settings = get_settings()


class IntentOutput(BaseModel):
    label: str
    rationale: str


DEFAULT_CONFIG = AgentConfig(
    agent_key="intention",
    system_prompt=MAIN_SYSTEM_PROMPT
    + " Classifique a intencao do lead em seguir, encerrar, pergunta ou ruido. "
    "Retorne JSON com campos label e rationale. Se pergunta, label=pergunta.",
    model=settings.llm_model,
    temperature=0.0,
    max_tokens=200,
)


async def detect_intention(text: str) -> IntentOutput:
    config = await agent_config_service.get_agent_config("intention", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            ("human", "{input}"),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    chain = prompt | llm.with_structured_output(schema=IntentOutput)
    return await chain.ainvoke({"input": text})
