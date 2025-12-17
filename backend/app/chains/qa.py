from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings
from app.prompts.templates import QA_SYSTEM_PROMPT
from app.services.agent_config import AgentConfig, agent_config_service
from app.utils.db import get_supabase_client

settings = get_settings()

embeddings = OpenAIEmbeddings(model=settings.embeddings_model)
supabase_client = get_supabase_client()

vector_store = SupabaseVectorStore(
    client=supabase_client,
    embedding=embeddings,
    table_name="documentos_embeddings",
    query_name="match_documents",
)

retriever = vector_store.as_retriever(search_kwargs={"k": 5})

DEFAULT_CONFIG = AgentConfig(
    agent_key="qa",
    system_prompt=QA_SYSTEM_PROMPT
    + " Use apenas informacoes do contexto e limite-se a respostas curtas (max 4 frases e 400 caracteres).",
    model=settings.llm_model,
    temperature=0.0,
    max_tokens=400,
)


async def run_qa(question: str) -> str:
    docs = await retriever.aget_relevant_documents(question)
    context = "\n\n".join(doc.page_content for doc in docs)
    config = await agent_config_service.get_agent_config("qa", DEFAULT_CONFIG)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", config.system_prompt),
            ("human", "Contexto:\n{context}\n\nPergunta: {input}"),
        ]
    )
    llm = ChatOpenAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    chain = prompt | llm | StrOutputParser()
    return await chain.ainvoke({"context": context, "input": question})
