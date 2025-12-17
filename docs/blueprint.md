# SDR Multi-Agentes - Fluxo de Qualificacao de Leads

Blueprint para um orquestrador multiagentes em Python que qualifica leads de empreendimentos, conversa via WhatsApp (Evolution) com suporte a audio, responde perguntas a partir de documentos e entrega resumo ao corretor. Mantemos linguagem humana, perguntas de qualificacao uma a uma e handoff estruturado.

## Visao Geral dos Agentes
- Orquestrador: mantem estado, chama intencao, QA, qualificador, gere falhas e handoff.
- Intencao: classifica resposta em `seguir`, `encerrar`, `pergunta`, `ruido` (incluindo audio vazio ou sem fala).
- QA: responde com base em documentos do empreendimento/empresa (busca em embeddings), com fallback seguro.
- Qualificador: conduz checklist (uma pergunta por vez) com tom casual.
- Primeira Mensagem: gera abertura personalizada do empreendimento.
- Transcricao: recebe audio do Evolution, transcreve e devolve texto para os demais agentes.
- Escalonamento: pede reformulacao ou envia ao humano em caso de erro/baixa confianca.
- Midia contextual: durante qualificacao ou sob pedido, pode enviar plantas/imagens/books do empreendimento mais aderentes ao contexto (tipologia/bairro/interesse citado).
- Reengajamento: dispara lembretes se o lead ficar inativo (30 min, 3h, 6h) e, com 24h sem retorno do lead, gera handoff ao corretor com historico.
- Frontend admin: painel para cadastrar/editar empreendimentos, midias (plantas/books), documentos/FAQ e acompanhar conversas.

## Fluxo (incluindo audio)
1) Iniciar: envia primeira mensagem do empreendimento.
2) Aguardar resposta (texto ou audio).
3) Se audio: baixar do Evolution, enfileirar para transcricao, obter texto.
4) Detecao de intencao: decide seguir/encerrar/pergunta/ruido.
5) Se pergunta: QA responde e volta a aguardar.
6) Se seguir: dispara proxima pergunta de qualificacao pendente.
7) Se checklist concluido: gera resumo e envia ao corretor (handoff), avisa lead.
8) Se encerrar: envia despedida.
9) Reengajamento: se lead sem resposta apos interacao da SDR, enviar lembretes em 30min/3h/6h; se completar 24h desde a ultima mensagem do lead, handoff ao corretor com historico e status "sem resposta".

## Tecnologias (Python)
- FastAPI para webhooks do Evolution (recebimento de mensagens/audio) e endpoints internos.
- Tarefas assinc (Celery/RQ) para transcricao e busca em embeddings, evitando bloquear webhook.
- Vetorizacao/QA: embeddings (ex. OpenAI ou local) + busca vetorial (Supabase pgvector).
- Transcricao: Whisper (local ou API) para audio do Evolution.
- Armazenamento: Supabase Postgres (tabelas abaixo) + Supabase Storage para audios originais e transcricoes em JSON opcional.
- Observabilidade: logs estruturados + metricas (tempo ate handoff, taxa de resposta).

## Primeira Mensagem (exemplo)
> Oi, aqui e da equipe do empreendimento **{nome}**. Vi que voce se interessou. Resumo rapido: {2-3 diferenciais}, plantas a partir de {metragem}, valores indicativos a partir de {preco}, localizacao em {bairro/ponto}. Prefere tirar alguma duvida agora ou quer que eu faca algumas perguntas rapidas para adiantar com o corretor?

## Checklist de Qualificacao
Perguntar uma por vez:
1. Uso: morar ou investir?
2. Localizacao/ponto de referencia desejado.
3. Tipologia/metragem ou quartos/suites.
4. Faixa de valor ou forma de pagamento (financiamento/consorcio).
5. Prazo: mudanca imediata ou futura; disponibilidade para visita/contato.
6. Canal e horario preferido.

Tom: frases curtas, reconhecer respostas ("entendi", "show"), variar formulacoes para nao soar bot.

