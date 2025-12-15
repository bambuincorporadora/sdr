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
  embedding vector,
  chunk text,
  ordem int
);
create index if not exists idx_documentos_embeddings_vec on documentos_embeddings using ivfflat (embedding vector_cosine_ops);

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
