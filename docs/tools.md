# Ferramentas / Stack

## MVP (já suportado pelo backend)
- Evolution (WhatsApp): recebimento/envio de mensagens e mídia (áudio, documentos).
- Supabase (Postgres + Storage + Auth): DB, pgvector, Storage de anexos, Auth do painel e RLS.
- FastAPI/Uvicorn: webhook do Evolution e APIs internas.
- OpenAI (ou provedor compatível): LLMs, embeddings e transcrição (Whisper/API).
- LangChain: chains (intention/qa/summarizer/guardrails/handoff_summary) com prompts configuráveis no Supabase.
- Extração de documentos:
  - PDF: `pdfminer.six`
  - DOCX: `python-docx`

## Produção (recomendado)
- Redis: dedupe, lock distribuído e buffer de mensagens “picotadas” em multi-réplica.
- Celery/RQ: execução assíncrona (transcrição, extração de anexos, retentativa de webhook/handoff).
- Observabilidade: logs estruturados + métricas + tracing (ex: OpenTelemetry).

## Fase 2 (opcional)
- Docling: extração mais fiel de PDF/DOCX para markdown (layout/tabelas), mantendo fallback.
- Frontend Admin (Next.js/React): CRUD de prompts/configs/tools, empresa, empreendimentos/mídias e monitoramento de conversas.
