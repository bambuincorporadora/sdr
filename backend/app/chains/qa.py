from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings
from app.utils.db import get_supabase_client

settings = get_settings()

embeddings = OpenAIEmbeddings(model=settings.embeddings_model)
supabase_client = get_supabase_client()

# Vector store com funcao match_documents no Supabase/pgvector
vector_store = SupabaseVectorStore(
    client=supabase_client,
    embedding=embeddings,
    table_name="documentos_embeddings",
    query_name="match_documents",
)

retriever = vector_store.as_retriever(search_kwargs={"k": 5})

llm = ChatOpenAI(model=settings.llm_model, temperature=0)

prompt = ChatPromptTemplate.from_template(
    "Responda de forma concisa usando apenas o contexto. "
    "Se a resposta nao estiver no contexto, admita que nao sabe e ofereca confirmar. "
    "Contexto:\n{context}\n\nPergunta: {input}"
)

# Formata documentos concatenando conteudo
def _format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# RAG chain na sintaxe LCEL (LangChain 0.2+), sem uso de langchain.chains.*
qa_chain = (
    {
        "context": retriever | RunnableLambda(_format_docs),
        "input": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)
