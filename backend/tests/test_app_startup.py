"""A inicialização do serviço não pode cair por causa do índice BM25
(docs/RAG_SPEC.md §3.2) — nem quando ele ainda não foi construído."""

from fastapi.testclient import TestClient

from app.main import app


def test_app_sobe_e_carrega_bm25_index_em_app_state():
    with TestClient(app) as client:
        resposta = client.get("/health")

        assert resposta.status_code == 200
        # Presente ou None (índice ainda não construído neste ambiente),
        # o que importa é que a chave existe e a subida não caiu.
        assert hasattr(client.app.state, "bm25_index")