## Roteiros de Perguntas (ramo com interesse vs sem interesse)
- Quando o lead nao declara interesse especifico (descoberta de empreendimento):
  - Motivacao -> motivo_busca: "O que te motivou a buscar um novo imovel agora?"
  - Motivacao -> prazo_mudanca: "Voce tem algum prazo em mente para a mudanca?"
  - Perfil_imovel -> bairro_regiao: "Existe algum bairro ou regiao que voce mais gosta?"
  - Perfil_imovel -> quartos_necessarios: "De quantos quartos voce precisaria?"
  - Perfil_imovel -> caracteristica_essencial: "Tem algo que nao pode faltar de jeito nenhum nesse imovel?"
  - Capacidade_financeira -> forma_pagamento: "Como voce pensa em fazer o pagamento? Financiamento, recursos proprios?"
  - Capacidade_financeira -> faixa_investimento: "Qual a faixa de investimento que voce esta planejando?"
- Quando o lead ja cita empreendimento(s) ou interesse claro:
  - Etapa_decisao -> proxima_etapa: convite de visita/decorado com data/horario.
  - Etapa_decisao -> horizonte_decisao: "Prazo em mente para mudanca? 3, 6 meses ou mais?"
  - Finalidade_imovel: "Esse imovel seria para voce morar ou investir?"
  - Comparacao_mercado: "Visitou ou avaliou outros empreendimentos? Quais?"
  - Principais_atrativos: "Qual perfil faz mais sentido? Compacto 70m², amplo 90-150m², ou maior/3 suites/cobertura?"
  - Detalhes_financeiros -> clareza_valores: "Qual faixa de investimento esta confortavel avaliar?"
  - Detalhes_financeiros -> plano_pagamento: "Como pretende comprar? Financiamento, FGTS, consorcio, recursos proprios?"

Logica de escolha:
- Se mensagem inicial ja inclui empreendimentos (ou match exato/parecido no banco), seguir ramo "com interesse" e usar dados do empreendimento nas respostas/QA.
- Se nao houver match, seguir ramo "sem interesse" para descobrir perfil; usar respostas para sugerir empreendimentos do banco (filtro por bairro/faixa/metragem) e, ao sugerir, mudar para "com interesse".
- Cada pergunta tem flags `pergunta_feita` / `pergunta_respondida` para controle de estado; evitar repetir; variar texto ao relembrar.

## Supabase - Esquema de Tabelas (Postgres)
- `leads`  
  - `id` uuid PK  
  - `nome` text  
  - `canal` text (ex: 'whatsapp')  
  - `contato` text (numero/whatsapp id)  
  - `origem` text (campanha/fonte)  
  - `criacao_em` timestamptz default now()

- `empreendimentos`  
  - `id` uuid PK  
  - `slug` text unique  
  - `nome` text  
  - `cidade` text  
  - `bairro` text  
  - `endereco_referencia` text  
  - `faixa_preco_min` numeric  
  - `faixa_preco_max` numeric  
  - `metragem_min` numeric  
  - `metragem_max` numeric  
  - `quartos` jsonb (ex: [2,3])  
  - `suites` jsonb  
  - `status_obra` text  
  - `diferenciais` jsonb  
  - `plantas_url` text  
  - `decorado_info` text  
  - `contato_corretor` text  
  - `criacao_em` timestamptz default now()
  - (armazenar links de midia em tabela a seguir)

- `midias_empreendimento`  
  - `id` uuid PK  
  - `empreendimento_id` uuid FK->empreendimentos(id)  
  - `tipo` text ('planta', 'book', 'imagem')  
  - `descricao` text  
  - `tipologia` text (ex: '2q', '3q', 'cobertura')  
  - `url` text (Supabase Storage ou CDN)  
  - `criado_em` timestamptz default now()

- `leads_interesses`  
  - `id` uuid PK  
  - `lead_id` uuid FK->leads(id)  
  - `empreendimento_id` uuid FK->empreendimentos(id)  
  - `origem` text (ex: "lead_citou", "sugerido")  
  - `prioridade` int  
  - `criacao_em` timestamptz default now()

- `conversas`  
  - `id` uuid PK  
  - `lead_id` uuid FK->leads(id)  
  - `status` text (iniciar, aguardando_resposta, qualificando, respondendo_pergunta, handoff, encerrar)  
  - `empreendimento` text  
  - `ultima_intencao` text  
  - `ultima_interacao_em` timestamptz default now()

- `mensagens`  
  - `id` uuid PK  
  - `conversa_id` uuid FK->conversas(id)  
  - `autor` text ('lead' | 'sdr' | 'corretor')  
  - `tipo` text ('texto' | 'audio' | 'imagem' | 'documento')  
  - `conteudo` text (mensagem ou URL do arquivo)  
  - `recebido_em` timestamptz default now()

