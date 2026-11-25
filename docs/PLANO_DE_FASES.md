# PLANO_DE_FASES.md — Ordem de execução

Mapeado ao Quadro 3 do TCC (cronograma 2026). Cada fase termina com um artefato
verificável. Não avance com testes vermelhos.

---

## Fase 0 — Fundação *(1–2 dias)*
Corresponde a: TCC etapa 2 (desenho da arquitetura).

- [x] `backend/` com FastAPI, `pydantic-settings`, `structlog`, `ruff`, `pytest`.
- [x] `app/` com Flutter 3.47, `very_good_analysis`, `get_it`, `go_router`.
- [x] Tokens e tema (`FRONTEND_SPEC.md` §17).
- [x] CI: lint, testes, cobertura ≥70% em `domain/` e `data/`, verificação da Regra de
      Dependência (`ARCHITECTURE.md` §2).
- [x] `.env.example` com `MODELO_ID`, `GEMINI_API_KEY`, `SUPABASE_URL`,
      `SUPABASE_SERVICE_KEY`, `APP_API_KEY`, `PRECO_IN_USD`, `PRECO_OUT_USD`.

**Pronto quando:** `flutter analyze`, `flutter test`, `ruff check`, `pytest` verdes; app
abre na tela de abertura.

---

## Fase 1 — Banco e ETL *(1 semana)*
Corresponde a: TCC etapa 3 (engenharia de dados).

- [x] Migrações de `DATABASE.md` aplicadas; índices criados.
- [x] `etl/extract.py` — PyMuPDF + pdfplumber sobre o PDF do Spinosa.
- [x] `etl/chunk.py` — janela de 512 tokens, sobreposição 64, nenhum chunk > 2048.
- [x] `etl/vocabulario/farmacos.yaml` — dicionário controlado de fármacos e espécies.
- [x] `etl/embed.py` — `gemini-embedding-001`, 1536 dims, `RETRIEVAL_DOCUMENT`, lote,
      normalização L2.
- [x] `etl/load.py` — carga idempotente por `texto_hash`, registro de `indice_versao`.
- [x] Índice BM25 persistido em `backend/data/bm25_index/`.

**Pronto quando:** `python -m etl.run` popula o banco e uma consulta manual a
`buscar_semantico` retorna trechos plausíveis sobre meloxicam em felinos.

---

## Fase 2 — Motor de recuperação *(1 semana)*
Corresponde a: TCC etapa 5 (RAG Híbrido).

- [x] `rag/retriever_vetorial.py` (top-30, `ef_search=100`, filtros por espécie/fármaco).
- [x] `rag/retriever_lexical.py` (`bm25s`, k1/b configuráveis, stemmer PT).
- [x] `rag/fusao.py` — RRF com **k=60**, com teste de unidade contra exemplo manual.
- [x] `eval/qrels.yaml` — gold set inicial das queries de referência (só 3 de exemplo,
      para fixar o formato — faltam as ≥30 rotuladas pelo autor, `CRITERIOS_DE_ACEITE.md`
      OE4). *Atualizado em 23/11/2026: 24 queries com resposta em `eval/qrels.yaml` e 6
      sem resposta em `eval/qrels_sem_resposta.yaml` (30 no total); commit `471baa8`.*
- [x] `eval/recall_at_k.py` — `ranx`, comparando híbrido × semântico × lexical.

**Pronto quando:** o Recall@10 do híbrido supera as duas estratégias isoladas no gold
set (critério do Quadro 1) — **pendente**: com as 3 queries de exemplo o híbrido ainda
não supera o semântico puro; só é decidível com o gold set completo (≥30 queries).
*Atualizado em 23/11/2026: decidido com o gold set real, nas 24 queries com resposta
(`backend/data/audit/recall_final.md`, 30/09/2026, `471baa8`): híbrido 0,8424, semântico
0,8208, lexical 0,7167. O híbrido supera as duas médias; os IC 95% das diferenças por
query incluem zero (ver `CRITERIOS_DE_ACEITE.md` OE4).*

---

## Fase 3 — Geração e validação de citações *(1 semana)*

- [x] `rag/roteador.py` — complexidade → `thinking_level` (`low`/`high`, explícito).
      *Evidência: tag `fase3-congelada` (`471baa8`); `backend/tests/test_roteador.py`.*
