from langchain.chains.summarize import load_summarize_chain
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from app.config import get_settings

settings = get_settings()

llm = ChatOpenAI(model=settings.llm_model, temperature=0)
summary_chain = load_summarize_chain(llm, chain_type="map_reduce")


async def summarize_text(text: str) -> str:
    docs = [Document(page_content=text)]
    result = await summary_chain.ainvoke(docs)
    return result["output_text"]
