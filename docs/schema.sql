-- Extensao pgvector (necessaria para embeddings)
create extension if not exists vector;

-- Tabelas principais (Postgres/Supabase)
create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  nome text,
  canal text default 'whatsapp',
  contato text unique not null,
  origem text,
  criacao_em timestamptz default now()
);

create table if not exists empreendimentos (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  nome text not null,
  cidade text,
  bairro text,
  endereco_referencia text,
  faixa_preco_min numeric,
  faixa_preco_max numeric,
  metragem_min numeric,
  metragem_max numeric,
  quartos jsonb,
  suites jsonb,
  status_obra text,
  diferenciais jsonb,
  plantas_url text,
  decorado_info text,
  contato_corretor text,
  criacao_em timestamptz default now()
);

create table if not exists leads_interesses (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  empreendimento_id uuid references empreendimentos(id) on delete cascade,
  origem text,
  prioridade int,
  criacao_em timestamptz default now()
);

create table if not exists conversas (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references leads(id) on delete cascade,
  status text default 'iniciar',
  empreendimento text,
  ultima_intencao text,
  ultima_interacao_em timestamptz default now()
);

create table if not exists mensagens (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid references conversas(id) on delete cascade,
  autor text check (autor in ('lead','sdr','corretor')),
  tipo text check (tipo in ('texto','audio','imagem','documento')),
  conteudo text,
  evolution_mensagem_id text unique,
  recebido_em timestamptz default now()
);

create table if not exists anexos_audio (
  id uuid primary key default gen_random_uuid(),
  mensagem_id uuid references mensagens(id) on delete cascade,
  evolution_media_id text,
  arquivo_url text,
  duracao_s numeric,
  mime_type text,
  status_transcricao text default 'pendente',
  criacao_em timestamptz default now()
);

create table if not exists transcricoes (
  id uuid primary key default gen_random_uuid(),
  anexo_audio_id uuid references anexos_audio(id) on delete cascade,
  texto text,
  modelo text,
  custo_estimado numeric,
  confianca numeric,
  criacao_em timestamptz default now()
);

create table if not exists intencoes (
  id uuid primary key default gen_random_uuid(),
  mensagem_id uuid references mensagens(id) on delete cascade,
  label text,
  confianca numeric,
  rationale text,
  criacao_em timestamptz default now()
);

create table if not exists respostas_qa (
  id uuid primary key default gen_random_uuid(),
  mensagem_id uuid references mensagens(id) on delete cascade,
  resposta text,
  fontes jsonb,
  confianca numeric,
  criacao_em timestamptz default now()
);

create table if not exists qualificacao_respostas (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid references conversas(id) on delete cascade,
  pergunta_slug text,
  resposta text,
  capturado_em timestamptz default now()
);

create table if not exists handoffs (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid references conversas(id) on delete cascade,
  resumo text,
  enviado_para text,
  enviado_em timestamptz default now()
);

create table if not exists documentos (
  id uuid primary key default gen_random_uuid(),
  tipo text check (tipo in ('empreendimento','faq','institucional')),
  empreendimento text,
  titulo text,
  conteudo text,
  criacao_em timestamptz default now()
);

-- pgvector precisa estar instalado na instancia
create table if not exists documentos_embeddings (
  id uuid primary key default gen_random_uuid(),
  documento_id uuid references documentos(id) on delete cascade,
  -- defina a dimensao conforme o modelo de embeddings usado (ex: 1536 para text-embedding-3-small)
  embedding vector(1536),
  chunk text,
  ordem int
);
create index if not exists idx_documentos_embeddings_vec on documentos_embeddings using ivfflat (embedding vector_cosine_ops);

create table if not exists qualificador_perguntas (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  pergunta text not null,
  categoria text,
  ordem int,
  opcoes jsonb,
  ativo bool default true,
  created_at timestamptz default now()
);

create table if not exists qualificador_fluxo (
  id uuid primary key default gen_random_uuid(),
  cenario text not null,
  pergunta_slug text references qualificador_perguntas(slug) on delete cascade,
  ordem int not null,
  condicao jsonb,
  unique (cenario, pergunta_slug)
);

create table if not exists midias_empreendimento (
  id uuid primary key default gen_random_uuid(),
  empreendimento_id uuid references empreendimentos(id) on delete cascade,
  tipo text check (tipo in ('planta','book','imagem')),
  descricao text,
  tipologia text,
  url text,
  criado_em timestamptz default now()
);

create table if not exists reengajamentos (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid references conversas(id) on delete cascade,
  agendado_para timestamptz,
  disparo_minutos int,
  executado_em timestamptz,
  status text,
  mensagem text,
  criacao_em timestamptz default now()
);

