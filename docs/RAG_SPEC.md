# RAG_SPEC.md — Pipeline de RAG Híbrido

Implementa o TCC §3.3, §3.4, §4.1b e §4.6.

## 1. Corpus

| Fonte | Papel | Observação |
|---|---|---|
| Spinosa, Górniak & Bernardi (2017), *Farmacologia Aplicada à Medicina Veterinária*, 6ª ed. | corpus primário indexado | português — aproxima o idioma do acervo do idioma das consultas (TCC §4.1b) |
| Bulas oficiais (MAPA/fabricantes) | corpus complementar | texto primário, por fármaco |
| Plumb's Veterinary Drug Handbook (2008) | **NÃO indexar** | é a fonte de *validação*, mantida independente para evitar circularidade (TCC §4.4b) |

Manter o Plumb's fora do índice é requisito metodológico, não um detalhe. Indexá-lo
invalidaria a avaliação clínica.

## 2. ETL

```
PDF → extração → limpeza → segmentação → chunking → metadados → embeddings → carga
```

**Extração** (`etl/extract.py`): PyMuPDF, preservando número de página e cabeçalhos de
capítulo. Tabelas de dose extraídas com `pdfplumber` e serializadas em Markdown — uma
tabela de posologia nunca deve ser quebrada entre chunks.

**Limpeza:** remoção de cabeçalho/rodapé por posição na página, junção de hifenização de
fim de linha, normalização de unidades (`mg/kg`, `mg kg-1` → `mg/kg`), preservação de
vírgula decimal.

**Chunking** (`etl/chunk.py`): janela deslizante de **512 tokens com sobreposição de 64**,
conforme o paradigma de *sliding window with overlap* adotado no TCC §4.1b. A
sobreposição garante que advertência de contraindicação e descrição de interação, quando
dispersas em segmentos contíguos, sejam recuperáveis em conjunto. Se o Recall@10 ficar
abaixo do baseline, elevar a sobreposição para 128 antes de mexer em qualquer outro
parâmetro. Nenhum chunk pode exceder 2048 tokens (limite de entrada do modelo de
embeddings).

**Metadados obrigatórios por chunk:**

```json
{
  "chunk_id": "spinosa-c22-p574-003",
  "fonte": "Spinosa et al. (2017)",
  "tipo_fonte": "livro",
  "capitulo": "22 — Anti-inflamatórios não esteroidais",
  "pagina": 574,
  "farmacos": ["meloxicam"],
  "especies": ["felino", "canino"],
  "texto": "..."
}
```

`farmacos` e `especies` são extraídos por casamento contra um dicionário controlado
(`etl/vocabulario/farmacos.yaml`) e habilitam filtragem na recuperação.

**Embeddings** (`etl/embed.py`): `gemini-embedding-001`,
`task_type="RETRIEVAL_DOCUMENT"`, `output_dimensionality=1536`, em lote, com
normalização L2 manual (obrigatória quando a dimensão difere de 3072). Consultas usam
`RETRIEVAL_QUERY`.

**Idempotência:** cada chunk tem hash do texto; reprocessar o mesmo PDF não duplica
linhas. O ETL registra `indice_versao` (data + hash do corpus), exposto na tela de
ajustes do app.

## 3. Recuperação

### 3.1 Vetorial
Top-30 por similaridade de cosseno (`<=>`) via função SQL `buscar_semantico`
(ver `DATABASE.md` §4). `SET LOCAL hnsw.ef_search = 100` na sessão de consulta.

### 3.2 Lexical (BM25)
`bm25s` com `k1 = 1.2` e `b = 0.75` (valores iniciais; são hiperparâmetros ajustáveis,
TCC §4.2). Tokenização com remoção de stopwords em português e stemmer Snowball/RSLP.
Índice construído no ETL e persistido em `backend/data/bm25_index/`, carregado na
inicialização do serviço. Top-30.