- `anexos_audio`  
  - `id` uuid PK  
  - `mensagem_id` uuid FK->mensagens(id)  
  - `evolution_media_id` text  
  - `arquivo_url` text (Supabase Storage)  
  - `duracao_s` numeric  
  - `mime_type` text  
  - `status_transcricao` text ('pendente','ok','falha')  
  - `criacao_em` timestamptz default now()

- `transcricoes`  
  - `id` uuid PK  
  - `anexo_audio_id` uuid FK->anexos_audio(id)  
  - `texto` text  
  - `modelo` text  
  - `custo_estimado` numeric  
  - `confianca` numeric  
  - `criacao_em` timestamptz default now()

- `intencoes`  
  - `id` uuid PK  
  - `mensagem_id` uuid FK->mensagens(id)  
  - `label` text  
  - `confianca` numeric  
  - `rationale` text  
  - `criacao_em` timestamptz default now()

- `reengajamentos`  
  - `id` uuid PK  
  - `conversa_id` uuid FK->conversas(id)  
  - `agendado_para` timestamptz  
  - `disparo_minutos` int (ex: 30, 180, 360)  
  - `executado_em` timestamptz  
  - `status` text ('pendente','enviado','cancelado','pulado')  
  - `mensagem` text (texto enviado)  
  - `criacao_em` timestamptz default now()

- `respostas_qa`  
  - `id` uuid PK  
  - `mensagem_id` uuid FK->mensagens(id) -- pergunta do lead  
  - `resposta` text  
  - `fontes` jsonb (trechos usados)  
  - `confianca` numeric  
  - `criacao_em` timestamptz default now()

- `qualificacao_respostas`  
  - `id` uuid PK  
  - `conversa_id` uuid FK->conversas(id)  
  - `pergunta_slug` text (uso, localizacao, tipologia, valor, prazo, canal)  
  - `resposta` text  
  - `capturado_em` timestamptz default now()

- `handoffs`  
  - `id` uuid PK  
  - `conversa_id` uuid FK->conversas(id)  
  - `resumo` text (payload enviado ao corretor)  
  - `enviado_para` text (contato do corretor)  
  - `enviado_em` timestamptz default now()

- `documentos` (para embeddings)  
  - `id` uuid PK  
  - `tipo` text ('empreendimento','faq','institucional')  
  - `empreendimento` text  
  - `titulo` text  
  - `conteudo` text  
  - `criacao_em` timestamptz default now()

- `documentos_embeddings` (pgvector)  
  - `id` uuid PK  
  - `documento_id` uuid FK->documentos(id)  
  - `embedding` vector  
  - `chunk` text  
  - `ordem` int  
  - index ivfflat em `embedding`
- `qualificador_perguntas`  
  - `id` uuid PK  
  - `slug` text unique (ex: uso, localizacao, tipologia)
  - `pergunta` text
  - `categoria` text (motivacao, perfil_imovel, etc.)
  - `ordem` int
  - `opcoes` jsonb (opcional para múltipla escolha)
  - `ativo` bool
- `qualificador_fluxo`  
  - `id` uuid PK
  - `cenario` text (ex: sem_interesse, com_interesse)
  - `pergunta_slug` text references qualificador_perguntas(slug)
  - `ordem` int
  - `condicao` jsonb (ex: depende de resposta anterior)

Indices recomendados: `idx_mensagens_conversa`, `idx_intencoes_mensagem`, `idx_qualificacao_conversa_pergunta`, `ivfflat_documentos_embeddings`.

## Supabase - Admin e Configurações Dinâmicas
- `ai_agents` (seed: `intention`, `qa`, `reengagement`, `summarizer`, `document_guardrail`, `document_qa`, `handoff_summary`)
- `ai_agent_configs` (prompt + modelo + params + metadata)
- `ai_agent_config_versions` (audit/rollback)
- `ai_tools` (catálogo global com `schema_json`)
- `ai_agent_tools` (whitelist habilitando cada tool por agente)
- `empresa_config` (dados da empresa + `policy_text`/`allowed_topics` + webhook)
- `admin_users` (controle de acesso do painel via Supabase Auth)
- `attachments` / `attachment_extractions` (PDF/DOCX salvo em Storage + markdown extraído)
- `conversation_events` (timeline/auditoria de mensagens, execuções de agentes, tools e webhooks)

