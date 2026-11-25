from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def _com_modelo(monkeypatch: pytest.MonkeyPatch, modelo_id: str | None) -> None:
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(modelo_id=modelo_id))


def test_health_returns_ok_e_modelo_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_modelo(monkeypatch, "modelo-teste-1")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "modelo_id": "modelo-teste-1"}


def test_health_sem_modelo_configurado_devolve_null(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_modelo(monkeypatch, None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "modelo_id": None}


def test_health_nao_exige_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # O app chama /health antes de qualquer consulta, só com o endereço.
    _com_modelo(monkeypatch, "m")

    assert client.get("/health").status_code == 200
