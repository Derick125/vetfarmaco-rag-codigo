"""Validação pós-geração (docs/RAG_SPEC.md §7) — barreira contra interpolação paramétrica.

Checagens, nesta ordem:

1. **Citações reais** — todo `chunk_id` citado (parágrafos, `citacoes`,
   `alerta_seguranca`) pertence ao conjunto recuperado. Se não, a resposta
   inteira é descartada (`citacao_fantasma`).
2. **Trecho literal** — cada `trecho` citado aparece no texto do chunk
   (comparação normalizada). Um `trecho` com elipse `[...]` é dividido nela:
   cada fragmento precisa aparecer literalmente no mesmo chunk, na mesma
   ordem (o fragmento seguinte é procurado depois do fim do anterior).
   Divergência → rebaixa a confiança e substitui o `trecho` pelo texto real do
   chunk (a interface o exibe como citação do documento, então o que sai do
   validador é literal); o original descartado vai para `trechos_substituidos`.
3. **Dose com lastro** — parágrafo com dose por peso (`etl.dose.extrair_doses`,
   nunca redefinido aqui) exige `chunk_ids` não vazio e ocorrência do mesmo
   valor numérico em algum chunk citado. Falha → remove o parágrafo e rebaixa.
4. **Espécie com lastro** — avaliada **por frase**: uma frase que contenha dose
   e mencione uma espécie exige ao menos um chunk citado pelo parágrafo cujo
   texto ou metadado `especies` contenha essa espécie (cada espécie
   mencionada precisa do seu). Falha → remove o parágrafo e rebaixa. Existe
   porque o valor pode estar no chunk sem que o chunk diga de qual espécie ele
   é (tabela sem cabeçalho). Exceção: se a **própria frase** declara ausência
   ("não consta", "não foi possível"; "não há", "não existe" e "não existem" só
   valem se a mesma frase também citar "documentos" ou "trechos"), ela não é
   barrada por essa espécie; cada exceção aplicada é registrada em `excecoes`.
   Frases são
   separadas por `.`, `!`, `?`, `;` ou quebra de linha — o `;` separa, de modo
   que "a dose para gatos não consta; em gatos use 2 mg/kg" é barrada (a
   segunda frase tem dose, espécie e nenhuma declaração de ausência).
5. **Coerência do alerta** — `alerta_seguranca` exige `chunk_ids` não vazios;
   sem eles é removido e a confiança rebaixada.
6. **Interação com lastro** — se o texto do `alerta_seguranca` nomeia dois ou
   mais fármacos do dicionário, ao menos um dos chunks citados no alerta
   precisa mencionar todos eles. Se não, o texto do alerta vira um parágrafo
   iniciado por "Inferência não documentada:" (com os `chunk_ids` do alerta) e o
   alerta é esvaziado (removido). Não rebaixa a confiança — o risco inferido
   continua na resposta, só deixa de se apresentar como documentado — e é
   registrado em `alertas_movidos` e em `eventos`. Roda antes das checagens 3 e
   4, para o parágrafo movido também passar por dose e espécie com lastro.

"Rebaixar" desce um degrau (alta → media → baixa); `sem_evidencia` não muda.
Se a validação remove todos os parágrafos de uma resposta que tinha algum, o
resultado vira `sem_evidencia` — uma resposta sem conteúdo sustentado é, por
definição, sem evidência (RAG_SPEC.md §5, regra 2).
"""

from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.rag.gerador import Trecho
from etl.chunk import Vocabulario
from etl.dose import extrair_doses

logger = structlog.get_logger()

_DEGRAUS = ["alta", "media", "baixa"]
_NUMERO_INICIAL = re.compile(r"\d+(?:[.,]\d+)?")
# Fim de frase: pontuação seguida de espaço (não separa "2.5 mg" nem "0,25"), ou quebra de linha.
_SEPARADOR_FRASE = re.compile(r"(?<=[.!?;])\s+|\n+")
# Declaração de ausência na própria frase (já normalizada: sem acento, minúscula).
_PADRAO_DECLARA_AUSENCIA = re.compile(
    r"\bnao (?:consta|constam|constou|foi possivel|foram possiveis)\b"
)
# "não há", "não existe" e "não existem" são amplos demais sozinhos ("em gatos não há
# restrição; use 2 mg/kg"): só contam como declaração de ausência se a mesma frase também
# citar "documentos" ou "trechos".
_PADRAO_NAO_HA = re.compile(r"\bnao (?:ha|existe|existem)\b")
_PADRAO_FONTE_DA_AUSENCIA = re.compile(r"\b(?:documentos?|trechos?)\b")


def _declara_ausencia(frase: str) -> bool:
    normalizada = _normalizar(frase)
    if _PADRAO_DECLARA_AUSENCIA.search(normalizada):
        return True
    return bool(
        _PADRAO_NAO_HA.search(normalizada) and _PADRAO_FONTE_DA_AUSENCIA.search(normalizada)
    )


