# CRITERIOS_DE_ACEITE.md

Tradução direta do Quadro 1 do TCC (objetivos específicos e indicadores de sucesso) em
verificações executáveis. Marque cada item somente com evidência reproduzível.

## OE1 — Engenharia de dados e ETL
> *Indicador: pipeline capaz de converter o corpus textual em embeddings com fragmentação
> semântica e indexação em pgvector.*

- [ ] `python -m etl.run` executa ponta a ponta sem intervenção manual.
- [ ] Todo chunk tem `chunk_id`, `pagina`, `capitulo`, `farmacos`, `especies`, `tokens`.
- [ ] Nenhum chunk excede 2048 tokens; sobreposição de 64 tokens verificada por teste.
- [ ] Reexecução do ETL sobre o mesmo PDF não duplica linhas (`texto_hash`).
- [ ] `select count(*) from chunk where embedding is null` retorna 0.
- [ ] `indice_versao` gravado e exibido na tela de ajustes.

**Evidência:** log do ETL + consulta SQL de contagem.

## OE2 — Arquitetura de software (Flutter)
> *Indicador: interface desacoplada da API do Gemini, com cache local em Hive operacional
> para resiliência a interrupções de rede.*

- [x] Verificação da Regra de Dependência passa no CI (nenhum import de framework em
      `domain/`). *Job `regra-de-dependencia` em `ci.yml`; o mesmo `grep` rodado
      localmente em 2026-10-06 não achou violação (inclui `injectable`, `flutter_bloc`,
      `get_it`, `go_router`, `dart:io`, `dart:ui`).*
- [x] Nenhuma referência a `gemini` fora de `core/network/` e da configuração.
      *`grep -ri gemini app/lib` só acha um comentário em `core/config/app_config.dart`.*
- [x] Com o modo avião ligado, uma consulta já respondida é servida do `hive_ce` com o
      selo de data. *Coberto por teste automatizado
      (`test/features/historico/historico_test.dart`); falta executar
      `ROTEIRO_MODO_AVIAO.md` no aparelho (passo 7).* **Atualizado em 23/11/2026:** o
      passo 7 foi executado em 29/10/2026 (Xiaomi 22101320G, Android 14, modelo
      `gemini-3.8-flash`): selo de cache visível ao rolar. Registro em
      `ROTEIRO_MODO_AVIAO.md` (commit `69ee3cb`, tag `fase4-concluida`). O campo "Vídeo"
      desse roteiro continua `_caminho/link_`: a gravação ainda não está referenciada.
- [x] Com o modo avião ligado, uma consulta nova exibe o estado offline sem travar.
      *Idem: teste automatizado verde; falta o passo 8 do roteiro no aparelho.*
      **Atualizado em 23/11/2026:** o passo 8 foi executado em 29/10/2026, no mesmo
      registro (`69ee3cb`): a consulta nova mostrou `Sem conexão` sem travar.
- [x] Trocar `MODELO_ID` no back-end não exige nenhuma alteração no app.
      *O app não conhece o identificador do modelo: lê `modelo` do evento `fim`.*

**Evidência:** execução do CI + roteiro de teste manual gravado.

## OE3 — Avaliação de sistemas e robustez
> *Indicador: conformidade com os princípios da Clean Architecture e cobertura mínima de
> 70% nos testes unitários das camadas de domínio e dados.*

- [x] `flutter test --coverage` ≥ **70%** em `lib/features/*/domain/` e
      `lib/features/*/data/`. *97,56% (519/532 linhas) em 2026-10-06, com
      `tool/check_domain_data_coverage.sh`.* **Atualizado em 23/11/2026:** `flutter test
      --coverage` (325 testes, todos aprovados) deu **domain 94,2%** (292/310 linhas) e
      **data 99,3%** (282/284), calculados do `lcov.info`; domain e data juntos somam
      96,6% (574/594, conta feita na ocasião). O valor de 06/10 fica como registro da
      medição anterior. Limitação: 15 dos 106 arquivos de `lib/` não aparecem no
      `lcov.info` (nenhum teste os importa). Evidência e método em
      `docs/evidencias_oe2_oe3.md` §1.
- [x] `pytest --cov` ≥ 70% em `backend/app/rag/` e `backend/app/domain/`. *`app/rag/`:
      91% (650 instruções, 60 sem cobertura; `gerador.py` é o menor, 53%), medido em
      2026-10-06 com `pytest --cov=app/rag` (270 testes). `backend/app/domain/` não
      existe: a lógica de domínio do back-end vive em `app/rag/`.*