- [x] `rag/gerador.py` — `google-genai` async, streaming, `response_json_schema`.
      *Evidência: `471baa8`; prompt com 15 regras, iterações v1 a v4 em
      `docs/relatorio_metodologia.md`.*
- [x] Validação pós-geração completa (`RAG_SPEC.md` §7): citação fantasma, trecho
      literal, dose com lastro, coerência do alerta. *Evidência: `rag/validador.py`,
      `backend/tests/test_rag_validador.py`; tag `fase3-congelada` (`471baa8`).*
- [x] Endpoint `/consulta` com SSE (`sse-starlette`), autenticação `X-API-Key`; parágrafos
      só depois de validados, sem token bruto (`RAG_SPEC.md` §7.1).
- [x] Telemetria estruturada com `usage_metadata` e custo (primeiro token, primeiro
      parágrafo validado e total, separados; `thought_tokens` no custo).

**Pronto quando:** os seis cenários do Quadro 2 retornam respostas válidas com citações
verificadas, e uma resposta com `chunk_id` forjado é rejeitada por teste.
*Atualizado em 23/11/2026: os seis cenários foram executados em três rodadas da v4 com
validador ligado (`backend/data/audit/geracao/v4-r1..r3`); a rejeição de `chunk_id`
forjado é testada em `test_rag_validador.py::test_citacao_fantasma_descarta_a_resposta_inteira`
e em `test_rag_streaming.py`. Tags `fase3-congelada` (`471baa8`) e `fase3-concluida`
(`d4e65c4`). O conteúdo clínico dos cenários não foi comparado com
`comportamento_esperado_dado_corpus` (ver `relatorio_metodologia.md`).*

---

## Fase 4 — Cliente reduzido *(substitui as Fases 4, 5 e 6 originais)*
Corresponde a: TCC etapa 4 (desenvolvimento em Flutter).

> **Corte de escopo (decidido em 2026-10-02).** As antigas Fases 4 (núcleo e consulta),
> 5 (resposta e trilho) e 6 (histórico, ajustes e telemetria) foram fundidas em uma só
> fase, com escopo reduzido. **Motivo:** (1) o prazo da defesa não comporta de 3 a 5
> semanas de cliente completo; (2) o painel clínico (Fase 8) e a campanha de avaliação
> (Fase 7) **não dependem do app** — usam o back-end, o `eval/` e o Google Forms. O app
> permanece como artefato do OE2 (Clean Architecture, cache em `hive_ce`) e como
> instrumento de medição do OE5 (TTFT no cliente).
>
> **Entra:** termo de uso com aceite persistido (§8); nova consulta com campos
> estruturados, sanitização no cliente e `Ver o que será enviado` (§9); resposta em SSE
> com trilho de evidência, alerta no topo e rodapé com modelo e tempos (§10); folha de
> evidência (§11); cache e histórico simples em `hive_ce` com leitura offline;
> telemetria de cliente com exportação CSV; ajustes reduzidos ao endereço do back-end;
> `GET /vocabulario` no back-end.
>
> **Fica fora (adiado, não cancelado):** tela de ajustes completa (nível de raciocínio
> manual, tamanho/limpeza de cache, modo pesquisador, versões, reexibir termo); painel de
> telemetria com percentis e gráficos (a análise P50/P90/P99 sai do CSV, fora do app);
> golden tests em `textScaleFactor` 2.0 (e os golden de 380 px — a verificação visual
> fica com testes de widget).
>
> **Regras mantidas:** nenhuma chave do Gemini ou do Supabase no app; a chave do cliente
> (`X-API-Key`) e o endereço padrão do back-end entram por `--dart-define`; `domain/` sem
> import de framework; cobertura ≥ 70% em `domain/` e `data/`.

Cada etapa termina com `flutter analyze` e `flutter test` (e `pytest`/`ruff`, quando toca
o back-end) verdes **e** algo que se vê rodando. Não avance com teste vermelho.

- [x] **4.1 Configuração e termo (§8).** `AppConfig` lê `API_BASE_URL` e `CLIENT_API_KEY`
      de `--dart-define`; `TermoCubit` + caixa `hive_ce` com data/hora do aceite; botão
      habilitado só após rolar até o fim. *Vê-se:* primeira abertura leva ao termo; depois
      do aceite, reabrir vai direto para `/consulta` (ainda vazia).