Storage: bucket privado `attachments/{conversa_id}/{mensagem_id}/{attachment_id}.{ext}`. Aplicar RLS (download apenas com token ou via backend).

### Autenticação e RLS
- Backend usa chave de serviço para bypass das políticas.
- Frontend Admin usa JWT Supabase:
  - `ai_*`, `empresa_config`, `conversation_events`, `attachments`: `select` permitido apenas se `auth.uid()` em `admin_users` (`ativo=true`); `update` restrito a `role in ('admin','editor')`.
  - `conversas`, `mensagens`, `leads`: somente leitura para admins; escrita apenas via backend/celery.
  - Storage: política exigindo `auth.role() = 'authenticated'` e membership em `admin_users`; downloads públicos só com signed URL emitido pelo backend.
- FastAPI valida JWT (JWKS Supabase) em `/admin/*`, injeta `user_id` e verifica `admin_users.role`.

### Status (implementado vs. pendente)
- Implementado no backend:
  - Leitura de `ai_agent_configs` e `empresa_config` no Supabase com cache em memória (TTL).
  - `conversation_events` para trilha/auditoria do processamento.
  - Pipeline de anexos PDF/DOCX: download seguro + Storage + extração para markdown + guardrail + resposta baseada no documento.
  - Handoff via webhook (assinatura HMAC opcional) + persistência em `handoffs`.
- Pendente (o blueprint descreve, mas ainda precisa ser construído):
  - Endpoints `/admin/*` (CRUD de prompts/configs/tools/empresa/empreendimentos, leitura de conversas/eventos).
  - Frontend Admin (telas + autenticação + consumo do backend).
  - (Opcional) Ajustar seeds (prompts/params/tools) conforme a operação.
  - (Operacional) Aplicar o bloco de RLS/Storage no Supabase (incluído em `docs/schema.sql`).

### Tools para seed (schema_json no `docs/schema.sql`)
1. `get_company_config`
2. `list_empreendimentos`
3. `get_empreendimento`
4. `retrieve_documents`
5. `get_conversation_history`
6. `save_qualificacao` / `log_event`
7. `download_attachment`
8. `store_attachment`
9. `extract_document_to_markdown`
10. `document_relevance_check`
11. `answer_from_document`
12. `dispatch_handoff_webhook`

Associações iniciais:
- `qa`: `get_company_config`, `retrieve_documents`
- `reengagement`: `get_company_config`, `get_conversation_history`
- `summarizer`: `get_conversation_history`
- `document_guardrail`: `get_company_config`, `document_relevance_check`
- `document_qa`: `get_company_config`, `answer_from_document`
- `handoff_summary`: `get_company_config`, `get_conversation_history`, `dispatch_handoff_webhook`
- Pipeline técnico (download/store/extract) pode ficar em um agente interno `document_extractor`.

## Frontend Admin (web)
- Objetivo: CRUD de empreendimentos, midias, documentos/FAQ; visualizacao de conversas e status de qualificacao/handoff.
- Requisitos principais:
  - Autenticacao/roles basica (ex: admin/operador).
  - Formulario de empreendimento (dados gerais, faixa de preco, metragem, status obra, diferenciais, contato do corretor).
  - Upload/gestao de midias (plantas, books) com tipologia e descricao; gravar URLs no Supabase Storage.
  - Gestao de documentos/FAQ por empreendimento para feeding de embeddings.
  - Visual de conversas: lista e detalhe com mensagens, intencao detectada, pendencias de qualificacao, proximas perguntas, reengajamentos agendados.
  - Acionamento manual: reenviar midia, forcar handoff, marcar conversa como encerrada.
- Telas extras: Prompts/Config (por agente), Tools (habilitar/desabilitar), Empresa (policy), Usuários Admin.
- Stack sugerida: Next.js (App Router) + Supabase Auth + Shadcn UI. Backend expõe endpoints REST autenticados (JWT Supabase) para CRUD e teste de prompt/tool.
- Dashboard e monitoramento de conversas:
  - Lista filtrável de conversas (status, intenção atual, sla de resposta, agente usado, última mensagem).
  - Detalhe mostrando timeline (mensagens, transcrições, respostas de IA, reengajamentos disparados, anexos).
  - KPIs: leads ativos, tempo médio até handoff, taxa de resposta; logs com prompts/config usados (para auditoria).
