# DIVERGENCIAS.md — Documentação oficial × TCC

Pontos verificados em setembro de 2026 em que a documentação das ferramentas diverge do
que o TCC afirma, ou acrescenta restrição que o TCC não previu. Cada item traz a decisão
adotada. **Nenhuma delas altera o desenho da pesquisa** — são ajustes de implementação, e
devem constar da seção de limitações da monografia.

| # | Ponto | O que o TCC diz | O que a documentação diz | Decisão |
|---|---|---|---|---|
| 1 | Constante do RRF | `k = 60` (Cormack et al., 2009) | O exemplo de busca híbrida do Supabase usa `rrf_k = 50` | Manter **k=60**. O RRF roda no FastAPI, não no SQL, então o default do Supabase é irrelevante. |
| 2 | BM25 no banco | Busca lexical BM25 com `k1` e `b` ajustáveis | O PostgreSQL gerenciado do Supabase não oferece BM25 nativo; `ts_rank_cd` não computa IDF verdadeiro | BM25 canônico em `bm25s` no back-end. `ts_rank_cd` fica como sinal auxiliar. Compatível com o TCC, que já situa a busca no back-end. |
| 3 | Dimensão do embedding | Não menciona limite | `gemini-embedding-001` gera 3072 dims; o índice HNSW do tipo `vector` suporta no máximo 2000 | Usar `output_dimensionality=1536` (Matryoshka) com normalização L2 manual. Alternativa documentada: `halfvec(3072)`. |
| 4 | `thinking_level` | `low`, `medium`, `high`; `minimal` não suportado | Confirmado para `gemini-3.8-flash`. Acrescenta: o **default é `medium`** | Definir o nível **sempre** explicitamente. Não confiar no default. |
| 5 | Métrica do RAGAS | "Context Relevancy" | A métrica clássica foi descontinuada; o equivalente atual chama-se **`ContextRelevance`** | Implementar `ContextRelevance`, mantendo o limiar de 0,75. Registrar a renomeação na monografia. |
| 6 | Cache local | "Hive" | O pacote `hive` original está sem manutenção ativa; a comunidade migrou para `hive_ce` | Usar **`hive_ce`**, que preserva a API do Hive. O requisito do TCC (cache local em Hive) é cumprido. |
| 7 | Chunking GUIDE-RAG | Sliding window com sobreposição, conforme Liu et al. (2025) | Os valores numéricos exatos recomendados pelo artigo **não foram verificados** | Adotar 512 tokens / 64 de sobreposição, baseline consolidado. Se o Recall@10 ficar baixo, elevar a sobreposição para 128 antes de qualquer outro ajuste. |
| 8 | Limite de entrada do embedding | Não menciona | `gemini-embedding-001` aceita até 2048 tokens por entrada | O ETL valida que nenhum chunk excede 2048 tokens. |
| 9 | Rotatividade de modelos | Cita quatro modelos Flash entre maio e setembro de 2026 e a depreciação do modelo originalmente previsto | Confirmado pela página oficial de depreciações | Reforça a decisão do TCC §4.7: `MODELO_ID` é configuração injetada na camada de dados. |
| 10 | Definição de TTFT | TTFT = tempo até o primeiro **token** (§1.4 H2, Quadro 1: < 2 s em 4G/5G), reportado com o tempo até o primeiro evento de stream | Não é divergência de documentação oficial, e sim do **desenho de segurança**: o cliente nunca recebe token bruto (`RAG_SPEC.md` §7.1), então o primeiro conteúdo visível é o primeiro parágrafo **validado** | **Fechado.** O limiar de P50 < 2 000 ms se aplica ao tempo até o **primeiro parágrafo validado** (`ttftMs` do cliente). O tempo até o primeiro token do modelo (servidor) e o tempo até o primeiro evento de stream são reportados junto. A diferença entre o primeiro parágrafo validado e o primeiro token do modelo é registrada como **custo de latência da validação**. O TTFT assim medido é maior que o do TCC por construção, e a monografia deve dizer que o critério foi aplicado à medida mais conservadora. Consultas sem parágrafo validado ficam fora do P50 e são contadas. Reflexo em `CRITERIOS_DE_ACEITE.md` (OE5). |

## Confirmações (o TCC está correto)

- `gemini-3.8-flash` é identificador válido e vigente.
- Janela de 1.048.576 tokens de entrada e 65.536 de saída.
- Preço promocional US$ 0,75 / US$ 3,75 por milhão até 31/12/2026, dobrando para
  US$ 1,50 / US$ 7,50 em 01/01/2027.
- Tokens de raciocínio são cobrados como saída.
- `minimal` não é suportado neste modelo: a deliberação interna não pode ser suprimida e
  compõe o piso da latência medida.
- No tier pago, os dados não são usados para treinar os modelos base; no tier gratuito,
  podem ser.
- RRF com `k = 60` é o valor do trabalho original de Cormack, Clarke & Büttcher (SIGIR
  2009).

## Estimativa de custo revisada

Com as premissas do TCC §6 (≈500 consultas, ~15.000 tokens de entrada e ~4.000 de saída
por consulta), sob a tabela **promocional** de 2026:

- Entrada: 7,5 M × US$ 0,75/M = **US$ 5,63**
- Saída (incluindo raciocínio): 2,0 M × US$ 3,75/M = **US$ 7,50**
- Embeddings do corpus: desprezível (< US$ 0,50)
- **Total ≈ US$ 14 (≈ R$ 77)**

Confortavelmente abaixo da reserva de R$ 150,00. Sob a tabela padrão de 2027, o valor
dobra para ≈ US$ 28 (≈ R$ 154) — daí a recomendação de concluir a campanha de telemetria
ainda em 2026, como o cronograma já prevê.

## Itens não verificados

- Valores numéricos específicos de chunk e sobreposição recomendados pelo GUIDE-RAG
  (Liu, McCoy & Wright, JAMIA 2025).
- Nome exato do atributo `thinking_level` dentro de `types.ThinkingConfig` na versão
  instalada do `google-genai` — confirmar em runtime na Fase 3.
- Versão exata do `pgvector` provisionada no projeto Supabase; verificar com
  `select extversion from pg_extension where extname = 'vector';`.
