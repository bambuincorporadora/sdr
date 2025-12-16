from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.config import get_settings

settings = get_settings()

llm = ChatOpenAI(model=settings.llm_model, temperature=0)

prompt = ChatPromptTemplate.from_template(
    "Resuma o texto a seguir em no maximo 300 tokens, mantendo fatos-chave e tom neutro:\n\n{texto}"
)


async def summarize_text(text: str) -> str:
    result = await (prompt | llm).ainvoke({"texto": text})
    return result.content