@dataclass
class ResultadoValidacao:
    resposta: dict[str, Any] | None
    descartada: bool = False
    nivel_original: str | None = None
    nivel_final: str | None = None
    paragrafos_removidos: list[dict[str, str]] = field(default_factory=list)
    eventos: list[str] = field(default_factory=list)
    # Frases com dose e espécie sem lastro que escaparam por declarar ausência.
    excecoes: list[dict[str, str]] = field(default_factory=list)
    # Alertas de segurança com ≥ 2 fármacos sem chunk que os mencione juntos,
    # movidos para um parágrafo "Inferência não documentada:".
    alertas_movidos: list[dict[str, Any]] = field(default_factory=list)
    # Citações cujo `trecho` não era literal: o trecho saiu substituído pelo texto real do
    # chunk e o original descartado fica aqui (`chunk_id`, `trecho_original`).
    trechos_substituidos: list[dict[str, str]] = field(default_factory=list)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().casefold()


def _rebaixar(nivel: str) -> str:
    if nivel not in _DEGRAUS:
        return nivel
    return _DEGRAUS[min(_DEGRAUS.index(nivel) + 1, len(_DEGRAUS) - 1)]


def _valor_ocorre(dose: str, texto_chunk: str) -> bool:
    """O valor numérico inicial da dose ("2,5" de "2,5 mg/kg") ocorre no texto
    do chunk como número inteiro (vírgula e ponto decimais equivalem)."""
    valor = _NUMERO_INICIAL.match(dose)
    if valor is None:
        return False
    padrao = re.escape(valor.group(0)).replace(r"\,", "[.,]").replace(r"\.", "[.,]")
    return re.search(rf"(?<![\d.,]){padrao}(?![\d]|[.,]\d)", texto_chunk) is not None


_ELIPSE = re.compile(r"\[(?:\.{3}|…)\]")


def _trecho_literal(trecho: str, texto_chunk: str) -> bool:
    """Cada fragmento de `trecho` (dividido em `[...]`) ocorre em `texto_chunk`, em
    ordem e sem sobreposição. Comparação normalizada (acento, caixa, espaços)."""
    chunk = _normalizar(texto_chunk)
    posicao = 0
    for fragmento in _ELIPSE.split(trecho):
        fragmento = _normalizar(fragmento)
        if not fragmento:
            continue
        achado = chunk.find(fragmento, posicao)
        if achado < 0:
            return False
        posicao = achado + len(fragmento)
    return True


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in _SEPARADOR_FRASE.split(texto) if f.strip()]


def _especies_mencionadas(texto: str, vocabulario: Vocabulario) -> list[str]:
    return sorted({t.nome for t in vocabulario.especies if t.padrao.search(texto)})


PREFIXO_INFERENCIA = "Inferência não documentada:"


def _farmacos_mencionados(texto: str, vocabulario: Vocabulario) -> list[str]:
    return sorted({t.nome for t in vocabulario.farmacos if t.padrao.search(texto)})


def _chunk_menciona_todos(trecho: Trecho, farmacos: list[str], vocabulario: Vocabulario) -> bool:
    presentes = {t.nome for t in vocabulario.farmacos if t.padrao.search(trecho.texto)}
    return set(farmacos) <= presentes


def _chunk_tem_especie(trecho: Trecho, especie: str, vocabulario: Vocabulario) -> bool:
    if especie in trecho.especies:
        return True
    return any(t.nome == especie and t.padrao.search(trecho.texto) for t in vocabulario.especies)


def validar_paragrafo(
    paragrafo: dict[str, Any],
    por_id: dict[str, Trecho],
    vocabulario: Vocabulario,
) -> tuple[str | None, list[dict[str, str]]]:
    """Checagens 3 e 4 sobre **um** parágrafo: `(motivo_da_remoção | None, exceções)`.

    Só olha o parágrafo e os chunks que ele cita, por isso pode rodar assim que o
    parágrafo fica completo no stream (`rag.streaming`) e dá o mesmo resultado que
    dentro de `validar`. Pressupõe que todo `chunk_id` do parágrafo está em `por_id`
    (checagem 1 — `chunk_ids_fantasmas`).
    """
    texto = paragrafo.get("texto", "")
    ids = paragrafo.get("chunk_ids", [])
    doses = extrair_doses(texto)
    if not doses:
        return None, []
    if not ids:
        return "dose_sem_chunk_ids", []
    if not all(any(_valor_ocorre(d, por_id[i].texto) for i in ids) for d in doses):
        return "dose_sem_lastro", []

    excecoes: list[dict[str, str]] = []
    for frase in _frases(texto):
        if not extrair_doses(frase):
            continue
        for especie in _especies_mencionadas(frase, vocabulario):
            if any(_chunk_tem_especie(por_id[i], especie, vocabulario) for i in ids):
                continue
            if _declara_ausencia(frase):
                excecoes.append(
                    {
                        "frase": frase,
                        "especie": especie,
                        "motivo": "a própria frase declara ausência",
                    }
                )
                continue
            return f"especie_sem_lastro: {especie}", []
    return None, excecoes