O BM25 real roda na aplicação porque o PostgreSQL gerenciado não oferece BM25 nativo —
`ts_rank_cd` não computa IDF verdadeiro. Ver `DIVERGENCIAS.md` §2.

### 3.3 Fusão — RRF

```python
def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion (Cormack, Clarke & Büttcher, SIGIR 2009)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for posicao, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + posicao)
    return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))
```

`k = 60` é o valor do trabalho original e o do TCC. **Não** use 50 (valor do exemplo do
Supabase). Top-10 do resultado fundido compõe o contexto.

### 3.4 Injeção de bulas inteiras
Quando a consulta cita fármacos do dicionário, as bulas correspondentes são anexadas
**na íntegra**, além dos 10 chunks fundidos. É o uso deliberado da janela de 1.048.576
tokens que justifica a escolha da nuvem sobre inferência on-device (TCC §3.6).

### 3.5 Desempenho da recuperação (sem alterar o resultado)

`app/rag/recuperacao.py` tem duas formas com **o mesmo resultado**: `recuperar`
(sequencial, a referência) e `recuperar_paralelo` (a do endpoint). A segunda reutiliza
um pool de conexões e o cliente Gemini entre requisições e roda embedding, BM25 e a
retirada da conexão ao mesmo tempo; a busca vetorial (depende do embedding), a fusão e a
carga dos trechos seguem em sequência. Mesmos retrievers, `QTD_*` e `k`, e **sem filtro
de espécie nem de fármaco**.

Medido sobre as 30 queries do gold set (24 com resposta + 6 sem resposta; uma execução
cada; Supabase remoto), mediana em ms:

| etapa | sequencial (antes) | paralela (depois) |
|---|---|---|
| cliente Gemini + conexão ao banco | 1 055 (aberta a cada consulta) | 59 (retirada do pool, sobreposta ao embedding) |
| embedding | 519 | 404 |
| busca vetorial | 261 | 231 |
| BM25 | 4,5 | 4,1 |
| fusão RRF | 0,1 | 0,1 |
| carga dos trechos | 165 | 165 |
| **total** | **2 002** (P90 2 133) | **797** (P90 909) |

O ganho vem quase todo de não reabrir cliente e conexão (≈ 1,05 s por consulta); o
paralelismo adiciona pouco porque o BM25 custa ≈ 4 ms e o embedding segue no caminho
crítico. A diferença de embedding e de busca vetorial entre as colunas (≈ 100 e 30 ms) é
variação entre execuções, não efeito do código.

Equivalência (`scripts.verificar_equivalencia_recuperacao`, resultados em
`backend/data/audit/recuperacao/`): com o embedding fixo, os rankings semântico (top-30),
lexical (top-30) e fundido (top-10), com escores, e a ordem dos trechos foram idênticos
nas 30 queries; com embedding ao vivo, também nas 30.

## 4. Geração

```python
config = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
    thinking_config=types.ThinkingConfig(thinking_level=nivel),
    response_mime_type="application/json",
    response_json_schema=SCHEMA_RESPOSTA,
)
async for chunk in await client.aio.models.generate_content_stream(
    model=settings.modelo_id, contents=prompt, config=config
):
    ...
```

**Roteamento do `thinking_level`** (TCC §3.2d):

| Condição | Nível |
|---|---|
| ≥ 2 fármacos, ou comorbidade marcada, ou pergunta sobre interação | `high` |
| Pergunta posológica direta, 1 fármaco, sem comorbidade | `low` |

Defina o nível **sempre** de forma explícita: o default do modelo é `medium`. `minimal`
não é suportado — a deliberação interna não pode ser suprimida e compõe o piso da
latência medida (TCC §1.4 H2).

## 5. System instruction