create table if not exists evolution_webhook_events (
  mensagem_id text primary key,
  recebido_em timestamptz default now()
);

-- Admin / configuracoes dinamicas
create table if not exists ai_agents (
  key text primary key,
  nome text not null,
  descricao text,
  ativo bool default true,
  criado_em timestamptz default now()
);

create table if not exists ai_agent_configs (
  agent_key text primary key references ai_agents(key) on delete cascade,
  system_prompt text not null,
  model text not null default 'gpt-4o-mini',
  temperature numeric default 0,
  max_tokens int default 400,
  metadata jsonb default '{}'::jsonb,
  updated_at timestamptz default now(),
  updated_by uuid
);

create table if not exists ai_agent_config_versions (
  id uuid primary key default gen_random_uuid(),
  agent_key text references ai_agents(key) on delete cascade,
  snapshot jsonb not null,
  change_note text,
  created_at timestamptz default now(),
  created_by uuid
);

create table if not exists ai_tools (
  key text primary key,
  nome text not null,
  descricao text,
  schema_json jsonb not null default '{}'::jsonb,
  enabled_default bool default true,
  created_at timestamptz default now()
);

create table if not exists ai_agent_tools (
  agent_key text references ai_agents(key) on delete cascade,
  tool_key text references ai_tools(key) on delete cascade,
  enabled bool default true,
  config jsonb default '{}'::jsonb,
  primary key (agent_key, tool_key)
);

create table if not exists empresa_config (
  id uuid primary key default gen_random_uuid(),
  nome text,
  descricao text,
  contatos jsonb,
  policy_text text,
  allowed_topics jsonb,
  handoff_webhook_url text,
  handoff_webhook_secret text,
  updated_at timestamptz default now()
);

create table if not exists attachments (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid references conversas(id) on delete cascade,
  mensagem_id uuid references mensagens(id) on delete cascade,
  mime_type text,
  ext text,
  size_bytes int,
  sha256 text,
  storage_path text,
  status text default 'uploaded',
  criado_em timestamptz default now()
);

create table if not exists attachment_extractions (
  id uuid primary key default gen_random_uuid(),
  attachment_id uuid unique references attachments(id) on delete cascade,
  markdown text,
  metadata jsonb,
  tokens_est int,
  created_at timestamptz default now()
);

create table if not exists admin_users (
  user_id uuid primary key,
  role text default 'editor',
  ativo bool default true,
  created_at timestamptz default now()
);

create table if not exists conversation_events (
  id uuid primary key default gen_random_uuid(),
  conversa_id uuid references conversas(id) on delete cascade,
  mensagem_id uuid references mensagens(id) on delete set null,
  event_type text not null,
  agent_key text,
  payload jsonb,
  created_at timestamptz default now(),
  constraint conversation_events_event_type_ck check (event_type <> '')
);

create index if not exists idx_conversation_events_conversa on conversation_events(conversa_id, created_at desc);
create index if not exists idx_conversation_events_agent on conversation_events(agent_key, created_at desc);

-- Seeds recomendados para agentes
insert into ai_agents (key, nome, descricao)
values
  ('intention', 'Intencao', 'Classificador de intencao do lead'),
  ('qa', 'Perguntas e Respostas', 'Responder duvidas com base em documentos'),
  ('reengagement', 'Reengajamento', 'Mensagem automatica para leads inativos'),
  ('summarizer', 'Sumarizador', 'Resumo de conversas e eventos'),
  ('document_guardrail', 'Guarda de Documentos', 'Filtro de relevancia para anexos'),
  ('document_qa', 'QA de Documento', 'Responde usando PDF/DOCX enviados pelo lead'),
  ('handoff_summary', 'Resumo para Handoff', 'Gera resumo e payload do lead para envio ao corretor')
on conflict (key) do nothing;

-- Indices recomendados
create index if not exists idx_mensagens_conversa on mensagens(conversa_id, recebido_em desc);
create index if not exists idx_intencoes_mensagem on intencoes(mensagem_id);
create index if not exists idx_qualificacao_conversa_pergunta on qualificacao_respostas(conversa_id, pergunta_slug);
create index if not exists idx_reengajamento_conversa on reengajamentos(conversa_id, agendado_para);

-- Função placeholder para match de embeddings (ajuste conforme supabase/pgvector)
create or replace function match_documents(query_embedding vector, match_count int)
returns table(id uuid, documento_id uuid, chunk text, similarity float)
language sql stable as $$
  select id, documento_id, chunk,
    1 - (embedding <=> query_embedding) as similarity
  from documentos_embeddings
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- =====================================================================================
-- RLS (Row Level Security) - Painel Admin
-- Observação:
-- - O backend deve usar a Service Role Key (bypass de RLS).
-- - O Frontend Admin deve usar JWT do Supabase Auth + políticas abaixo.
-- Ajuste roles conforme seu modelo (admin/editor/viewer).
-- =====================================================================================

