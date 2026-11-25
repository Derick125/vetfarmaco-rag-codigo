-- Índices de recuperação híbrida. docs/DATABASE.md §3.
--
-- Em sessões de consulta: `set local hnsw.ef_search = 100;` (default 40 —
-- 100 favorece recall, a métrica do Quadro 1 do TCC).

create index chunk_embedding_hnsw on chunk
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create index chunk_fts_gin      on chunk using gin (fts);
create index chunk_farmacos_gin on chunk using gin (farmacos);
create index chunk_especies_gin on chunk using gin (especies);
