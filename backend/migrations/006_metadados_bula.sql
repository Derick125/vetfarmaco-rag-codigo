-- Estende `chunk` com metadados próprios de bula. docs/DATABASE.md §2.
--
-- A primeira carga real de bula (antes desta migração) reaproveitou
-- `capitulo` pra guardar a seção canônica (posologia, interações...) por
-- falta de coluna própria — um hack provisório documentado em
-- `scripts/carregar_corpus_completo.py`. Esta migração dá a `secao` sua
-- própria coluna e some com esse reaproveitamento: `capitulo` volta a
-- significar só "capítulo de livro", nulo em todo chunk de bula.
--
-- `origem` (humana|veterinaria) e `produto` (nome comercial do
-- ciclo/apresentação) vêm do manifesto (`data/bulas/manifesto.yaml`) e do
-- preview de bula (`etl/extract_bula.py`), nunca de casamento de texto —
-- mesma regra do resto do pipeline de bula. As três colunas ficam nulas
-- em chunk de livro (`tipo_fonte='livro'`), que não tem nenhum desses
-- conceitos.

alter table chunk add column secao   text;
alter table chunk add column origem  text;
alter table chunk add column produto text;

create index chunk_secao_idx  on chunk (secao);
create index chunk_origem_idx on chunk (origem);

-- Migra o que já foi carregado com o hack: copia `capitulo` (que ali
-- guardava a seção) para `secao`, e limpa `capitulo` desses chunks.
update chunk
set secao = capitulo, capitulo = null
where documento_id in (select id from documento where tipo_fonte = 'bula');