create or replace function public.is_active_admin()
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.admin_users au
    where au.user_id = auth.uid()
      and au.ativo = true
  );
$$;

create or replace function public.is_admin_editor()
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.admin_users au
    where au.user_id = auth.uid()
      and au.ativo = true
      and au.role in ('admin', 'editor')
  );
$$;

-- Tabelas admin/config
alter table public.ai_agents enable row level security;
alter table public.ai_agent_configs enable row level security;
alter table public.ai_agent_config_versions enable row level security;
alter table public.ai_tools enable row level security;
alter table public.ai_agent_tools enable row level security;
alter table public.empresa_config enable row level security;
alter table public.admin_users enable row level security;

drop policy if exists admin_select_ai_agents on public.ai_agents;
create policy admin_select_ai_agents
on public.ai_agents for select
using (public.is_active_admin());

drop policy if exists admin_write_ai_agents on public.ai_agents;
create policy admin_write_ai_agents
on public.ai_agents for all
using (public.is_admin_editor())
with check (public.is_admin_editor());

drop policy if exists admin_select_ai_agent_configs on public.ai_agent_configs;
create policy admin_select_ai_agent_configs
on public.ai_agent_configs for select
using (public.is_active_admin());

drop policy if exists admin_write_ai_agent_configs on public.ai_agent_configs;
create policy admin_write_ai_agent_configs
on public.ai_agent_configs for all
using (public.is_admin_editor())
with check (public.is_admin_editor());

drop policy if exists admin_select_ai_agent_config_versions on public.ai_agent_config_versions;
create policy admin_select_ai_agent_config_versions
on public.ai_agent_config_versions for select
using (public.is_active_admin());

drop policy if exists admin_write_ai_agent_config_versions on public.ai_agent_config_versions;
create policy admin_write_ai_agent_config_versions
on public.ai_agent_config_versions for insert
with check (public.is_admin_editor());

drop policy if exists admin_select_ai_tools on public.ai_tools;
create policy admin_select_ai_tools
on public.ai_tools for select
using (public.is_active_admin());

drop policy if exists admin_write_ai_tools on public.ai_tools;
create policy admin_write_ai_tools
on public.ai_tools for all
using (public.is_admin_editor())
with check (public.is_admin_editor());

drop policy if exists admin_select_ai_agent_tools on public.ai_agent_tools;
create policy admin_select_ai_agent_tools
on public.ai_agent_tools for select
using (public.is_active_admin());

drop policy if exists admin_write_ai_agent_tools on public.ai_agent_tools;
create policy admin_write_ai_agent_tools
on public.ai_agent_tools for all
using (public.is_admin_editor())
with check (public.is_admin_editor());

drop policy if exists admin_select_empresa_config on public.empresa_config;
create policy admin_select_empresa_config
on public.empresa_config for select
using (public.is_active_admin());

drop policy if exists admin_write_empresa_config on public.empresa_config;
create policy admin_write_empresa_config
on public.empresa_config for all
using (public.is_admin_editor())
with check (public.is_admin_editor());

drop policy if exists admin_select_admin_users on public.admin_users;
create policy admin_select_admin_users
on public.admin_users for select
using (public.is_active_admin());

drop policy if exists admin_write_admin_users_admin_only on public.admin_users;
create policy admin_write_admin_users_admin_only
on public.admin_users for all
using (
  exists (
    select 1
    from public.admin_users au
    where au.user_id = auth.uid()
      and au.ativo = true
      and au.role = 'admin'
  )
)
with check (
  exists (
    select 1
    from public.admin_users au
    where au.user_id = auth.uid()
      and au.ativo = true
      and au.role = 'admin'
  )
);

-- Tabelas de acompanhamento (somente leitura no painel)
alter table public.leads enable row level security;
alter table public.conversas enable row level security;
alter table public.mensagens enable row level security;
alter table public.conversation_events enable row level security;
alter table public.attachments enable row level security;
alter table public.attachment_extractions enable row level security;
alter table public.handoffs enable row level security;

drop policy if exists admin_select_leads on public.leads;
create policy admin_select_leads
on public.leads for select
using (public.is_active_admin());

drop policy if exists admin_select_conversas on public.conversas;
create policy admin_select_conversas
on public.conversas for select
using (public.is_active_admin());

