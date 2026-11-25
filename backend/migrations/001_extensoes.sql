-- Extensões necessárias para embeddings vetoriais e busca lexical.
-- docs/DATABASE.md §1.

create extension if not exists vector;
create extension if not exists pg_trgm;
