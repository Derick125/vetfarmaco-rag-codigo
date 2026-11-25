"""Testes de etl/embed.py — lote e normalização L2 (docs/RAG_SPEC.md §2).

Usa um cliente Gemini falso (sem rede, sem custo) para testar lote, ordem
e normalização; não valida a resposta real da API.
"""

import math

import pytest
from google.genai import errors

from etl.embed import DIMENSOES, MODELO_EMBEDDING, _lotes, _normalizar_l2, gerar_embeddings


class _EmbeddingFalso:
    def __init__(self, values: list[float]):
        self.values = values


class _RespostaFalsa:
    def __init__(self, embeddings: list[_EmbeddingFalso]):
        self.embeddings = embeddings


class _ModelosFalsos:
    """Substitui `client.models` — grava as chamadas para inspeção nos testes."""

    def __init__(self, vetor_por_texto):
        self.chamadas: list[dict] = []
        self._vetor_por_texto = vetor_por_texto

    def embed_content(self, *, model, contents, config):
        contents = list(contents)
        self.chamadas.append({"model": model, "contents": contents, "config": config})
        return _RespostaFalsa([_EmbeddingFalso(self._vetor_por_texto(texto)) for texto in contents])


class _ClienteFalso:
    def __init__(self, vetor_por_texto):
        self.models = _ModelosFalsos(vetor_por_texto)


def test_normalizar_l2_produz_vetor_unitario():
    resultado = _normalizar_l2([3.0, 4.0])
    assert resultado == [0.6, 0.8]
    assert math.isclose(math.sqrt(sum(v * v for v in resultado)), 1.0)


def test_normalizar_l2_vetor_zero_nao_gera_divisao_por_zero():
    assert _normalizar_l2([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


def test_lotes_particiona_no_tamanho_pedido():
    assert _lotes(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]


def test_lotes_lista_vazia():
    assert _lotes([], 10) == []


def test_gerar_embeddings_faz_uma_chamada_por_lote():
    cliente = _ClienteFalso(vetor_por_texto=lambda _texto: [3.0, 4.0])

    resultado = gerar_embeddings(cliente, ["a", "b", "c"], tamanho_lote=2)

    assert len(cliente.models.chamadas) == 2  # 3 textos, lote de 2 => 2 chamadas
    assert [c["contents"] for c in cliente.models.chamadas] == [["a", "b"], ["c"]]
    assert resultado == [[0.6, 0.8], [0.6, 0.8], [0.6, 0.8]]


def test_gerar_embeddings_preserva_a_ordem_dos_textos():
    # cada texto gera um vetor distinto e identificável
    vetores = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [1.0, 1.0]}
    cliente = _ClienteFalso(vetor_por_texto=lambda texto: vetores[texto])

    resultado = gerar_embeddings(cliente, ["c", "a", "b"], tamanho_lote=10)

    assert resultado[0] == _normalizar_l2(vetores["c"])
    assert resultado[1] == _normalizar_l2(vetores["a"])
    assert resultado[2] == _normalizar_l2(vetores["b"])


def test_gerar_embeddings_usa_modelo_dimensao_e_task_type_corretos():
    cliente = _ClienteFalso(vetor_por_texto=lambda _texto: [1.0, 0.0])

    gerar_embeddings(cliente, ["a"], task_type="RETRIEVAL_QUERY")

    chamada = cliente.models.chamadas[0]
    assert chamada["model"] == MODELO_EMBEDDING
    assert chamada["config"].task_type == "RETRIEVAL_QUERY"
    assert chamada["config"].output_dimensionality == DIMENSOES


def test_gerar_embeddings_default_e_retrieval_document():
    cliente = _ClienteFalso(vetor_por_texto=lambda _texto: [1.0, 0.0])

    gerar_embeddings(cliente, ["a"])

    assert cliente.models.chamadas[0]["config"].task_type == "RETRIEVAL_DOCUMENT"


class _ModelosComFalhaTemporaria:
    """Simula estourar a cota (429) `n_falhas` vezes antes de responder."""

    def __init__(self, n_falhas: int, vetor_por_texto):
        self.n_falhas = n_falhas
        self.chamadas = 0
        self._vetor_por_texto = vetor_por_texto

    def embed_content(self, *, model, contents, config):
        self.chamadas += 1
        if self.chamadas <= self.n_falhas:
            raise errors.ClientError(429, {"error": {"message": "cota excedida"}})
        contents = list(contents)
        return _RespostaFalsa([_EmbeddingFalso(self._vetor_por_texto(t)) for t in contents])


class _ClienteComFalhaTemporaria:
    def __init__(self, n_falhas: int, vetor_por_texto):
        self.models = _ModelosComFalhaTemporaria(n_falhas, vetor_por_texto)


def test_gerar_embeddings_tenta_de_novo_apos_limite_de_taxa(monkeypatch):
    esperas: list[float] = []
    monkeypatch.setattr("etl.embed.time.sleep", lambda s: esperas.append(s))
    cliente = _ClienteComFalhaTemporaria(n_falhas=2, vetor_por_texto=lambda _t: [1.0, 0.0])

    resultado = gerar_embeddings(cliente, ["a"])

    assert resultado == [[1.0, 0.0]]
    assert cliente.models.chamadas == 3  # 2 falhas + 1 sucesso
    assert esperas == [20.0, 40.0]  # espera exponencial


def test_gerar_embeddings_desiste_apos_limite_de_tentativas(monkeypatch):
    monkeypatch.setattr("etl.embed.time.sleep", lambda _s: None)
    cliente = _ClienteComFalhaTemporaria(n_falhas=999, vetor_por_texto=lambda _t: [1.0, 0.0])

    with pytest.raises(errors.ClientError):
        gerar_embeddings(cliente, ["a"])


def test_gerar_embeddings_nao_tenta_de_novo_em_erro_que_nao_e_limite_de_taxa():
    class _ModelosComErroPermanente:
        def embed_content(self, *, model, contents, config):
            raise errors.ClientError(400, {"error": {"message": "requisição inválida"}})

    class _Cliente:
        models = _ModelosComErroPermanente()

    with pytest.raises(errors.ClientError):
        gerar_embeddings(_Cliente(), ["a"])