```
Você é um assistente de consulta a literatura de farmacologia veterinária,
para cães e gatos.

REGRAS ABSOLUTAS
1. Responda usando EXCLUSIVAMENTE os trechos fornecidos em <contexto>.
2. Nunca use conhecimento próprio. Se os trechos não sustentarem a resposta,
   devolva nivel_confianca = "sem_evidencia" e deixe paragrafos vazio.
3. Nunca informe uma dose que não apareça literalmente nos trechos.
4. Cada parágrafo deve listar os chunk_id que o sustentam. Parágrafo sem
   chunk_id é proibido, salvo transição puramente conectiva.
5. Se houver contraindicação, toxicidade espécie-específica ou interação
   documentada nos trechos, preencha alerta_seguranca.
6. Não invente chunk_id. Use apenas os que aparecem em <contexto>.
7. Escreva em português do Brasil, para um médico veterinário. Sem saudações,
   sem hedging genérico, sem repetir a pergunta.
```

## 6. Schema da resposta

```json
{
  "type": "object",
  "required": ["paragrafos", "citacoes", "nivel_confianca"],
  "properties": {
    "paragrafos": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["texto", "chunk_ids"],
        "properties": {
          "texto": {"type": "string"},
          "chunk_ids": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "citacoes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["chunk_id", "trecho"],
        "properties": {
          "chunk_id": {"type": "string"},
          "trecho": {"type": "string"},
          "fonte": {"type": "string"},
          "pagina": {"type": "integer"}
        }
      }
    },
    "nivel_confianca": {"enum": ["alta", "media", "baixa", "sem_evidencia"]},
    "alerta_seguranca": {
      "type": "object",
      "properties": {
        "severidade": {"enum": ["contraindicacao", "cautela"]},
        "texto": {"type": "string"},
        "chunk_ids": {"type": "array", "items": {"type": "string"}}
      }
    }
  }
}
```

## 7. Validação pós-geração — obrigatória

Antes de emitir o evento `fim`, o back-end verifica (a emissão incremental dos
parágrafos durante o stream está em §7.1):

1. **Citações reais:** todo `chunk_id` citado pertence ao conjunto recuperado. Se não
   → descarta a resposta, registra `citacao_fantasma` e devolve erro. Sem exceções.
2. **Trecho literal:** cada `trecho` citado aparece no texto do chunk correspondente
   (comparação normalizada). Divergência → rebaixa `nivel_confianca` e loga.
3. **Dose com lastro:** todo padrão numérico de dose por peso corporal em um parágrafo
   exige `chunk_ids` não vazio **e** ocorrência do mesmo valor em algum chunk citado.
   Falha → remove o parágrafo e rebaixa a confiança. O padrão (`PADRAO_DOSE_POR_KG`,
   `extrair_doses`) vive em `backend/etl/dose.py` — compartilhado com
   `etl/auditar_previews.py`, nunca redefinido aqui nem em `rag/gerador.py`, para as
   duas pontas nunca divergirem. Cobre mg/ml/mcg/µg/μg/mEq/UI/ng/g, "mg de &lt;fármaco&gt;
   / kg", sufixo "/dia" e a notação de expoente "kg-1"/"kg–1" — ver o docstring do
   módulo e `backend/tests/test_etl_dose.py` para a lista de variantes reais do corpus.
4. **Coerência do alerta:** `alerta_seguranca` presente exige `chunk_ids` não vazios.

Esta é a barreira que separa recuperação genuína de interpolação paramétrica — a
implementação direta da mitigação da Falácia da Acurácia (TCC §1.3).

### 7.1 Streaming validado — endpoint `/consulta`

`POST /consulta` (`app/api/consulta.py`) responde por SSE (`sse-starlette`) e exige o
cabeçalho `X-API-Key` igual a `APP_API_KEY` (`app/api/deps.py`): 401 sem chave ou com
chave errada; **503** se `APP_API_KEY` não está configurada — o serviço nunca fica
aberto por falta de configuração.

Corpo (campos estruturados do FRONTEND_SPEC.md §9; o que não é `pergunta` é opcional):

