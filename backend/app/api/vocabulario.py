"""GET /vocabulario — vocabulário controlado que o app usa no autocomplete.

Mesma fonte que o `POST /consulta` valida (`request.app.state.vocabulario`, carregado de
`etl/vocabulario/farmacos.yaml`, e `COMORBIDADES`/`ESPECIES` de `app/rag/composicao.py`),
para a lista do app nunca divergir do que o servidor aceita (docs/RAG_SPEC.md §7.1).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import exigir_api_key
from app.rag.composicao import COMORBIDADES, ESPECIES

router = APIRouter()


def montar_vocabulario(vocabulario: Any) -> dict[str, Any]:
    """Conteúdo do endpoint, com `versao` = hash do conteúdo (muda se qualquer item mudar)."""
    farmacos = []
    for termo in sorted(vocabulario.farmacos, key=lambda t: t.nome.casefold()):
        vistos = {termo.nome.casefold()}
        sinonimos = []
        for s in termo.sinonimos:
            if s.casefold() not in vistos:
                vistos.add(s.casefold())
                sinonimos.append(s)
        farmacos.append({"nome": termo.nome, "sinonimos": sinonimos})
    conteudo: dict[str, Any] = {
        "especies": list(ESPECIES),
        "farmacos": farmacos,
        "comorbidades": [{"chave": k, "rotulo": v} for k, v in COMORBIDADES.items()],
    }
    canonico = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    versao = hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:12]
    return {"versao": versao, **conteudo}


@router.get("/vocabulario", dependencies=[Depends(exigir_api_key)])
async def vocabulario(request: Request) -> dict[str, Any]:
    return montar_vocabulario(request.app.state.vocabulario)
