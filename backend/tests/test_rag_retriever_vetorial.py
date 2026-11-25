"""Testes de app/rag/retriever_vetorial.py (docs/RAG_SPEC.md §3.1).

Usa uma conexão Postgres falsa (sem rede, sem servidor real) — mesmo
padrão de `tests/test_etl_load.py`. Confirmado contra um Supabase real em
sessão manual: aqui o foco é a montagem da chamada (tipo do embedding,
`ef_search`, cast de `qtd`, repasse dos filtros), não o SQL em si.
"""

import contextlib

from pgvector import Vector

from app.rag.retriever_vetorial import EF_SEARCH, QTD_PADRAO, buscar


class _CursorFalso:
    def __init__(self, linhas):
        self._linhas = linhas

    def fetchall(self):
        return self._linhas


class _ConexaoFalsa:
    def __init__(self, linhas=()):
        self._linhas = linhas
        self.comandos: list[tuple[str, tuple | None]] = []

    def transaction(self):
        return contextlib.nullcontext()

    def execute(self, sql, params=None):
        sql_normalizado = " ".join(sql.split())
        self.comandos.append((sql_normalizado, params))
        if "buscar_semantico" in sql_normalizado:
            return _CursorFalso(self._linhas)
        return _CursorFalso([])


def _comando_da_busca(conexao):
    return next(c for c in conexao.comandos if "buscar_semantico" in c[0])


def test_buscar_devolve_pares_chunk_id_similaridade():
    conexao = _ConexaoFalsa([("c1", 0.9), ("c2", 0.5)])
    resultados = buscar(conexao, [0.1, 0.2, 0.3], qtd=5)
    assert resultados == [("c1", 0.9), ("c2", 0.5)]


def test_buscar_envolve_o_embedding_em_vector_nao_lista_comum():
    conexao = _ConexaoFalsa([])
    buscar(conexao, [0.1, 0.2, 0.3])
    _sql, params = _comando_da_busca(conexao)
    assert isinstance(params[0], Vector)


def test_buscar_seta_ef_search_na_sessao_antes_da_busca():
    conexao = _ConexaoFalsa([])
    buscar(conexao, [0.1])
    sql_set, _params = conexao.comandos[0]
    assert f"hnsw.ef_search = {EF_SEARCH}" in sql_set


def test_buscar_faz_cast_explicito_de_qtd_para_int():
    conexao = _ConexaoFalsa([])
    buscar(conexao, [0.1], qtd=7)
    sql, params = _comando_da_busca(conexao)
    assert "qtd => %s::int" in sql
    assert params[-1] == 7


def test_buscar_default_qtd_e_30():
    conexao = _ConexaoFalsa([])
    buscar(conexao, [0.1])
    _sql, params = _comando_da_busca(conexao)
    assert params[-1] == QTD_PADRAO == 30


def test_buscar_sem_filtro_passa_none_para_os_dois():
    conexao = _ConexaoFalsa([])
    buscar(conexao, [0.1])
    _sql, params = _comando_da_busca(conexao)
    assert params[1] is None
    assert params[2] is None


def test_buscar_repassa_filtros_de_especie_e_farmaco():
    conexao = _ConexaoFalsa([])
    buscar(conexao, [0.1], filtro_especies=["felino"], filtro_farmacos=["meloxicam"])
    _sql, params = _comando_da_busca(conexao)
    assert params[1] == ["felino"]
    assert params[2] == ["meloxicam"]