| Campo | Regra | Uso |
|---|---|---|
| `pergunta` | texto livre já sanitizado no cliente, 3 a 4000 caracteres | recuperação e texto da consulta |
| `especie` | `canino` ou `felino` | só no texto da consulta |
| `peso_kg` | > 0 e ≤ 200 | só no texto da consulta |
| `farmacos` | até 10, **nomes do dicionário** (`etl/vocabulario/farmacos.yaml`, sem diferenciar caixa); fora dele → 422 | texto da consulta; o roteador os detecta |
| `comorbidades` | chaves do vocabulário controlado de `app/rag/composicao.py` (`insuficiencia_renal_cronica`, `hepatopatia`, `gestacao`, `epilepsia`, `raca_mdr1`); outra chave → 422 | texto da consulta; qualquer uma marca `comorbidade_marcada` no roteador (`thinking_level = high`) |
| `complexidade_dica` | `alta` ou `baixa` | roteador (`alta` nunca é rebaixada) |

Os campos estruturados são fechados (dicionário e vocabulário) para que texto livre, e
PII, só exista em `pergunta` (CLAUDE.md regra 3).

**Texto da consulta.** `compor_consulta` monta, só com as linhas presentes e nesta ordem,
`Espécie: …`, `Peso: … kg.` (vírgula decimal), `Fármacos em questão: …` e
`Condições relevantes: …`, uma linha em branco e `Pergunta: <pergunta>`. Sem nenhum campo
estruturado, o texto é a `pergunta` intacta. Esse texto vai ao roteador e ao modelo.

**A recuperação não muda.** Ela recebe só `pergunta`, **sem filtro de espécie** (nem de
fármaco) e sem o texto composto: é a recuperação avaliada na Fase 2, e filtrar ou
reescrever a consulta de busca alteraria o sistema congelado. A espécie da requisição só
chega ao modelo, pelo texto; o validador (§7, checagem 4) continua olhando as espécies
que a própria resposta menciona, não a da requisição.

**Nenhum token bruto do modelo chega ao cliente.** O back-end acumula o JSON em
streaming (`app/rag/streaming.py`) e só emite objetos completos que já passaram pelo
validador:

| Evento | Quando sai | Carga |
|---|---|---|
| `recuperacao` | fim da busca híbrida, antes de chamar o modelo | `{chunks, ms, thinkingLevel}` |
| `paragrafo` | o objeto do parágrafo fechou no JSON **e** passou nas checagens 1, 3 e 4 (citação real, dose e espécie com lastro — as que dependem só do parágrafo) | `{indice, texto, chunkIds}` |
| `citacoes` | depois do stream inteiro e do `validar` completo | `{citacoes: [{chunkId, indice, trecho, fonte, capitulo, pagina}]}` — `trecho` já literal (checagem 2, com substituição pelo texto do chunk); `fonte`, `capitulo` e `pagina` vêm do banco, não do modelo |
| `alerta` | só depois da validação completa (checagens 5 e 6); ausente se removido ou movido | `{severidade, texto, chunkIds}` |
| `fim` | último evento de sucesso | `{nivelConfianca, modelo, thinkingLevel, usage{inputTokens, outputTokens, thoughtTokens}, custoUsd, tempos{msPrimeiroToken, msPrimeiroParagrafoValidado, msTotal}}` |
| `erro` | em qualquer ponto | `{codigo, mensagem}` — `citacao_fantasma`, `resposta_invalida`, `falha_recuperacao`, `falha_geracao`, `inconsistencia_validador`; a mensagem nunca contém texto do modelo nem detalhe interno |

Regras:

- **Parágrafo reprovado nunca é emitido.** `indice` conta só os parágrafos emitidos.
  Se todos forem reprovados, `fim` traz `nivelConfianca = "sem_evidencia"`.