- [x] **4.2 Ajustes mínimos.** Tela `/ajustes` só com o endereço do back-end (sobrepõe o
      `--dart-define`, persistido em `hive_ce`) e botão `Testar` que chama `/health`.
      *Vê-se:* trocar o endereço no aparelho e ver "back-end respondeu".
- [x] **4.3 Back-end: `GET /vocabulario`.** Serve os fármacos de `farmacos.yaml`, as
      comorbidades de `COMORBIDADES` (chave + rótulo) e as espécies, com `versao` (hash do
      conteúdo). Mesma fonte que o `POST /consulta` usa para validar, com teste de
      contrato: tudo que o endpoint devolve é aceito por `/consulta`. Exige `X-API-Key`.
      *Vê-se:* `curl` no endpoint local.
- [x] **4.4 Consulta: formulário estruturado (§9).** Espécie, peso, fármacos (chips +
      autocomplete) e comorbidades (toggles), todos alimentados pelo `/vocabulario`, com
      cópia em `hive_ce` para uso offline. Validação do §9. *Vê-se:* o formulário no
      aparelho com o vocabulário real do servidor.
- [x] **4.5 Consulta: pergunta, sanitização e `Ver o que será enviado`.** Campo de
      pergunta; `Sanitizador` (interface no domínio, implementação em `core/privacy/`);
      montagem do corpo exatamente como o `ConsultaRequest` (`complexidade_dica` incluída);
      expansor mostrando o JSON que sairá. *Vê-se:* digitar CPF e telefone sintéticos e ver
      os mascaramentos no expansor.
- [x] **4.6 Cliente SSE e resposta bruta.** `sse_parser` sobre `dio` (`ResponseType.stream`,
      `X-API-Key`), `RagRemoteSource`, `RagRepository.consultar`, `RealizarConsulta`,
      mapeamento para `Failure`; `RespostaBloc` com estados mínimos; tela
      `/consulta/:id` listando parágrafos em texto simples. *Vê-se:* uma consulta real
      aparecendo parágrafo a parágrafo.
- [x] **4.7 Trilho de evidência, alerta e rodapé (§10).** `TrilhoEvidencia`,
      `AncoraCitacao`, `BlocoAlerta`, `TrechoSerifado`; alerta promovido ao topo; rodapé
      com modelo, data e tempos; estados `Sem evidência` (sucesso, sem cor de falha),
      `Falha`, `FalhaCitacao` (descarta tudo) e tempo esgotado (mantém o parcial).
      Testes de widget, incluindo "dose em parágrafo sem `chunkIds` não é renderizada".
      *Vê-se:* resposta com trilho sólido/hachurado e um cenário `sem_evidencia`.
- [x] **4.8 Folha de evidência (§11).** `DraggableScrollableSheet` aberta pela âncora,
      com trecho literal em serifa, fonte, capítulo, página e `chunk_id`. *Vê-se:* tocar a
      âncora e abrir o trecho.
- [x] **4.9 Telemetria e CSV.** `TtftStopwatch` (primeiro evento × primeiro parágrafo com
      texto), `TelemetryRecorder` gravando por consulta em `hive_ce`: tempos de cliente,
      `fim.tempos`, `usage`, `custoUsd`, `modelo`, data, condição de rede, desfecho.
      Botão `Exportar CSV` (`share_plus`). *Vê-se:* o CSV compartilhado abre em planilha.
- [x] **4.10 Cache, histórico e offline.** `salvarEmCache`/`buscarEmCache`/`historico`
      sobre `hive_ce`; `/historico` (lista simples, remover, faixa offline); selo
      `Resposta armazenada em dd/MM · pode estar desatualizada`; estado `Offline sem
      cache`. *Vê-se:* modo avião — consulta repetida servida do cache com selo, consulta
      nova com o estado offline.
