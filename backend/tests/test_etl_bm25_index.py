"""Testes de etl/bm25_index.py — construção, persistência e k1/b (docs/RAG_SPEC.md §3.2)."""

import json

import bm25s

from etl.bm25_index import construir_indice, salvar_indice, stemmer_rslp, stopwords_pt

TEXTOS = [
    "O meloxicam é um fármaco anti-inflamatório não esteroidal usado em cães e gatos.",
    "A insuficiência renal crônica em felinos exige cautela com o uso de AINEs.",
    "O carprofeno é indicado para dor pós-operatória em cães saudáveis.",
]
CHUNK_IDS = ["c1", "c2", "c3"]


def test_indice_persiste_k1_e_b_da_configuracao(tmp_path):
    indice = construir_indice(CHUNK_IDS, TEXTOS, k1=1.7, b=0.6)
    salvar_indice(indice, tmp_path)

    parametros = json.loads((tmp_path / "params.index.json").read_text(encoding="utf-8"))
    assert parametros["k1"] == 1.7
    assert parametros["b"] == 0.6


def test_indice_persiste_arquivos_esperados(tmp_path):
    indice = construir_indice(CHUNK_IDS, TEXTOS, k1=1.2, b=0.75)
    salvar_indice(indice, tmp_path)

    arquivos = {p.name for p in tmp_path.iterdir()}
    assert {"corpus.jsonl", "params.index.json", "vocab.index.json"} <= arquivos


def test_indice_persiste_o_chunk_id_de_cada_documento(tmp_path):
    indice = construir_indice(CHUNK_IDS, TEXTOS, k1=1.2, b=0.75)
    salvar_indice(indice, tmp_path)

    linhas = (tmp_path / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    chunk_ids_salvos = [json.loads(linha)["chunk_id"] for linha in linhas]
    assert chunk_ids_salvos == CHUNK_IDS


def test_stemmer_une_variacoes_da_mesma_palavra():
    """'inflamatório' e 'inflamatórios' devem casar — é o ponto do stemmer."""
    indice = construir_indice(
        ["a", "b"],
        ["Efeitos anti-inflamatórios relevantes.", "Nada relacionado ao tema aqui."],
        k1=1.2,
        b=0.75,
    )
    tokens_consulta = bm25s.tokenize(
        ["anti-inflamatório"],
        stopwords=stopwords_pt(),
        stemmer=stemmer_rslp(),
        show_progress=False,
    )
    documentos, escores = indice.retrieve(tokens_consulta, k=2, show_progress=False)

    assert documentos[0][0]["chunk_id"] == "a"
    assert escores[0][0] > escores[0][1]