- **Alerta por último.** O `alerta_seguranca` pode chegar antes dos parágrafos no JSON do
  modelo, mas só sai depois da validação completa. Se a checagem de interação o move
  para um parágrafo "Inferência não documentada:", esse parágrafo sai como `paragrafo`
  no fim do stream, antes de `citacoes`, e não há evento `alerta`.
- **`erro` invalida tudo.** A citação fantasma em um parágrafo aborta a consulta na hora
  (o stream do modelo é fechado); a que aparece só em `citacoes`/`alerta` é detectada
  no fim. Em ambos os casos o cliente descarta os parágrafos já recebidos
  (ARCHITECTURE.md §4, `FalhaCitacao`).
- **`sem_evidencia` no `fim`** continua mandando a UI esconder os parágrafos (o nível só
  é conhecido ao final; o modelo é instruído a deixar `paragrafos` vazio nesse caso).
- **Premissa de ordem.** A emissão antecipada depende de o modelo escrever `paragrafos`
  antes do resto do JSON (a ordem do schema do §6). Se vier depois, nada quebra: os
  parágrafos só saem mais tarde, e o tempo até o primeiro parágrafo validado piora.
  **Não verificado** contra o `gemini-3.8-flash` real neste trabalho (os testes usam
  um stream simulado).

**Contrato de TTFT.** Como não há token bruto no cliente, o primeiro conteúdo clínico
visível é o primeiro `paragrafo`. Três tempos são medidos separadamente, todos a partir
do recebimento da requisição, e registrados em `consulta_concluida`:

1. `ms_ate_primeiro_token` — primeiro texto do modelo (só servidor; o cliente nunca o vê).
2. `ms_ate_primeiro_paragrafo_validado` — primeiro evento `paragrafo` (nulo se nenhum
   parágrafo passou).
3. `ms_total` — até o último evento.

O tempo até o primeiro chunk do stream (qualquer parte, mesmo sem texto) continua em
`ms_ate_primeiro_evento`. Ver `DIVERGENCIAS.md` §10 e `FRONTEND_SPEC.md` §6.

### 7.2 `GET /vocabulario`

Serve ao app o vocabulário controlado para o autocomplete, com `X-API-Key` (mesmos 401/503
do `/consulta`). Lê das **mesmas fontes que o `/consulta` valida** — o dicionário
`etl/vocabulario/farmacos.yaml` (já carregado em `app.state.vocabulario`) e
`ESPECIES`/`COMORBIDADES` de `app/rag/composicao.py` —, de modo que o app nunca oferece um
valor que o servidor rejeitaria com 422.

```json
{
  "versao": "<sha256 do conteúdo, 12 hex>",
  "especies": ["canino", "felino"],
  "farmacos": [{"nome": "meloxicam", "sinonimos": ["..."]}],
  "comorbidades": [{"chave": "hepatopatia", "rotulo": "hepatopatia"}]
}
```

`farmacos` vem em ordem alfabética; `sinonimos` não repete o `nome`. O app casa o que o
usuário digita contra nome e sinônimos, mas **envia sempre o `nome`** (e a `chave` da
comorbidade). `versao` muda quando qualquer item muda. Teste de contrato
(`tests/test_api_vocabulario.py`): todo fármaco servido é aceito por `POST /consulta`.

## 8. Telemetria por consulta

```python
log.info("consulta_concluida",
    consulta_id=cid,
    modelo=settings.modelo_id,          # TCC §4.7
    thinking_level=nivel,
    ms_conexao=t_con,                   # retirada da conexão do pool (§3.5)
    ms_embedding=t_emb,                 # §3.5: etapas medidas separadamente
    ms_busca_vetorial=t_vet,            # só a consulta SQL, sem o embedding
    ms_busca_lexical=t_bm25,
    ms_fusao=t_rrf,
    ms_carga_trechos=t_carga,
    ms_recuperacao=t_rec,               # tempo de parede da recuperação inteira
    ms_ate_primeiro_evento=t_ev,
    ms_ate_primeiro_token=t_tok,                 # §7.1: três tempos, separados
    ms_ate_primeiro_paragrafo_validado=t_par,    # nulo se nenhum parágrafo passou
    ms_total=t_total,
    input_tokens=u.prompt_token_count,
    output_tokens=u.candidates_token_count,
    thought_tokens=u.thoughts_token_count,
    custo_usd=custo,
    chunks_recuperados=len(chunks),
    citacoes_validadas=n_ok,
    citacoes_fantasma=n_fantasma,
    desfecho=desfecho,                  # "ok" ou o código do evento `erro`
)
```