- [ ] Cada caso de uso do domínio tem teste de caminho feliz e de falha. *Parcial: a
      cobertura de linhas é alta, mas não há auditoria caso a caso (ex.: `ObterVocabulario`
      e `RealizarConsulta` são repasses ao repositório, testados via repositório).*
- [ ] Cada BLoC tem `bloc_test` cobrindo sucesso, falha de rede e `semEvidencia`.
      *Parcial: o projeto usa Cubit; `RespostaCubit` cobre sucesso, falha de rede e
      `semEvidencia`, os demais cobrem seus próprios estados, mas sem a tríade.*

**Evidência:** relatório `lcov.info` e saída do `pytest --cov`.

## OE4 — Sistemas de recuperação (RAG)
> *Indicador: ganho mensurável de Recall@10 no RAG Híbrido em relação às estratégias
> puramente semântica ou puramente lexical.*

- [x] Gold set com no mínimo 30 queries clínicas rotuladas em `eval/qrels.yaml` (3 de
      exemplo preenchidas, formato documentado no cabeçalho do arquivo — faltam 27+,
      rotuladas pelo autor). **Atualizado em 23/11/2026:** o gold set real tem **30
      queries**, divididas em **24 com resposta** (`eval/qrels.yaml`, base do Recall@10)
      e **6 sem resposta** (`eval/qrels_sem_resposta.yaml`, fora do Recall@10; mede
      `sem_evidencia`, ver `RAG_SPEC.md` §9). O critério dizia "30 em `qrels.yaml`"; a
      divisão 24 + 6 é o que está registrado em `RAG_SPEC.md` §9 e no cabeçalho do
      `qrels.yaml`. O Recall@10 é calculado sobre as 24.
- [x] `python -m eval.recall_at_k` reporta as três estratégias na mesma execução.
- [x] `Recall@10(híbrido) > Recall@10(semântico)` **e** `> Recall@10(lexical)` (não
      verificável com só 3 queries de exemplo — nas 3 atuais o híbrido não supera o
      semântico puro; depende do gold set completo). **Atualizado em 23/11/2026:**
      medido nas 24 queries com resposta (`backend/data/audit/recall_final.md`, gerado em
      30/09/2026, commit `471baa8`): **híbrido 0,8424**, **semântico 0,8208**, **lexical
      0,7167**. **Atendido no valor pontual (o híbrido teve o maior Recall@10); as
      diferenças não são estatisticamente significativas (os IC 95% incluem zero).**
      Detalhe registrado no mesmo arquivo: por query, o híbrido vence/empata/perde 3/20/1
      contra o semântico e 7/13/4 contra o lexical; IC 95% por bootstrap pareado: Δ
      semântico +0,0215 [−0,0035; +0,0500], Δ lexical +0,1257 [−0,0111; +0,2750].
- [x] RRF implementado com `k=60`, com teste de unidade contra cálculo manual
      (`backend/tests/test_rag_fusao.py`).

**Evidência:** tabela de resultados com data e `indice_versao`.

## OE5 — Métricas de performance
> *Indicador: TTFT inferior a 2 segundos sob rede 4G/5G, reportado em conjunto com o tempo
> até o primeiro evento de stream, e custo por consulta compatível com a operação clínica.*

> **Leitura adotada (`DIVERGENCIAS.md` §10):** o cliente nunca recebe token bruto do
> modelo (`RAG_SPEC.md` §7.1), então o "TTFT" do indicador é medido como o tempo até o
> **primeiro parágrafo validado** (`ttftMs` no cliente; `ms_ate_primeiro_paragrafo_validado`
> no servidor). O limiar de 2 s vale para essa medida.

- [x] Três tempos medidos e registrados **separadamente**, em toda consulta *(app:
      `TtftStopwatch` + `RegistrarTelemetria`; CSV com `primeiro_evento_ms`, `ttft_ms` e
      `primeiro_token_servidor_ms`; a campanha ainda não foi executada)*: tempo até o
      primeiro evento de stream, tempo até o primeiro token do modelo (servidor) e tempo
      até o primeiro parágrafo validado (**o TTFT do critério**).
- [ ] **Custo de latência da validação** registrado: tempo até o primeiro parágrafo
      validado menos tempo até o primeiro token do modelo, por consulta, com P50, P90 e
      P99. É o que a validação acrescenta à espera; não é medido contra o limiar.
