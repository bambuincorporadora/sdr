from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.prompts.templates import MAIN_SYSTEM_PROMPT

settings = get_settings()

llm = ChatOpenAI(model=settings.llm_model, temperature=0)


class IntentOutput(BaseModel):
    label: str
    rationale: str

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            MAIN_SYSTEM_PROMPT
            + " Classifique a intencao do lead em seguir, encerrar, pergunta ou ruido. "
            "Retorne JSON com campos label e rationale. Se pergunta, label=pergunta.",
        ),
        ("human", "{input}"),
    ]
)

intention_router = prompt | llm.with_structured_output(schema=IntentOutput)
