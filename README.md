# SDR-IA

Backend em Python (FastAPI + LangChain) para SDR multiagentes com WhatsApp Evolution, transcricao de audio, qualificacao, QA com embeddings (Supabase pgvector), reengajamento e handoff ao corretor. Inclui blueprint em `docs/blueprint.md`.

## Estrutura
- `backend/app/main.py`: cria FastAPI e registra webhook Evolution.
- `backend/app/routes/webhook.py`: recebe mensagens; audios vao para fila de transcricao.
- `backend/app/orchestrator.py`: roteia intencao, QA, qualificador (stub), envia respostas.
- `backend/app/chains/*`: chains de intencao, QA (retriever Supabase), sumarizador.
- `backend/app/chains/reengagement.py`: gera mensagem de reengajamento usando historico da conversa.
- `backend/app/jobs/*`: transcricao (Whisper) e reengajamento.
- `backend/app/services/evolution.py`: cliente para envio via Evolution.
- `backend/app/utils/db.py`: cliente Supabase.
- `backend/app/prompts/templates.py`: prompts principais (sistema, QA, reengajamento, tom do qualificador).
- `backend/app/services/conversations.py`: garante que cada novo contato inicia nova conversa se a anterior foi encerrada/handoff/nutricao, preservando lead por contato.
- `backend/app/repos/conversations.py`: persistencia de mensagens/conversas/reengajamentos e resumo.
- `scripts/reengagement_runner.py`: loop a cada 5 min para disparar reengajamentos.
- `docs/blueprint.md`: desenho detalhado do fluxo e tabelas.

## Requisitos
Python 3.10+. Instale deps:
```bash
pip install -r requirements.txt
```

Configurar `.env` (exemplo):
```
EVOLUTION_BASE_URL=https://api.evolution.example
EVOLUTION_TOKEN=seu_token
EVOLUTION_INSTANCE=nome_da_instancia
EVOLUTION_WEBHOOK_SECRET=segredo_webhook
SUPABASE_URL=...
SUPABASE_KEY=...
OPENAI_API_KEY=...
LLM_MODEL=gpt-4o-mini
WHISPER_MODEL=whisper-1
EMBEDDINGS_MODEL=text-embedding-3-small
REDIS_URL=redis://localhost:6379/0
```

Rodar API:
```bash
uvicorn app.main:app --reload --app-dir backend
```

## Frontend Admin (stub)
Crie um app React/Next.js consumindo endpoints do backend para CRUD de empreendimentos, midias, documentos/FAQ e visualizacao de conversas. Use Supabase Auth para login e Supabase Storage para uploads.

## Deploy com Coolify
- Use o `Dockerfile` da raiz. No Coolify, configure uma aplicacao do tipo Docker.
- Adicione variaveis de ambiente conforme `.env` (Evolution, Supabase, OpenAI, Redis).
- Porta exposta: `8000`.
- Para rodar Redis junto via Coolify, importe o `docker-compose.yml` ou crie um recurso Redis separado e aponte `REDIS_URL`.
- Comando de start (ja no Dockerfile): `uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend`.
- Serviço de reengajamento: no compose existe o serviço `reengagement` que roda `scripts/reengagement_runner.py` a cada 5 minutos.
- Para transcricao assincrona, suba tambem o servi�o `worker` (Celery) do compose para tirar carga do webhook.

## Proximos passos
- Implementar fila de transcricao (Celery/RQ) com Whisper.
- Implementar qualificador/checklist com persistencia das perguntas no Supabase.
- Implementar escolha de midias contextuais e envio Evolution.
- Adicionar testes/mocks para webhook e chains.