- [ ] Campanha com as três condições de rede (Wi-Fi, 4G, 5G) concluída.
- [ ] **P50 do tempo até o primeiro parágrafo validado < 2 000 ms em 4G e 5G.** Consultas
      sem nenhum parágrafo validado (`sem_evidencia`, erro) não têm esse tempo: ficam
      fora do P50, e a campanha reporta quantas foram.
- [ ] P90 e P99 reportados, ainda que acima do limiar, para as três medidas.
- [ ] Custo por consulta calculado incluindo `thought_tokens` no lado da saída.
- [ ] Custo total da campanha dentro da reserva de R$ 150,00 do TCC §6.
- [x] Toda medição carrega `modelo_versao` e data (TCC §4.7). *O modelo vem do evento
      `fim` e, se a consulta falha antes dele, de `GET /health` consultado no envio
      (`modelo_id`). Só fica vazio se o back-end não respondeu nem ao `/health`.
      Cada linha também traz `condicao_campanha` (Wi-Fi/4G/5G, escolhida em Ajustes).*

**Evidência:** CSV exportado do painel de telemetria + estatística descritiva.

## OE6 — Validação clínica e funcional
> *Indicador: concordância do painel clínico em escala Likert de cinco pontos, com índices
> de Faithfulness e Context Relevancy ambos ≥ 4,0.*

**Regra de análise do painel (atualizado em 23/11/2026).** A regra fixada em 05/11/2026,
antes de qualquer resposta do painel, está na seção «Regra de análise do painel (fixada
antes da coleta)» de `docs/relatorio_metodologia.md`: o painel usa as **6 situações**
(cenários do Quadro 2); o desfecho principal (mediana ≥ 4 nas quatro dimensões e nenhuma
nota ≤ 2 em Segurança Percebida) é calculado **só nas 3 situações aprovadas no RAGAS**
(`paracetamol-felino`, `ivermectina-mdr1`, `meloxicam-irc`), com o **Claude
(`claude-opus-5-5`) como juiz principal**; as 3 reprovadas (`fenobarbital-carprofeno`,
`tramadol-felino-vs-cao-renal`, `insulina-nph-extra-label`) entram numa análise
secundária. **O que mudou em relação aos itens abaixo:** a decisão original era excluir as
respostas reprovadas do painel (TCC §4.5b); a regra fixada as mantém no painel, fora do
desfecho principal. A decisão original continua escrita no item correspondente. Resultado
do RAGAS: `backend/data/audit/ragas/resultado.md` (05/11/2026); variabilidade do juiz em
`backend/data/audit/ragas/variabilidade.md` (06/11/2026), que não altera a classificação.
Nenhum item da camada humana está marcado: a análise do painel ainda não foi concluída.

**Camada automatizada (filtro):**
- [ ] `Faithfulness ≥ 0,80` em todos os cenários enviados ao painel. *Atualizado em
      23/11/2026: 3 de 6 cenários atingem os dois limiares (juiz principal, 05/11); os
      outros 3 não, e seguem para a análise secundária, não para o desfecho principal.*
- [ ] `ContextRelevance ≥ 0,75` idem.
- [ ] Respostas reprovadas documentadas e excluídas do painel.

**Camada humana:**
- [ ] 5 a 8 veterinários recrutados conforme os critérios de inclusão do TCC §4.3.1.
- [ ] Avaliação cega (sem acesso prévio aos trechos recuperados).
- [ ] Mediana ≥ 4 em cada uma das quatro dimensões.
- [ ] Kappa de Cohen ou Alpha de Krippendorff calculado.
- [ ] Zero notas ≤ 2 em Segurança Percebida (ausência de discordância crítica).

**Evidência:** exportação do Google Forms + planilha de tabulação com identificadores
pseudonimizados.

---

## Critérios adicionais de integridade da pesquisa

Não constam do Quadro 1, mas sustentam a validade do experimento.

- [ ] Nenhuma resposta com `chunk_id` inexistente chega ao usuário (teste com citação
      forjada).
- [ ] Nenhuma dose é exibida em parágrafo sem citação (teste de widget).
- [ ] O Plumb's **não** está indexado no corpus (verificação em `documento.referencia`).
- [ ] O back-end opera exclusivamente com chave de faturamento habilitado (TCC §4.6).
- [ ] Nenhum dado de tutor, animal ou prontuário aparece nos logs do servidor (inspeção
      por amostragem).
- [ ] O termo de uso clínico é exibido e aceito antes do primeiro uso, com registro de
      data.
