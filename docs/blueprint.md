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

Indices recomendados: `idx_mensagens_conversa`, `idx_intencoes_mensagem`, `idx_qualificacao_conversa_pergunta`, `ivfflat_documentos_embeddings`.

## Frontend Admin (web)
- Objetivo: CRUD de empreendimentos, midias, documentos/FAQ; visualizacao de conversas e status de qualificacao/handoff.
- Requisitos principais:
  - Autenticacao/roles basica (ex: admin/operador).
  - Formulario de empreendimento (dados gerais, faixa de preco, metragem, status obra, diferenciais, contato do corretor).
  - Upload/gestao de midias (plantas, books) com tipologia e descricao; gravar URLs no Supabase Storage.
  - Gestao de documentos/FAQ por empreendimento para feeding de embeddings.
  - Visual de conversas: lista e detalhe com mensagens, intencao detectada, pendencias de qualificacao, proximas perguntas, reengajamentos agendados.
  - Acionamento manual: reenviar midia, forcar handoff, marcar conversa como encerrada.
- Stack sugerida: React ou Next.js + Supabase Auth; backend FastAPI ja exposto; usar endpoints REST (ou GraphQL se desejar) para CRUD.

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
  intencao = agente_intencao(texto)
  if intencao == pergunta: resposta = agente_QA(texto)
  elif intencao == seguir: resposta = prox_pergunta_qualificacao()
  elif intencao == encerrar: resposta = despedida()
  elif intencao == ruido: resposta = pedir_reformulacao()
  enviar_resposta(resposta)
  atualizar_estado_conversa()
  agendar_reengajamentos(conversa_id)  # 30min, 3h, 6h; cancelar se lead responder

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

## Consideracoes
- Evolucao do tom: variar abre/sim/nosso para soar humano.
- Limitar blocos grandes; sempre confirmar recepcao de audio ("recebi seu audio, ja transcrevendo") se demorar.
- Se dado nao existe: admitir e oferecer retorno com canal preferido.
- Logs: registrar tentativas de transcricao e de QA com confianca para revisao humana.
- Resumo e envio: respostas longas (especialmente QA) passam por sumarizador e sao quebradas em blocos de 200-400 tokens; enviar blocos em sequencia curta, priorizando fatos principais e oferta de ajuda no final.
