# Frontend Admin Leve (estático)

Interface simples em HTML/JS para cadastrar empreendimentos, mídias e documentos diretamente no Supabase. Útil para testes rápidos enquanto o backend/CRUD não está exposto.

## Como usar
1. Abrir `frontend/index.html` no navegador.
2. Preencher `SUPABASE_URL` e `SUPABASE_KEY` (use a anon key em ambiente de dev ou configure RLS/políticas para segurança).
3. Cadastrar:
   - Empreendimento (slug, nome, localização, preços, metragem, status, contato do corretor, diferenciais).
   - Mídia do empreendimento (tipo, tipologia, URL).
   - Documento/FAQ (tipo, título, conteúdo).

## Atenção
- Para produção, não exponha chaves sensíveis no frontend; prefira endpoints do backend com Auth.
- Este frontend não faz upload para o Storage; informe URLs já hospedadas (ex: Supabase Storage, CDN).
- IDs de empreendimento precisam ser copiados manualmente para vincular mídias.