def chunk_ids_fantasmas(paragrafo: dict[str, Any], por_id: dict[str, Trecho]) -> list[str]:
    """Checagem 1 sobre um parágrafo: `chunk_id` citado que não foi recuperado."""
    return sorted(set(paragrafo.get("chunk_ids", [])) - por_id.keys())


def validar(
    resposta: dict[str, Any] | None,
    trechos: list[Trecho],
    vocabulario: Vocabulario,
) -> ResultadoValidacao:
    """Valida `resposta` contra os `trechos` efetivamente enviados ao modelo.

    Não altera `resposta`; o resultado traz uma cópia corrigida.
    """
    if resposta is None:
        return ResultadoValidacao(
            resposta=None, descartada=True, eventos=["resposta_nao_parseavel"]
        )

    por_id = {t.chunk_id: t for t in trechos}
    nivel_original = resposta.get("nivel_confianca")
    res = ResultadoValidacao(
        resposta=copy.deepcopy(resposta),
        nivel_original=nivel_original,
        nivel_final=nivel_original,
    )
    corrigida = res.resposta
    assert corrigida is not None

    def rebaixar(motivo: str) -> None:
        res.eventos.append(motivo)
        if res.nivel_final is not None:
            res.nivel_final = _rebaixar(res.nivel_final)
        logger.warning("validacao_rebaixou_confianca", motivo=motivo)

    # 1. Citações reais.
    citados: set[str] = set()
    for paragrafo in corrigida.get("paragrafos", []):
        citados.update(paragrafo.get("chunk_ids", []))
    for citacao in corrigida.get("citacoes", []):
        citados.add(citacao.get("chunk_id", ""))
    citados.update((corrigida.get("alerta_seguranca") or {}).get("chunk_ids", []))
    fantasmas = sorted(citados - por_id.keys())
    if fantasmas:
        res.descartada = True
        res.resposta = None
        res.eventos.append(f"citacao_fantasma: {', '.join(fantasmas)}")
        logger.error("citacao_fantasma", chunk_ids=fantasmas)
        return res

    # 2. Trecho literal.
    for citacao in corrigida.get("citacoes", []):
        chunk = por_id[citacao["chunk_id"]]
        if not _trecho_literal(citacao.get("trecho", ""), chunk.texto):
            res.trechos_substituidos.append(
                {"chunk_id": citacao["chunk_id"], "trecho_original": citacao.get("trecho", "")}
            )
            citacao["trecho"] = chunk.texto
            rebaixar(f"trecho_nao_literal: {citacao['chunk_id']}")

    # 6 (antes de 3 e 4). Interação com lastro: alerta que nomeia ≥ 2 fármacos.
    alerta = corrigida.get("alerta_seguranca")
    if alerta is not None:
        farmacos_do_alerta = _farmacos_mencionados(alerta.get("texto", ""), vocabulario)
        ids_do_alerta = alerta.get("chunk_ids", [])
        if len(farmacos_do_alerta) >= 2 and not any(
            _chunk_menciona_todos(por_id[i], farmacos_do_alerta, vocabulario) for i in ids_do_alerta
        ):
            corrigida.setdefault("paragrafos", []).append(
                {
                    "texto": f"{PREFIXO_INFERENCIA} {alerta['texto']}",
                    "chunk_ids": list(ids_do_alerta),
                }
            )
            del corrigida["alerta_seguranca"]
            res.alertas_movidos.append(
                {
                    "texto": alerta["texto"],
                    "farmacos": farmacos_do_alerta,
                    "chunk_ids": list(ids_do_alerta),
                    "severidade": alerta.get("severidade"),
                }
            )
            res.eventos.append(f"interacao_sem_lastro: {' + '.join(farmacos_do_alerta)}")
            logger.warning("interacao_sem_lastro", farmacos=farmacos_do_alerta)

    # 3 e 4. Dose com lastro e espécie com lastro, parágrafo a parágrafo.
    mantidos: list[dict[str, Any]] = []
    for paragrafo in corrigida.get("paragrafos", []):
        motivo, excecoes = validar_paragrafo(paragrafo, por_id, vocabulario)
        if motivo is None:
            res.excecoes.extend(excecoes)
            mantidos.append(paragrafo)
        else:
            res.paragrafos_removidos.append({"texto": paragrafo.get("texto", ""), "motivo": motivo})
            rebaixar(motivo)

    corrigida["paragrafos"] = mantidos
    if res.paragrafos_removidos and not mantidos:
        res.nivel_final = "sem_evidencia"
        res.eventos.append("todos_os_paragrafos_removidos")

    # 5. Coerência do alerta.
    alerta = corrigida.get("alerta_seguranca")
    if alerta is not None and not alerta.get("chunk_ids"):
        del corrigida["alerta_seguranca"]
        rebaixar("alerta_sem_chunk_ids")

    corrigida["nivel_confianca"] = res.nivel_final
    return res