Custo (`None` se faltar preço ou contagem de tokens: custo desconhecido não é zero) = `(input/1e6 × PRECO_IN) + ((output + thought)/1e6 × PRECO_OUT)`. Os tokens de
raciocínio contam como saída (TCC §3.2c). Os preços são configuração, com a virada
tarifária de 01/01/2027 prevista.

## 9. Avaliação

**Recall@10** (`eval/recall_at_k.py`): gold set em `eval/qrels.yaml`, rotulado pelo
autor, com triagem assistida por modelo de linguagem; a decisão final de relevância foi do
autor (atualizado em 23/11/2026; o texto anterior dizia "rotulado por veterinário", e
`CRITERIOS_DE_ACEITE.md` já dizia "rotuladas pelo autor"). Compara três execuções —
híbrido, semântico puro, lexical puro — com `ranx`.
O critério do Quadro 1 é ganho mensurável do híbrido sobre ambas as estratégias isoladas.

`scripts.consolidar_qrels` separa a rotulação em dois arquivos pela linha `RELEVANTES:`
de cada `backend/data/rotulacao/<slug>.md`: chunk_id preenchido vai para `eval/qrels.yaml`
(Recall@10, acima); a marca `RELEVANTES: NENHUMA` — query revisada sem nenhum chunk que a
sustente — vai para `eval/qrels_sem_resposta.yaml`, fora do Recall@10. Esse segundo
arquivo é o gold set da Fase 3 (docs/PLANO_DE_FASES.md): mede se o sistema devolve
`nivel_confianca = "sem_evidencia"` para essas consultas em vez de responder sem lastro no
corpus.

**RAGAS** (`eval/ragas_run.py`): métricas `Faithfulness` e `ContextRelevance` (nome
atual do "Context Relevancy" do TCC — ver `DIVERGENCIAS.md` §5), juiz Gemini via
`LangchainLLMWrapper`. Limiares: `Faithfulness ≥ 0,80`, `ContextRelevance ≥ 0,75`.
Respostas reprovadas não vão ao painel humano (TCC §4.5b).

*Atualizado em 23/11/2026.* Decisão original acima: juiz Gemini e exclusão das reprovadas
do painel. O que mudou: o **juiz principal é o `claude-opus-5-5`** e o **juiz de comparação
é o Gemini** (`gemini-3.8-flash`, o mesmo modelo que gera as respostas, portanto não
independente); a aprovação é a do juiz principal. As respostas **reprovadas vão para a
análise secundária** (comparam o RAGAS com a avaliação dos especialistas) e não entram no
desfecho principal do painel. Onde está registrado: `docs/relatorio_metodologia.md`,
seções «Avaliação automatizada RAGAS (v4-r1)» e «Regra de análise do painel (fixada antes
da coleta)»; resultados em `backend/data/audit/ragas/resultado.md`. Os juízes usam os SDKs
nativos, não o `LangchainLLMWrapper` citado acima.

**Cenários** (`eval/scenarios.yaml`): os seis casos do Quadro 2 — paracetamol/felino,
ivermectina/MDR1, fenobarbital+carprofeno, tramadol felino vs. cão renal, insulina NPH
extra-label, meloxicam/IRC — cada um com o comportamento esperado e a página do Plumb's
para conferência humana.