- Endpoint/API correspondente: `GET /admin/conversations`, `GET /admin/conversations/{id}`, `GET /admin/conversations/{id}/events`.

### Implementação sugerida (Next.js + Supabase Auth)
1. **Stack**: Next.js 14 (App Router) + TypeScript + Supabase JS client + Shadcn UI + TanStack Query.
2. **Auth Flow**:
   - Página `/login` -> Supabase Auth (email/senha).
   - Middleware valida sessão e consulta `/admin/me` para obter `role`; redireciona se não for ativo.
3. **Layout/Páginas**:
   - `/dashboard`: cards (leads ativos, SLA médio), tabela de conversas com filtros (status, intenção, agente).
   - `/conversations/[id]`: timeline (mensagens, eventos, anexos), resumo rápido, ações (forçar handoff, reenviar).
   - `/prompts`: lista de agentes, editor de prompt/model/params, histórico de versões (com diff/rollback).
   - `/tools`: catálogo global + matriz (agent vs tool) com toggles e configs (limites, k, etc.).
   - `/empresa`: formulário para dados gerais, `policy_text`, contatos, URLs do webhook e secret (com teste de envio).
   - `/empreendimentos`: CRUD completo + upload de mídias (usando Supabase Storage) + preview.
   - `/usuarios`: gestão de `admin_users` (só role=admin).
4. **API Backend (endereços novos)**:
   - Auth guard: header `Authorization: Bearer <jwt>` validado via JWKS Supabase.
   - `GET /admin/me` -> retorna user + role.
   - `GET/PUT /admin/company`
   - `GET/PUT /admin/agents`, `/admin/agents/{key}`, `/admin/agents/{key}/versions`.
   - `GET/PUT /admin/tools`, `/admin/agents/{key}/tools`
   - `GET/POST /admin/empreendimentos`, `/admin/empreendimentos/{id}`, `/midias`
   - `GET /admin/conversations` (paginação/filtros), `GET /admin/conversations/{id}`, `GET /admin/conversations/{id}/events`
   - `POST /admin/actions/force-handoff`, `/admin/actions/send-media`
5. **Observabilidade/UI**:
   - Component global de “Testar prompt/tool”: chama endpoint `/admin/test-agent`.
   - Toast/Logs para erro de webhook/handoff (alimentado por `conversation_events`).
6. **DevFlow**:
   - Repositório `frontend/` com scripts `pnpm dev`/`build`.
   - `.env.local` com SUPABASE_URL/KEY; `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
   - Deploy em VPS via Docker/Compose apontando para backend via env `API_BASE_URL`.

## Pipeline de PDF/DOCX
- Limites: 15 MB, até 40 páginas, timeout de 30s. Rejeitar acima disso com mensagem amigável.
- MVP: extração via `pdfminer.six` (PDF) e `python-docx` (DOCX).
- Fase 2 (opcional): Docling como extrator principal (melhor estruturação/layout), mantendo fallback.
- Cache por `sha256` em `attachments`: se o mesmo arquivo reaparecer, reutilizar `attachment_extractions`.
- Truncar markdown para ~3k tokens e, na fase 2, gerar embeddings específicos para RAG do anexo.
- Se o lead enviar documento sem pergunta, confirmar (“Documento salvo, quer que eu analise algo específico?”). Se perguntar sem documento/previamente expirado, solicitar reenvio.

## Orquestracao - Pseudocodigo (adaptado)
```pseudo
webhook_evolution(event):
  salvar_mensagem(event)
  if event.tipo == audio:
    enfileirar_transcricao(event.mensagem_id)
    return ack()
  processar_mensagem(event.mensagem_id)

transcrever(mensagem_id):
  baixar_audio_evolution()
  salvar_anexo_audio()
  texto = whisper(audio)
  salvar_transcricao(texto)
  processar_mensagem(mensagem_id, override_texto=texto)