drop policy if exists admin_select_mensagens on public.mensagens;
create policy admin_select_mensagens
on public.mensagens for select
using (public.is_active_admin());

drop policy if exists admin_select_conversation_events on public.conversation_events;
create policy admin_select_conversation_events
on public.conversation_events for select
using (public.is_active_admin());

drop policy if exists admin_select_attachments on public.attachments;
create policy admin_select_attachments
on public.attachments for select
using (public.is_active_admin());

drop policy if exists admin_select_attachment_extractions on public.attachment_extractions;
create policy admin_select_attachment_extractions
on public.attachment_extractions for select
using (public.is_active_admin());

drop policy if exists admin_select_handoffs on public.handoffs;
create policy admin_select_handoffs
on public.handoffs for select
using (public.is_active_admin());

-- Storage (Supabase) - bucket privado "attachments"
-- 1) Criar bucket no painel do Supabase: attachments (private)
-- 2) Aplicar policies em storage.objects (ajuste o schema se necessário):
--    alter table storage.objects enable row level security;
--    create policy admin_read_attachments_bucket
--    on storage.objects for select
--    using (bucket_id = 'attachments' and public.is_active_admin());
--
-- Downloads para o lead devem ser via signed URL emitido pelo backend.

-- =====================================================================================
-- Seeds recomendados (MVP): configs + tools + associações
-- =====================================================================================

-- Configs default por agente (edite os prompts conforme sua operação)
insert into public.ai_agent_configs (agent_key, system_prompt, model, temperature, max_tokens, metadata)
values
  (
    'intention',
    'Você classifica a mensagem do lead em: seguir, encerrar, pergunta, ruido. Responda somente com o label.',
    'gpt-4o-mini',
    0,
    120,
    '{}'::jsonb
  ),
  (
    'qa',
    'Você responde apenas com informações presentes nos documentos recuperados. Se não houver, diga que não encontrou.',
    'gpt-4o-mini',
    0.2,
    500,
    '{}'::jsonb
  ),
  (
    'reengagement',
    'Você cria mensagens curtas e humanas para retomar a conversa sem pressionar. Não invente informações.',
    'gpt-4o-mini',
    0.2,
    200,
    '{}'::jsonb
  ),
  (
    'summarizer',
    'Resuma o texto a seguir em no máximo 300 tokens, mantendo fatos-chave e tom neutro.',
    'gpt-4o-mini',
    0,
    300,
    '{}'::jsonb
  ),
  (
    'document_guardrail',
    'Você é um filtro de segurança. Permita apenas perguntas/documentos relacionados à empresa e empreendimentos. Se não for relacionado, bloqueie com uma mensagem amigável.',
    'gpt-4o-mini',
    0,
    200,
    '{}'::jsonb
  ),
  (
    'document_qa',
    'Você responde usando exclusivamente o documento fornecido. Se a informação não estiver no documento, diga que não encontrou.',
    'gpt-4o-mini',
    0.1,
    600,
    '{}'::jsonb
  ),
  (
    'handoff_summary',
    'Gere um resumo estruturado para o corretor com base no histórico. Seja conciso e use bullet points.',
    'gpt-4o-mini',
    0.1,
    700,
    '{}'::jsonb
  )
on conflict (agent_key) do update
set
  system_prompt = excluded.system_prompt,
  model = excluded.model,
  temperature = excluded.temperature,
  max_tokens = excluded.max_tokens,
  metadata = excluded.metadata,
  updated_at = now();

