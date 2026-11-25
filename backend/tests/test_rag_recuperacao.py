"""Testes de app/rag/recuperacao.py: o caminho paralelo devolve o mesmo que o sequencial."""

import threading
import time

import pytest

import app.rag.recuperacao as rec
from app.rag.gerador import Trecho

pytestmark = pytest.mark.anyio

SEMANTICOS = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
LEXICAIS = [("c", 5.0), ("d", 4.0), ("a", 3.0)]


@pytest.fixture
def anyio_backend():
    return "asyncio"


class ConexaoFalsa:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class PoolFalso:
    def __init__(self, atraso=0.0):
        self.atraso = atraso
        self.conn = ConexaoFalsa()
        self.devolvidas = []

    def getconn(self):
        time.sleep(self.atraso)
        return self.conn

    def putconn(self, conn):
        self.devolvidas.append(conn)


@pytest.fixture(autouse=True)
def retrievers_falsos(monkeypatch):
    chamadas = {"vetorial": [], "carga": []}

    def vetorial(conn, embedding, qtd=30, **kw):
        chamadas["vetorial"].append((conn, embedding, qtd, kw))
        return list(SEMANTICOS)

    def lexical(indice, pergunta, qtd=30):
        return list(LEXICAIS)

    def carregar(conn, ids):
        chamadas["carga"].append(list(ids))
        return [Trecho(chunk_id=i, texto=f"texto {i}", referencia="ref") for i in ids]

    monkeypatch.setattr(rec, "buscar_vetorial", vetorial)
    monkeypatch.setattr(rec, "buscar_lexical", lexical)
    monkeypatch.setattr(rec, "carregar_trechos", carregar)
    return chamadas


def _embedding(client, pergunta):
    return [0.1, 0.2]


async def test_paralelo_devolve_exatamente_o_mesmo_que_o_sequencial():
    pool = PoolFalso()
    sequencial = rec.recuperar(pool.conn, None, object(), "q", embedding_fn=_embedding)
    paralelo = await rec.recuperar_paralelo(pool, None, object(), "q", embedding_fn=_embedding)
    assert paralelo.semanticos == sequencial.semanticos == SEMANTICOS
    assert paralelo.lexicais == sequencial.lexicais == LEXICAIS
    assert paralelo.fundidos == sequencial.fundidos
    assert [t.chunk_id for t in paralelo.trechos] == [t.chunk_id for t in sequencial.trechos]


async def test_sem_filtro_de_especie_nem_de_farmaco(retrievers_falsos):
    await rec.recuperar_paralelo(PoolFalso(), None, object(), "q", embedding_fn=_embedding)
    _, embedding, qtd, kw = retrievers_falsos["vetorial"][0]
    assert qtd == rec.QTD_RETRIEVER == 30
    assert kw == {}  # nem filtro_especies nem filtro_farmacos
    assert len(retrievers_falsos["carga"][0]) <= rec.QTD_CONTEXTO


async def test_embedding_bm25_e_conexao_rodam_ao_mesmo_tempo(monkeypatch):
    # Cada etapa espera as outras duas: só termina se as três estiverem em andamento.
    barreira = threading.Barrier(3, timeout=5)

    def embedding(client, pergunta):
        barreira.wait()
        return [0.1]

    def lexical(indice, pergunta, qtd=30):
        barreira.wait()
        return list(LEXICAIS)

    class Pool(PoolFalso):
        def getconn(self):
            barreira.wait()
            return self.conn

    monkeypatch.setattr(rec, "buscar_lexical", lexical)
    resultado = await rec.recuperar_paralelo(Pool(), None, object(), "q", embedding_fn=embedding)
    assert resultado.trechos


async def test_conexao_e_encerrada_e_devolvida_ao_pool():
    pool = PoolFalso()
    await rec.recuperar_paralelo(pool, None, object(), "q", embedding_fn=_embedding)
    assert pool.devolvidas == [pool.conn]
    assert pool.conn.rollbacks == 1


async def test_falha_no_embedding_nao_vaza_a_conexao():
    pool = PoolFalso(atraso=0.05)

    def quebra(client, pergunta):
        raise RuntimeError("embedding fora")

    with pytest.raises(RuntimeError, match="embedding fora"):
        await rec.recuperar_paralelo(pool, None, object(), "q", embedding_fn=quebra)
    assert pool.devolvidas == [pool.conn]


async def test_tempos_de_cada_etapa_sao_registrados_separadamente():
    r = await rec.recuperar_paralelo(PoolFalso(), None, object(), "q", embedding_fn=_embedding)
    for campo in (
        "ms_embedding",
        "ms_busca_vetorial",
        "ms_busca_lexical",
        "ms_fusao",
        "ms_carga_trechos",
        "ms_conexao",
        "ms_total",
    ):
        assert getattr(r, campo) >= 0.0
    assert r.ms_total > 0


def test_cliente_gemini_e_reutilizado_por_chave():
    assert rec.obter_cliente("chave-1") is rec.obter_cliente("chave-1")
    assert rec.obter_cliente("chave-1") is not rec.obter_cliente("chave-2")
