"""Avaliação RAGAS (Faithfulness, ContextRelevance) das respostas validadas da rodada v4-r1.

Não gera respostas novas e não toca no sistema congelado: lê os JSONs já gravados em
`data/audit/geracao/v4-r1/`, reconstrói os trechos exatamente como foram enviados ao
modelo (blocos `<trecho>` do campo `prompt`) e os submete a dois juízes — Claude
(principal) e Gemini (comparação).

Dependências (ragas, anthropic) vivem em `.venv-eval`, fora do `pyproject.toml`:

    .venv-eval/Scripts/python -m eval.ragas_run              # só estima o custo (sem chamadas)
    .venv-eval/Scripts/python -m eval.ragas_run --executar   # roda os juízes e grava os resultados
    .venv-eval/Scripts/python -m eval.ragas_run --painel     # só regera o formulário, com os 6 cenários (sem chamadas)

Saídas: `data/audit/ragas/resultado.json`, `resultado.md` e
`data/audit/painel/conteudo_formulario.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
RODADA = "v4-r1"
DIR_RODADA = BACKEND / "data" / "audit" / "geracao" / RODADA
DIR_RAGAS = BACKEND / "data" / "audit" / "ragas"
DIR_PAINEL = BACKEND / "data" / "audit" / "painel"
CENARIOS = BACKEND / "eval" / "scenarios.yaml"

LIMIAR_FAITHFULNESS = 0.80
LIMIAR_CONTEXT_RELEVANCE = 0.75

# Preços USD por 1M de tokens. Claude: tabela da API (claude-opus-5-5). Gemini: os valores
# de PRECO_IN_USD / PRECO_OUT_USD do .env, que são os do modelo configurado em MODELO_ID.
CLAUDE_MODELO = "claude-opus-5-5"
CLAUDE_PRECO = (4.00, 20.00)
CLAUDE_MAX_TOKENS = 8000  # inclui o raciocínio adaptativo, que não pode ser desligado

# Chamadas por cenário e juiz: Faithfulness = 2 (extrair afirmações; veredito contra o
# contexto), ContextRelevance = 2 (dois prompts de juiz, ambos com o contexto inteiro).
CHAMADAS_COM_CONTEXTO = 3
CHAMADAS_SEM_CONTEXTO = 1
# Estimativas de saída por chamada, em tokens (sem raciocínio / raciocínio do Claude).
SAIDA_POR_CHAMADA = {"faith_afirmacoes": 250, "faith_veredito": 900, "relevancia": 10}
RACIOCINIO_CLAUDE_POR_CHAMADA = 1500  # teto conservador; effort=low costuma ficar abaixo
TOKENS_POR_CARACTERE = 1 / 3.0  # português com acentos/tabelas: ~3 caracteres por token
OVERHEAD_PROMPT_RAGAS = 700  # instruções + exemplos few-shot das métricas, por chamada


@dataclass
class Cenario:
    id: str
    pergunta: str
    resposta: str
    contextos: list[str]
    dados: dict = field(repr=False)


def _texto_resposta(validada: dict) -> str:
    """Resposta validada em texto corrido: parágrafos e, ao final, o alerta de segurança."""
    partes = [p["texto"].strip() for p in validada.get("paragrafos", [])]
    alerta = validada.get("alerta_seguranca")
    if alerta and alerta.get("texto"):
        partes.append(alerta["texto"].strip())
    return "\n\n".join(partes)


def _trechos_do_prompt(prompt: str) -> list[str]:
    """Corpo de cada `<trecho>` do prompt, na ordem em que o modelo os recebeu."""
    blocos = re.findall(r"<trecho [^>]*>\n(.*?)\n</trecho>", prompt, re.S)
    return [b.strip() for b in blocos]


def carregar_cenarios() -> list[Cenario]:
    ids = [c["id"] for c in yaml.safe_load(CENARIOS.read_text(encoding="utf-8"))["cenarios"]]
    saida = []
    for cid in ids:
        dados = json.loads((DIR_RODADA / f"{cid}.json").read_text(encoding="utf-8"))
        trechos = _trechos_do_prompt(dados["prompt"])
        enviados = [t["chunk_id"] for t in dados["trechos_enviados"]]
        if len(trechos) != len(enviados):
            raise SystemExit(f"{cid}: {len(trechos)} blocos no prompt, {len(enviados)} enviados")
        saida.append(
            Cenario(
                id=cid,
                pergunta=dados["pergunta"],
                resposta=_texto_resposta(dados["resposta_validada"]),
                contextos=trechos,
                dados=dados,
            )
        )
    return saida


# --------------------------------------------------------------------------- custo


def _tokens(texto: str) -> int:
    return math.ceil(len(texto) * TOKENS_POR_CARACTERE)


def estimar_custo(cenarios: list[Cenario], preco_gemini: tuple[float, float]) -> dict:
    """Estimativa por juiz; é um teto aproximado (a contagem real vem do `usage`)."""
    ent_c = sai_c = 0
    for c in cenarios:
        ctx = sum(_tokens(t) for t in c.contextos)
        resp = _tokens(c.resposta)
        q = _tokens(c.pergunta)
        # Faithfulness: afirmações (pergunta+resposta) e veredito (contexto+afirmações).
        ent_c += OVERHEAD_PROMPT_RAGAS + q + resp
        ent_c += OVERHEAD_PROMPT_RAGAS + ctx + resp
        # ContextRelevance: dois juízes, contexto inteiro.
        ent_c += 2 * (OVERHEAD_PROMPT_RAGAS + ctx + q)
        sai_c += (
            SAIDA_POR_CHAMADA["faith_afirmacoes"]
            + SAIDA_POR_CHAMADA["faith_veredito"]
            + 2 * SAIDA_POR_CHAMADA["relevancia"]
        )
    chamadas = len(cenarios) * 4
    sai_claude = sai_c + chamadas * RACIOCINIO_CLAUDE_POR_CHAMADA
    return {
        "chamadas_por_juiz": chamadas,
        "entrada_tokens": ent_c,
        "saida_tokens_sem_raciocinio": sai_c,
        "claude": {
            "modelo": CLAUDE_MODELO,
            "saida_tokens_com_raciocinio": sai_claude,
            "usd": ent_c * CLAUDE_PRECO[0] / 1e6 + sai_claude * CLAUDE_PRECO[1] / 1e6,
        },
        "gemini": {
            "modelo": os.environ["MODELO_ID"],
            "saida_tokens_com_raciocinio": sai_c,
            "usd": ent_c * preco_gemini[0] / 1e6 + sai_c * preco_gemini[1] / 1e6,
        },
    }


# --------------------------------------------------------------------------- juízes


class _Juiz:
    """Base de um juiz compatível com `InstructorBaseRagasLLM` (contabiliza tokens)."""

    nome: str
    modelo: str

    def __init__(self) -> None:
        self.entrada = 0
        self.saida = 0
        self.chamadas = 0

    def generate(self, prompt, response_model):  # exigido pela ABC; só o async é usado
        return asyncio.run(self.agenerate(prompt, response_model))


def _criar_juiz_claude():
    import anthropic
    from ragas.llms.base import InstructorBaseRagasLLM

    class JuizClaude(_Juiz, InstructorBaseRagasLLM):
        nome = "claude"
        modelo = CLAUDE_MODELO

        def __init__(self) -> None:
            super().__init__()
            self.client = anthropic.AsyncAnthropic()

        async def agenerate(self, prompt, response_model):
            msg = await self.client.messages.create(
                model=self.modelo,
                max_tokens=CLAUDE_MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "low",
                    "format": {
                        "type": "json_schema",
                        "schema": anthropic.transform_schema(response_model),
                    },
                },
                messages=[{"role": "user", "content": prompt}],
            )
            self.chamadas += 1
            self.entrada += msg.usage.input_tokens
            self.saida += msg.usage.output_tokens
            if msg.stop_reason != "end_turn":
                raise RuntimeError(f"claude: stop_reason={msg.stop_reason}")
            texto = "".join(b.text for b in msg.content if b.type == "text")
            return response_model.model_validate_json(texto)

    return JuizClaude()


def _criar_juiz_gemini():
    from google import genai
    from google.genai import types
    from ragas.llms.base import InstructorBaseRagasLLM

    class JuizGemini(_Juiz, InstructorBaseRagasLLM):
        nome = "gemini"
        modelo = os.environ["MODELO_ID"]

        def __init__(self) -> None:
            super().__init__()
            self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        async def agenerate(self, prompt, response_model):
            resp = await self.client.aio.models.generate_content(
                model=self.modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=response_model,
                ),
            )
            u = resp.usage_metadata
            self.chamadas += 1
            self.entrada += u.prompt_token_count or 0
            self.saida += (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
            return response_model.model_validate_json(resp.text)

    return JuizGemini()


# --------------------------------------------------------------------------- execução


async def _avaliar(juiz: _Juiz, cenarios: list[Cenario]) -> dict[str, dict]:
    from ragas.metrics.collections import ContextRelevance, Faithfulness

    fidelidade = Faithfulness(llm=juiz)
    relevancia = ContextRelevance(llm=juiz)
    saida: dict[str, dict] = {}
    for c in cenarios:  # sequencial: poucas chamadas, e evita estourar limite de taxa
        f = await fidelidade.ascore(
            user_input=c.pergunta, response=c.resposta, retrieved_contexts=c.contextos
        )
        r = await relevancia.ascore(user_input=c.pergunta, retrieved_contexts=c.contextos)
        saida[c.id] = {"faithfulness": float(f.value), "context_relevance": float(r.value)}
        print(f"  [{juiz.nome}] {c.id}: F={f.value:.3f} CR={r.value:.3f}", flush=True)
    return saida


def _aprovado(esc: dict) -> bool:
    return (
        esc["faithfulness"] >= LIMIAR_FAITHFULNESS
        and esc["context_relevance"] >= LIMIAR_CONTEXT_RELEVANCE
    )


def montar_resultado(cenarios, claude: dict, gemini: dict, juizes: list[_Juiz]) -> dict:
    por_cenario = {}
    for c in cenarios:
        cl, ge = claude[c.id], gemini[c.id]
        por_cenario[c.id] = {
            "claude": cl,
            "gemini": ge,
            "diferenca_claude_menos_gemini": {
                k: cl[k] - ge[k] for k in ("faithfulness", "context_relevance")
            },
            "aprovado_juiz_principal": {
                "faithfulness": cl["faithfulness"] >= LIMIAR_FAITHFULNESS,
                "context_relevance": cl["context_relevance"] >= LIMIAR_CONTEXT_RELEVANCE,
                "ambos": _aprovado(cl),
            },
        }
    return {
        "rodada": RODADA,
        "executado_em": datetime.now(UTC).isoformat(),
        "limiares": {
            "faithfulness": LIMIAR_FAITHFULNESS,
            "context_relevance": LIMIAR_CONTEXT_RELEVANCE,
        },
        "juizes": {
            j.nome: {
                "modelo": j.modelo,
                "chamadas": j.chamadas,
                "tokens_entrada": j.entrada,
                "tokens_saida": j.saida,
            }
            for j in juizes
        },
        "cenarios": por_cenario,
    }


# --------------------------------------------------------------------------- relatórios


def _n(v: float) -> str:
    return "n/d" if math.isnan(v) else f"{v:.2f}".replace(".", ",")


def _d(v: float) -> str:
    return "n/d" if math.isnan(v) else f"{v:+.2f}".replace(".", ",")


def escrever_resultado_md(res: dict, preco_gemini: tuple[float, float]) -> Path:
    lim = res["limiares"]
    linhas = [
        f"# RAGAS — {res['rodada']}",
        "",
        f"Executado em {res['executado_em']}. Respostas validadas já gravadas; nenhuma resposta nova.",
        f"Contexto = trechos enviados ao modelo na rodada. Limiares: Faithfulness ≥ "
        f"{_n(lim['faithfulness'])}, ContextRelevance ≥ {_n(lim['context_relevance'])} "
        "(aprovação pelo juiz principal, Claude).",
        "",
        "| cenário | F Claude | F Gemini | Δ F | CR Claude | CR Gemini | Δ CR | F ≥ 0,80 | CR ≥ 0,75 | aprovado |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    sim = {True: "sim", False: "não"}
    for cid, e in res["cenarios"].items():
        a, d = e["aprovado_juiz_principal"], e["diferenca_claude_menos_gemini"]
        linhas.append(
            f"| `{cid}` | {_n(e['claude']['faithfulness'])} | {_n(e['gemini']['faithfulness'])} "
            f"| {_d(d['faithfulness'])} | {_n(e['claude']['context_relevance'])} "
            f"| {_n(e['gemini']['context_relevance'])} | {_d(d['context_relevance'])} "
            f"| {sim[a['faithfulness']]} | {sim[a['context_relevance']]} | **{sim[a['ambos']]}** |"
        )
    linhas += ["", "Δ = Claude − Gemini.", "", "## Juízes e custo real", ""]
    linhas += ["| juiz | modelo | chamadas | tokens in | tokens out | custo USD |", "|---|---|---|---|---|---|"]
    for nome, j in res["juizes"].items():
        p = CLAUDE_PRECO if nome == "claude" else preco_gemini
        usd = j["tokens_entrada"] * p[0] / 1e6 + j["tokens_saida"] * p[1] / 1e6
        linhas.append(
            f"| {nome} | `{j['modelo']}` | {j['chamadas']} | {j['tokens_entrada']} "
            f"| {j['tokens_saida']} | {usd:.2f} |".replace(f"| {usd:.2f} |", f"| {usd:.3f} |")
        )
    linhas += [
        "",
        "Observação: o juiz Gemini é o mesmo modelo que gerou as respostas "
        "(`MODELO_ID` do .env); a concordância dele não é independente.",
        "",
    ]
    DIR_RAGAS.mkdir(parents=True, exist_ok=True)
    caminho = DIR_RAGAS / "resultado.md"
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return caminho


def escrever_formulario(cenarios: list[Cenario]) -> Path:
    """Conteúdo dos seis cenários para o formulário, sem marcação de aprovação (cegamento)."""
    linhas = [f"# Conteúdo para o formulário ({RODADA})", ""]
    for n, c in enumerate(cenarios, 1):
        v = c.dados["resposta_validada"]
        alerta = (v.get("alerta_seguranca") or {}).get("texto", "").strip()
        linhas += [f"## Situação {n}", "", f"**Pergunta:** {c.pergunta}", ""]
        linhas += ["**Resposta do sistema:**", "", " ".join(p["texto"].strip() for p in v["paragrafos"]), ""]
        linhas += ["**Alerta de segurança:**", "", alerta or "(sem alerta)", ""]
        linhas += ["**Trechos citados:**", ""]
        for i, ct in enumerate(v["citacoes"], 1):
            linhas += [f"{i}. «{ct['trecho'].strip()}» — {ct['fonte']}, p. {ct['pagina']}"]
        linhas += [""]
    DIR_PAINEL.mkdir(parents=True, exist_ok=True)
    caminho = DIR_PAINEL / "conteudo_formulario.md"
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return caminho


# --------------------------------------------------------------------------- main


DIR_REPETICOES = DIR_RAGAS / "repeticoes"
_METRICAS = (("faithfulness", "F"), ("context_relevance", "CR"))


def _media_dp(valores: list[float]) -> tuple[float, float]:
    """Média e desvio-padrão amostral (n − 1); sem desvio com uma só execução."""
    validos = [v for v in valores if not math.isnan(v)]
    if not validos:
        return math.nan, math.nan
    dp = statistics.stdev(validos) if len(validos) > 1 else math.nan
    return statistics.fmean(validos), dp


def consolidar_variabilidade() -> Path:
    """Média e desvio-padrão por cenário e por métrica, em tabela separada.

    Reúne a execução de 05/11 (`resultado.json`, só lida) e as repetições em
    `repeticoes/execucao-N.json`. Não altera `resultado.md` nem `resultado.json`.
    """
    base = json.loads((DIR_RAGAS / "resultado.json").read_text(encoding="utf-8"))
    execucoes = [("05/11 (fixa)", base)]
    for arq in sorted(DIR_REPETICOES.glob("execucao-*.json")):
        r = json.loads(arq.read_text(encoding="utf-8"))
        execucoes.append((r["executado_em"][:10] + f" ({arq.stem})", r))
    ids = list(base["cenarios"])
    consolidado: dict = {"n_execucoes": len(execucoes), "juizes": {}}
    linhas = [
        f"# RAGAS — variabilidade do juiz ({base['rodada']})",
        "",
        f"{len(execucoes)} execuções sobre as mesmas respostas validadas e os mesmos trechos: "
        "a de 05/11/2026 (`resultado.md`, **fixa**) e as repetições adicionais. "
        "Desvio-padrão amostral (n − 1). Esta tabela mede só a variabilidade do juiz: "
        "a classificação em aprovados e reprovados continua a da execução de 05/11 e "
        "não é alterada.",
        "",
    ]
    for juiz in ("claude", "gemini"):
        modelo = base["juizes"][juiz]["modelo"]
        linhas += [
            f"## Juiz {juiz} (`{modelo}`)",
            "",
            "| cenário | F média | F dp | F mín–máx | CR média | CR dp | CR mín–máx |",
            "|---|---|---|---|---|---|---|",
        ]
        consolidado["juizes"][juiz] = {}
        for cid in ids:
            linha = [f"`{cid}`"]
            consolidado["juizes"][juiz][cid] = {}
            for chave, sigla in _METRICAS:
                vals = [r["cenarios"][cid][juiz][chave] for _, r in execucoes]
                media, dp = _media_dp(vals)
                consolidado["juizes"][juiz][cid][chave] = {
                    "valores": vals,
                    "media": media,
                    "desvio_padrao": dp,
                }
                faixa = f"{_n(min(vals))}–{_n(max(vals))}"
                linha += [_n(media), _n(dp), faixa]
            linhas.append("| " + " | ".join(linha) + " |")
        linhas += ["", "Valores por execução (F / CR):", ""]
        linhas += ["| cenário | " + " | ".join(rot for rot, _ in execucoes) + " |"]
        linhas += ["|---|" + "---|" * len(execucoes)]
        for cid in ids:
            celulas = [
                f"{_n(r['cenarios'][cid][juiz]['faithfulness'])} / "
                f"{_n(r['cenarios'][cid][juiz]['context_relevance'])}"
                for _, r in execucoes
            ]
            linhas.append(f"| `{cid}` | " + " | ".join(celulas) + " |")
        linhas.append("")
    DIR_RAGAS.mkdir(parents=True, exist_ok=True)
    (DIR_RAGAS / "variabilidade.json").write_text(
        json.dumps(consolidado, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    caminho = DIR_RAGAS / "variabilidade.md"
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return caminho


def main() -> None:
    load_dotenv(BACKEND / ".env")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--executar", action="store_true", help="chama os juízes (gera custo)")
    ap.add_argument(
        "--repeticao",
        type=int,
        metavar="N",
        help="executa de novo e grava em repeticoes/execucao-N.json, sem tocar em resultado.*",
    )
    ap.add_argument(
        "--variabilidade",
        action="store_true",
        help="consolida média e desvio-padrão em variabilidade.md (sem chamadas)",
    )
    ap.add_argument("--painel", action="store_true", help="regera o formulário (sem chamadas)")
    args = ap.parse_args()

    preco_g = (float(os.environ["PRECO_IN_USD"]), float(os.environ["PRECO_OUT_USD"]))
    cenarios = carregar_cenarios()

    if args.painel:
        print(escrever_formulario(cenarios))
        return

    if args.variabilidade:
        print(consolidar_variabilidade())
        return

    if not args.executar and args.repeticao is None:
        est = estimar_custo(cenarios, preco_g)
        print(json.dumps(est, indent=2, ensure_ascii=False))
        print(f"\nTOTAL estimado (teto): US$ {est['claude']['usd'] + est['gemini']['usd']:.2f}")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY ausente do .env")
    if args.repeticao is None and (DIR_RAGAS / "resultado.json").exists():
        sys.exit(
            "resultado.json (execução de 05/11, fixa) já existe e não é sobrescrito; "
            "use --repeticao N para executar de novo."
        )
    juiz_claude, juiz_gemini = _criar_juiz_claude(), _criar_juiz_gemini()
    print("Claude (principal)…")
    claude = asyncio.run(_avaliar(juiz_claude, cenarios))
    print("Gemini (comparação)…")
    gemini = asyncio.run(_avaliar(juiz_gemini, cenarios))
    res = montar_resultado(cenarios, claude, gemini, [juiz_claude, juiz_gemini])
    if args.repeticao is not None:
        DIR_REPETICOES.mkdir(parents=True, exist_ok=True)
        alvo = DIR_REPETICOES / f"execucao-{args.repeticao}.json"
        alvo.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(alvo)
        return
    DIR_RAGAS.mkdir(parents=True, exist_ok=True)
    (DIR_RAGAS / "resultado.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(escrever_resultado_md(res, preco_g))
    print(escrever_formulario(cenarios))


if __name__ == "__main__":
    main()