-- Catálogo de tools (governança no painel; schema_json é um contrato de entrada/saída)
insert into public.ai_tools (key, nome, descricao, schema_json, enabled_default)
values
  (
    'get_company_config',
    'Get Company Config',
    'Lê o perfil e políticas da empresa (empresa_config).',
    '{"args":{},"returns":{"company_profile":"object"}}'::jsonb,
    true
  ),
  (
    'list_empreendimentos',
    'List Empreendimentos',
    'Lista empreendimentos disponíveis.',
    '{"args":{"filters":{"type":"object"}},"returns":{"items":"array"}}'::jsonb,
    true
  ),
  (
    'get_empreendimento',
    'Get Empreendimento',
    'Obtém detalhes de um empreendimento pelo id/slug.',
    '{"args":{"id":{"type":"string","format":"uuid"},"slug":{"type":"string"}},"returns":{"item":"object"}}'::jsonb,
    true
  ),
  (
    'retrieve_documents',
    'Retrieve Documents',
    'Busca trechos relevantes via pgvector (match_documents).',
    '{"args":{"query":{"type":"string"},"k":{"type":"integer"}},"returns":{"chunks":"array"}}'::jsonb,
    true
  ),
  (
    'get_conversation_history',
    'Get Conversation History',
    'Retorna histórico de mensagens (conversa_id).',
    '{"args":{"conversa_id":{"type":"string","format":"uuid"}},"returns":{"history":"string"}}'::jsonb,
    true
  ),
  (
    'log_event',
    'Log Event',
    'Registra um evento em conversation_events.',
    '{"args":{"conversa_id":{"type":"string","format":"uuid"},"event_type":{"type":"string"},"payload":{"type":"object"}},"returns":{"ok":"boolean"}}'::jsonb,
    true
  ),
  (
    'save_qualificacao',
    'Save Qualificacao',
    'Persiste uma resposta de qualificação em qualificacao_respostas.',
    '{"args":{"conversa_id":{"type":"string","format":"uuid"},"pergunta_slug":{"type":"string"},"resposta":{"type":"string"}},"returns":{"ok":"boolean"}}'::jsonb,
    true
  ),
  (
    'download_attachment',
    'Download Attachment',
    'Baixa um anexo via Evolution/URL resolvida com limites (SSRF/DoS).',
    '{"args":{"url":{"type":"string"},"max_bytes":{"type":"integer"}},"returns":{"bytes_b64":"string"}}'::jsonb,
    true
  ),
  (
    'store_attachment',
    'Store Attachment',
    'Salva um anexo no Supabase Storage (bucket attachments) e registra em attachments.',
    '{"args":{"conversa_id":{"type":"string","format":"uuid"},"mensagem_id":{"type":"string","format":"uuid"},"ext":{"type":"string"},"bytes_b64":{"type":"string"}},"returns":{"attachment_id":"string","storage_path":"string"}}'::jsonb,
    true
  ),
  (
    'extract_document_to_markdown',
    'Extract Document To Markdown',
    'Extrai PDF/DOCX para markdown e persiste em attachment_extractions.',
    '{"args":{"attachment_id":{"type":"string","format":"uuid"}},"returns":{"markdown":"string","metadata":"object"}}'::jsonb,
    true
  ),
  (
    'document_relevance_check',
    'Document Relevance Check',
    'Aplica guardrail de relevância com base na empresa e pergunta.',
    '{"args":{"question":{"type":"string"},"document_summary":{"type":"string"}},"returns":{"allowed":"boolean","reason":"string","policy_message":"string"}}'::jsonb,
    true
  ),
  (
    'answer_from_document',
    'Answer From Document',
    'Responde à pergunta com base no markdown extraído.',
    '{"args":{"question":{"type":"string"},"markdown":{"type":"string"}},"returns":{"answer":"string"}}'::jsonb,
    true
  ),
  (
    'dispatch_handoff_webhook',
    'Dispatch Handoff Webhook',
    'Envia o payload do handoff ao CRM (POST) e registra evento.',
    '{"args":{"conversa_id":{"type":"string","format":"uuid"},"payload":{"type":"object"}},"returns":{"delivered":"boolean","status_code":"integer"}}'::jsonb,
    true
  )
on conflict (key) do update
set
  nome = excluded.nome,
  descricao = excluded.descricao,
  schema_json = excluded.schema_json,
  enabled_default = excluded.enabled_default;

-- Associações iniciais (allowlist por agente)
insert into public.ai_agent_tools (agent_key, tool_key, enabled)
values
  ('qa', 'get_company_config', true),
  ('qa', 'retrieve_documents', true),
  ('reengagement', 'get_company_config', true),
  ('reengagement', 'get_conversation_history', true),
  ('summarizer', 'get_conversation_history', true),
  ('document_guardrail', 'get_company_config', true),
  ('document_guardrail', 'document_relevance_check', true),
  ('document_qa', 'get_company_config', true),
  ('document_qa', 'answer_from_document', true),
  ('handoff_summary', 'get_company_config', true),
  ('handoff_summary', 'get_conversation_history', true),
  ('handoff_summary', 'dispatch_handoff_webhook', true)
on conflict (agent_key, tool_key) do update
set enabled = excluded.enabled;

-- Empresa (single-row) - opcional: cria uma linha inicial se ainda não existir nenhuma
insert into public.empresa_config (nome, descricao, contatos, policy_text, allowed_topics)
select
  'Minha Empresa',
  'Descrição curta da empresa e do atendimento.',
  '{}'::jsonb,
  'Esta IA responde apenas sobre a empresa e seus empreendimentos. Não use para assuntos pessoais ou fora do escopo.',
  '["empreendimentos","valores","visita","documentos","financiamento"]'::jsonb
where not exists (select 1 from public.empresa_config);