processar_mensagem(mensagem_id, override_texto?):
  texto = override_texto or mensagem.conteudo
  config_intencao = ConfigService.get('intention')
  # agente_intencao usa system_prompt/model vindos do Supabase
  intencao = agente_intencao(texto)
  if intencao == pergunta: resposta = agente_QA(texto)
  elif intencao == seguir: resposta = prox_pergunta_qualificacao()
  elif intencao == encerrar: resposta = despedida()
  elif intencao == ruido: resposta = pedir_reformulacao()
  enviar_resposta(resposta)
  atualizar_estado_conversa()
  agendar_reengajamentos(conversa_id)  # 30min, 3h, 6h; cancelar se lead responder

processar_documento(mensagem_id):
  anexar = AttachmentService.download_store_extract(mensagem_id)
  guardrail = agentes.document_guardrail(question=mensagem.conteudo, document_summary=anexar.resumo)
  if not guardrail.allowed:
    responder(guardrail.policy_message)
    return
  resposta = agentes.document_qa(question=mensagem.conteudo, document_markdown=anexar.markdown)
  responder(resposta)

# Buffer de mensagens em sequência ("picotadas"):
# MVP (single-réplica): buffer em memória no processo do FastAPI.
# Produção multi-réplica: manter no Redis/persistência um registro "pending_text:{conversa_id}".
# Sempre que chega mensagem textual, append ao buffer e agende (ou reagende) job com countdown (ex: 3-5s).
# Se chegar nova mensagem antes do job rodar, apenas atualize o buffer e retarde o job.
# Quando o job disparar, junte todo o texto acumulado e chame processar_mensagem (limpando o buffer).
# Diferenciar mídia/áudio: processar imediatamente sem buffer.

handoff(conversa_id):
  resumo = agentes.handoff_summary(
    question="resuma conversa para corretor",
    conversation_history=get_conversation_history(conversa_id),
    company_profile=get_company_config()
  )
  payload = {
    "lead_nome": lead.nome,
    "lead_contato": lead.contato,
    "conversa_id": conversa_id,
    "resumo": resumo,
    "status": conversa.status
  }
  if empresa_config.handoff_webhook_url:
    dispatch_handoff_webhook(payload, empresa_config.handoff_webhook_url, empresa_config.handoff_webhook_secret)
  registrar_conversation_event("handoff_webhook", payload)
  salvar_handoff(resumo, destino=conversa.contato_corretor)

reengajamento_cron():
  pendentes = buscar_reengajamentos_pendentes()
  for r in pendentes:
    enviar_resposta(r.mensagem)
    marcar_enviado(r)
  conversas_sem_resposta_24h = buscar_conversas_inativas(24h)
  for c in conversas_sem_resposta_24h:
    resumo = gerar_resumo_lead(c, status="sem_resposta_24h")
    enviar_para_corretor(resumo)
    informar_lead_handoff()
```

## Payload de Handoff ao Corretor
- Lead: nome, contato, canal.
- Interesse: empreendimento, tipologia/metragem, faixa de valor, uso.
- Urgencia: prazo, disponibilidade para visita.
- Perguntas em aberto e o que ja foi respondido.
- Sentimento/atitude percebida.
- Resumo IA configurável: agente `handoff_summary` usa prompt/versionamento no Supabase e retorna texto estruturado (blocos `contexto`, `oportunidades`, `proximos_passos`).
- Webhook CRM: backend envia `POST` assinado (`handoff_webhook_secret`) para `empresa_config.handoff_webhook_url` com `lead_nome`, `lead_contato`, `conversa_id`, `resumo`, `status`, `timestamp`, `origem`. Registrar sucesso/falha em `conversation_events`.
- Robustez: no MVP não há retry automático; para produção, adicionar retentativa (Celery) com backoff + limite e dead-letter, registrando tentativas em `conversation_events`.

## Consideracoes
- Evolucao do tom: variar abre/sim/nosso para soar humano.
- Limitar blocos grandes; sempre confirmar recepcao de audio ("recebi seu audio, ja transcrevendo") se demorar.
- Se dado nao existe: admitir e oferecer retorno com canal preferido.
- Logs: registrar tentativas de transcricao e de QA com confianca para revisao humana.
- Resumo e envio: respostas longas (especialmente QA) passam por sumarizador e sao quebradas em blocos de 200-400 tokens; enviar blocos em sequencia curta, priorizando fatos principais e oferta de ajuda no final.
- Admin Frontend: versionar alterações de prompt/tool, registrar auditoria e oferecer "test prompt/tool" com input de exemplo.
- `conversation_events` armazena timeline completa (mensagens, tools, webhooks) para painel e debugging.
