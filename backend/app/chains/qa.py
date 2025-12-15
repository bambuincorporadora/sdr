from langchain.chains import RetrievalQA
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings
from app.utils.db import get_supabase_client

settings = get_settings()

embeddings = OpenAIEmbeddings(model=settings.embeddings_model)
supabase_client = get_supabase_client()

# Placeholder vector store; expects pgvector table already configured.
vector_store = SupabaseVectorStore(
    client=supabase_client,
    embedding=embeddings,
    table_name="documentos_embeddings",
    query_name="match_documents",
)

retriever = vector_store.as_retriever(search_kwargs={"k": 5})

llm = ChatOpenAI(model=settings.llm_model, temperature=0)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True,
)
