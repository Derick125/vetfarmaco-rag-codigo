-- Funções de recuperação. docs/DATABASE.md §4.
--
-- `buscar_semantico` é o retriever vetorial do RAG híbrido. O operador
-- `<=>` é distância de cosseno; a similaridade é `1 - distância`.
create or replace function buscar_semantico(
  consulta_embedding vector(1536),
  filtro_especies    text[] default null,
  filtro_farmacos    text[] default null,
  qtd                int    default 30
)
returns table (chunk_id text, texto text, similaridade float, pagina int, capitulo text)
language sql stable
as $$
  select c.chunk_id,
         c.texto,
         1 - (c.embedding <=> consulta_embedding) as similaridade,
         c.pagina,
         c.capitulo
  from chunk c
  where (filtro_especies is null or c.especies && filtro_especies)
    and (filtro_farmacos is null or c.farmacos && filtro_farmacos)
  order by c.embedding <=> consulta_embedding
  limit qtd;
$$;

-- `buscar_lexical` existe como sinal auxiliar e fallback. O BM25 canônico
-- do pipeline roda em `bm25s` no back-end (docs/RAG_SPEC.md §3.2), porque
-- `ts_rank_cd` não computa IDF verdadeiro.
create or replace function buscar_lexical(
  termos text,
  qtd    int default 30
)
returns table (chunk_id text, texto text, escore float)
language sql stable
as $$
  select c.chunk_id, c.texto,
         ts_rank_cd(c.fts, plainto_tsquery('portuguese', termos)) as escore
  from chunk c
  where c.fts @@ plainto_tsquery('portuguese', termos)
  order by escore desc
  limit qtd;
$$;