- [x] **4.11 Fechamento.** `check_domain_data_coverage.sh` ≥ 70%, CI verde, Regra de
      Dependência, varredura de chaves no app, roteiro manual do modo avião, critérios
      OE2/OE3/OE5 marcados em `CRITERIOS_DE_ACEITE.md`. *Feito em 2026-10-06: cobertura
      97,56%; `flutter analyze`, `flutter test` (170), `ruff` e `pytest` (268) verdes
      localmente; Regra de Dependência e varredura de chaves sem achados. **Pendente
      fora do código:** executar `docs/ROTEIRO_MODO_AVIAO.md` no aparelho e gravar o
      vídeo (fecha os dois itens de modo avião do OE2).* **Atualizado em 23/11/2026:** roteiro
      executado em 29/10/2026, passos 7 e 8 aprovados (commit `69ee3cb`, tag
      `fase4-concluida`, registro em `docs/ROTEIRO_MODO_AVIAO.md`); os dois itens de modo
      avião do OE2 estão fechados. O campo "Vídeo" do roteiro ainda não tem caminho.

**Pronto quando:** uma consulta sai do aparelho sanitizada, a resposta chega em SSE com
proveniência visível, a mesma consulta é servida offline pelo cache, e o CSV exportado
traz, por consulta, o tempo até o primeiro evento e o TTFT do contrato (primeiro
parágrafo validado), com versão do modelo e data.

---

## Fase 7 — Avaliação automatizada *(1 semana)*
Corresponde a: TCC etapa 7–8.

- [x] `eval/scenarios.yaml` — os seis cenários com comportamento esperado e página do
      Plumb's. *Evidência: `471baa8`.*
- [x] `eval/ragas_run.py` — `Faithfulness` e `ContextRelevance`, juiz Gemini.
      *Atualizado em 23/11/2026: feito no commit `0f21d11` (05/11/2026), mas o **juiz
      principal é o `claude-opus-5-5`** e o Gemini é o juiz de comparação; o texto
      original ("juiz Gemini") fica como registro da decisão inicial. Ver
      `relatorio_metodologia.md`, «Avaliação automatizada RAGAS (v4-r1)». Variabilidade
      do juiz medida em 06/11/2026 (`ba37d04`).*
- [x] Relatório de aprovação/reprovação por cenário nos limiares 0,80 / 0,75.
      *Evidência: `backend/data/audit/ragas/resultado.md` (3 aprovados, 3 reprovados) e
      `variabilidade.md`.*
- [ ] Campanha de telemetria: 6 cenários × 3 condições de rede × ~10 repetições.
      *Atualizado em 23/11/2026: ainda sem execução registrada. Há protocolo
      (`docs/PROTOCOLO_TELEMETRIA.md`) e back-end implantado no Cloud Run em 17/11/2026
      (`b21aa5b`); os CSVs da campanha não estão no repositório.*

**Pronto quando:** existe um relatório reproduzível com as métricas e o custo total
apurado.

---

## Fase 8 — Preparação do painel clínico *(paralelo à etapa 6 do TCC)*

> *Atualizado em 23/11/2026: itens desta fase ficam **desmarcados** a pedido do autor,
> até ele concluir a análise do painel. Material de preparação existente:
> `backend/data/audit/painel/conteudo_formulario.md` e `criar_formulario.gs` (commits
> `c51ddd0`, `7f5fc04`); regra de análise fixada em `b71910f`
> (`relatorio_metodologia.md`, «Regra de análise do painel»). O painel usa as seis
> situações; a decisão original de compilar só as aprovadas mudou, ver
> `CRITERIOS_DE_ACEITE.md` OE6.*

- [ ] Compilação das respostas aprovadas para avaliação cega.
- [ ] Formulário Google Forms com TCLE digital na primeira página e as quatro dimensões
      Likert (Fidelidade, Relevância do Contexto, Utilidade Clínica, Segurança Percebida).
- [ ] Planilha de tabulação com mediana por dimensão, Kappa/Alpha e taxa de discordância
      crítica.

**Pronto quando:** o protocolo está pronto para submissão ao CEP via Plataforma Brasil.

---

## Ordem de dependências

```
F0 ──► F1 ──► F2 ──► F3 ──► F7 ──► F8
        │             │
        └──► F4 ◄─────┘   (F4 = cliente reduzido; F8 não depende dele)
```

A Fase 4 consome o contrato SSE de `RAG_SPEC.md` §7.1 (já congelado) e o
`GET /vocabulario` (etapa 4.3). A Fase 8 depende só de F7: o painel clínico avalia
respostas compiladas pelo `eval/`, não o app.
