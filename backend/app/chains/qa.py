from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
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

combine_docs_chain = create_stuff_documents_chain(llm, prompt)
qa_chain = create_retrieval_chain(retriever, combine_docs_chain)
