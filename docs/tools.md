# Ferramentas necessárias

- Evolution (WhatsApp) — recepção/envio de mensagens e mídia (áudio, imagens, documentos).
- Supabase (Postgres + Storage + Auth opcional) — tabelas, pgvector, storage de mídias.
- Redis — fila/broker para jobs (transcrição, reengajamento).
- OpenAI (ou provedor LLM/Whisper compatível) — LLMs, embeddings, transcrição.
- LangChain — orquestração de chains (intenção, QA, sumarização, reengajamento).
- FastAPI/Uvicorn — API/webhook do Evolution e endpoints internos.
- Celery/RQ — execução assíncrona de transcrição e tarefas.
- Next.js/React (Frontend admin) — CRUD de empreendimentos, mídias, documentos, visão de conversas.
