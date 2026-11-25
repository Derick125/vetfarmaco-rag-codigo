"""Testes de app/rag/retriever_lexical.py (docs/RAG_SPEC.md §3.2)."""

from app.rag.retriever_lexical import buscar, carregar_indice
from etl.bm25_index import construir_indice, salvar_indice

TEXTOS = [
    "O meloxicam é um fármaco anti-inflamatório não esteroidal usado em cães e gatos.",
    "A insuficiência renal crônica em felinos exige cautela com o uso de AINEs.",
    "O carprofeno é indicado para dor pós-operatória em cães saudáveis.",
]
CHUNK_IDS = ["c1", "c2", "c3"]


def test_carregar_indice_retorna_none_quando_diretorio_nao_existe(tmp_path):
    assert carregar_indice(tmp_path / "nao-existe") is None


def test_carregar_e_buscar_index_real_persistido(tmp_path):
    indice_construido = construir_indice(CHUNK_IDS, TEXTOS, k1=1.2, b=0.75)
    salvar_indice(indice_construido, tmp_path)

    indice = carregar_indice(tmp_path)
    assert indice is not None

    resultados = buscar(indice, "gatos com problema renal e uso de AINE", qtd=3)

    assert [chunk_id for chunk_id, _escore in resultados][0] == "c2"
    assert len(resultados) == 3


def test_buscar_respeita_qtd():
    indice = construir_indice(CHUNK_IDS, TEXTOS, k1=1.2, b=0.75)
    resultados = buscar(indice, "cães", qtd=1)
    assert len(resultados) == 1


def test_buscar_nao_estoura_quando_qtd_maior_que_o_corpus():
    indice = construir_indice(CHUNK_IDS, TEXTOS, k1=1.2, b=0.75)
    resultados = buscar(indice, "cães", qtd=1000)
    assert len(resultados) == len(CHUNK_IDS)


def test_escores_vem_em_ordem_decrescente():
    indice = construir_indice(CHUNK_IDS, TEXTOS, k1=1.2, b=0.75)
    resultados = buscar(indice, "cães gatos AINE renal meloxicam", qtd=3)
    escores = [escore for _chunk_id, escore in resultados]
    assert escores == sorted(escores, reverse=True)
