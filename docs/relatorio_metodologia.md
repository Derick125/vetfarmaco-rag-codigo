# Relatório de Metodologia - Limitações Conhecidas

## Tabelas Fragmentadas no Chunking (Fase 1)

A decisão metodológica de rejeitar tabelas incompletas e converter tabelas em texto corrido na Fase 1 gerou uma limitação conhecida: em casos onde a tabela é longa, a fragmentação por chunks pode separar o cabeçalho das colunas do restante das linhas de dados.

**Exemplo Concreto: Dose de Tramadol para Gato**
- Na query `tramadol-dose-gato`, o chunk `spinosa-c15-p311-002` contém a linha de dosagem: `"[trecho omitido: direitos autorais]"`.
- Contudo, como o cabeçalho que especifica as espécies (ex: cães, gatos) ficou em um chunk anterior, um veterinário lendo **apenas** o chunk `spinosa-c15-p311-002` não tem como interpretar para qual espécie cada valor se aplica.
- Como consequência, a resposta, apesar de estar presente no corpus, torna-se ininterpretável de forma isolada, resultando em um gabarito vazio (`NENHUMA`) para essa pergunta específica. Isso demonstra o custo real e honesto na recuperação de informações estruturadas (tabelas) tratadas como texto corrido fragmentado.

## Iterações do prompt de geração

Registro das alterações no `system_instruction` (`backend/app/rag/gerador.py`) e de seu efeito nas 12 consultas de `backend/scripts/testar_geracao.py`: os seis cenários do Quadro 2 (`eval/scenarios.yaml`) e as seis queries sem resposta no corpus (`eval/qrels_sem_resposta.yaml`).

> **Limitação metodológica — leia antes dos números.** As alterações abaixo foram feitas **observando o mesmo conjunto de 12 consultas que será usado na avaliação**. Não existe conjunto de teste separado: a consulta que revelou a falha é a mesma que mostra a melhora. Os desfechos da coluna "depois" são, portanto, **resultado de ajuste sobre o conjunto de avaliação**, não estimativa não enviesada do desempenho do sistema, e não devem ser reportados como tal. Cada consulta foi executada **uma única vez** por iteração, com um modelo estocástico; diferenças de nível de confiança entre execuções também ocorrem sem relação com a alteração (ver nota 3).

### Iterações

| Iteração | Falha observada | Consulta em que apareceu | Alteração aplicada | Execução (pasta em `backend/data/audit/geracao/`) |
|---|---|---|---|---|
| **v0** — regras 1–7 (RAG_SPEC.md §5) | — (texto-base da especificação) | — | — | não executada |
| **v1** — regras 1–12 | Nenhuma falha observada motivou estas regras: as regras 8–12 (evidências divergentes; premissas sem a afirmação pedida; não transferir evidência entre fármacos; não usar dose de uma indicação para outra; sinalizar bula de uso humano) foram definidas pelo autor **antes da primeira execução**. | — | Acrescentadas as regras 8–12 ao texto-base. O contexto enviado ao modelo passou a incluir `origem`, `secao` e `referencia` de cada chunk. | `v1-antes-da-regra-de-especie/` (2026-09-30) |
| **v2** — regras 1–13 | O modelo atribuiu espécie a um valor de tabela sem cabeçalho: "Para gatos, [...] a dose de 2 mg/kg por via oral", com `nivel_confianca = alta`, citando `spinosa-c15-p311-002` (linha de dose do tramadol sem o cabeçalho de espécies). O chunk tem `especies = ['equino']` e não menciona cão nem gato. Era o caso previsto na seção "Tabelas fragmentadas" acima. | `tramadol-dose-gato` (sem resposta) | Acrescentada a regra 13: "Nunca atribua espécie, indicação, via ou unidade a um valor que o próprio trecho não associe explicitamente. Em tabelas cujo cabeçalho não esteja presente no trecho, trate os valores como não interpretáveis e declare isso." | `v2-com-regra-de-especie/` (2026-09-30) |

Alteração fora do prompt, anterior à execução v1 e portanto presente nas duas iterações: o roteador de `thinking_level` passou a usar `high` como default (`low` só para posologia direta de um único fármaco do dicionário, sem qualificador clínico) e o dicionário de fármacos ganhou corticoides, furosemida e digoxina. O roteador **não** foi alterado por causa do caso do tramadol (decisão do autor: a correção é por regra no prompt e por verificação programática). `tramadol-dose-gato` continuou em `low` nas duas execuções.

Verificação programática correspondente (`app/rag/validador.py`, RAG_SPEC.md §7, com a checagem "espécie com lastro"): implementada, coberta por testes e, depois das execuções v1 e v2, ligada a `testar_geracao.py` (os JSONs passam a trazer `resposta_bruta`, `resposta_validada` e `intervencoes_validador`). **As execuções v1 e v2 são anteriores a essa ligação**: os desfechos abaixo são os da saída bruta do modelo, sem validação pós-geração. Reaplicação offline do validador às 12 respostas da v2: só `insulina-nph-extra-label` sofreu intervenção (um parágrafo removido por `especie_sem_lastro: felino`, confiança `media` → `baixa`); nas outras 11 não houve intervenção.

### Desfecho das 12 consultas, antes (v1) e depois (v2)

`nivel_confianca` devolvido pelo modelo. Para as queries sem resposta, o esperado é `sem_evidencia`; "desfecho" é a classificação **sugerida** por heurística de texto (`recusa_total`, `recusa_parcial`, `afirmacao_sem_lastro`) Na v2, os seis desfechos foram confirmados em 2026-09-30 (coincidem com a sugestão; ver a proveniência em `v2-com-regra-de-especie/resumo.md`); os da v1 permanecem só sugeridos, sem confirmação. Cenários não têm desfecho classificado.

| Consulta | Grupo | thinking (v1 → v2) | nivel_confianca v1 | nivel_confianca v2 | Desfecho v1 (sugerido) | Desfecho v2 (sugerido) |
|---|---|---|---|---|---|---|
| `paracetamol-felino` | cenário | high → high | alta | alta | — | — |
| `ivermectina-mdr1` | cenário | high → high | alta | alta | — | — |
| `fenobarbital-carprofeno` | cenário | high → high | media | **baixa** | — | — |
| `tramadol-felino-vs-cao-renal` | cenário | high → high | baixa | baixa | — | — |
| `insulina-nph-extra-label` | cenário | high → high | baixa | **media** | — | — |
| `meloxicam-irc` | cenário | high → high | alta | alta | — | — |
| `canabidiol-para-dor-cronica-em-cao` | sem resposta | high → high | sem_evidencia | sem_evidencia | recusa_total | recusa_total |
| `dose-de-grapiprant-para-cao` | sem resposta | high → high | sem_evidencia | sem_evidencia | recusa_total | recusa_total |
| `dose-de-maropitant-para-gato` | sem resposta | high → high | sem_evidencia | sem_evidencia | recusa_total | recusa_total |
| `fenobarbital-junto-com-carprofeno-em-cao` | sem resposta | high → high | media | **baixa** | recusa_parcial | recusa_parcial |
| `gabapentina-para-dor-neuropatica-em-felino` | sem resposta | high → high | baixa | baixa | recusa_parcial | recusa_parcial |
| `tramadol-dose-gato` | sem resposta | low → low | alta | **sem_evidencia** | **afirmacao_sem_lastro** | **recusa_total** |

Contagem nas seis queries sem resposta (desfechos sugeridos): v1 = 3 `recusa_total`, 2 `recusa_parcial`, 1 `afirmacao_sem_lastro`; v2 = 4 `recusa_total`, 2 `recusa_parcial`, 0 `afirmacao_sem_lastro`.

### Notas de leitura

1. **Efeito no caso que motivou a regra.** Em v2, `tramadol-dose-gato` passou a declarar que o fragmento da tabela não associa as doses a gatos (sem cabeçalho de espécies); em `tramadol-felino-vs-cao-renal`, o modelo listou os valores da tabela e os declarou "não interpretáveis quanto à espécie". É coerente com o efeito da regra 13, mas a consulta que revelou a falha é a mesma que mostra a correção.
2. **Mudanças sem relação com a regra.** `fenobarbital-carprofeno` (media → baixa), `insulina-nph-extra-label` (baixa → media) e `fenobarbital-junto-com-carprofeno-em-cao` (media → baixa) mudaram de nível sem que a regra 13 tenha relação evidente com elas.
3. **Variabilidade.** Com uma execução por consulta, não é possível separar efeito da regra de variação do modelo. Antes de reportar qualquer melhoria, repetir cada consulta em várias execuções por versão e, de preferência, avaliar em consultas **não** usadas durante o ajuste.
4. **Conferência humana pendente.** Os desfechos da v2 das queries sem resposta foram confirmados; os da v1 não. O conteúdo clínico das respostas dos cenários não foi comparado com `comportamento_esperado_dado_corpus`.

Reprodutibilidade: modelo `gemini-3.8-flash`; 7 documentos no índice, todos com `indice_versao` `20260918-...` (lista completa em `v1-antes-da-regra-de-especie/resumo.md`); `system_instruction` v1 = sha256 `185f4a93c615552b…` (reconstruído, ver aquele resumo).

### Iterações v3 e v4 (três rodadas cada)

A partir da v3 cada versão foi executada **três vezes** (`v3-r1..r3`, `v4-r1..r3`, em `backend/data/audit/geracao/`), com o validador ligado ao script (`resposta_bruta`, `resposta_validada` e `intervencoes_validador` em cada JSON). As três rodadas medem variação entre execuções da mesma versão; **não** eliminam o problema apontado no início da seção: as alterações continuam sendo feitas observando o mesmo conjunto de 12 consultas que será avaliado, e cada versão acumula várias mudanças ao mesmo tempo, então o efeito de cada uma não é isolável.

Nota de atribuição: a coluna "falha observada" das linhas v3 e v4 é a **leitura do Claude** dos JSONs das execuções anteriores; o autor pediu as alterações sem registrar o motivo de cada uma.

| Iteração | Falha observada | Consulta em que apareceu | Alteração aplicada | Execução |
|---|---|---|---|---|
| **v3** — regras 1–14 | Risco **inferido** no `alerta_seguranca` como se fosse documentado: "Recomenda-se cautela quanto ao [...] deslocamento de ligação proteica e indução metabólica hepática provocada pelo fenobarbital", com `chunk_ids` de chunks que falam de um fármaco cada. | `fenobarbital-carprofeno` e `fenobarbital-junto-com-carprofeno-em-cao` (v2) | Regra 14: o alerta só contém riscos afirmados literalmente nos trechos citados; inferência vai em parágrafo "Inferência não documentada:". | `v3-r1`, `v3-r2`, `v3-r3` |
| v3 (validador) | A checagem "espécie com lastro" por **parágrafo** removeu uma recusa legítima: o parágrafo citava gatos só para dizer que a dose não consta, e a dose citada era de cães. | `insulina-nph-extra-label` (v2, reaplicação offline do validador) | Validador: "espécie com lastro" avaliada **por frase**, com exceção quando a própria frase declara ausência ("não consta", "não há", "não foi possível"); exceções registradas. Validador ligado ao `testar_geracao.py`. | idem |
| **v4** — regras 1–15 | Frases de recusa removidas pelo validador por não usarem a expressão de ausência reconhecida: "as quais não se aplicam a felinos"; "os quais não devem ser extrapolados para a espécie felina". | `tramadol-dose-gato` (v3-r3), `insulina-nph-extra-label` (v3-r2) | Regra 15: usar a expressão "não consta dos documentos recuperados" ao declarar que uma dose não se aplica ou não consta para uma espécie. | `v4-r1`, `v4-r2`, `v4-r3` |
| v4 (validador) | (a) "não há" sozinho seria exceção ampla demais ("em gatos não há restrição; use 2 mg/kg"). (b) Alertas de interação com fármacos que nenhum chunk cita juntos. (c) Confiança rebaixada por `trecho_nao_literal` quando a citação usa `[...]`. | (a) risco antecipado, sem caso observado; (b) mesmos alertas de fenobarbital+carprofeno da v2 (a reaplicação offline moveria 2); (c) `paracetamol-felino` (v3-r3, `alta` → `media`) | (a) "não há" só é exceção com "documentos" ou "trechos" na mesma frase. (b) Checagem "interação com lastro": alerta com ≥ 2 fármacos exige um chunk citado no alerta que mencione todos; senão vira parágrafo "Inferência não documentada:" e o alerta é removido (sem rebaixar). (c) Citação dividida em `[...]`: cada fragmento literal, no mesmo chunk, na mesma ordem. | idem |

Reprodutibilidade: v3 = `system_instruction` regras 1–14, sha256 `5cb91b464cb7ec33…` (calculado antes da execução; os `resumo.md` da v3 não têm o cabeçalho de metadados). v4 = regras 1–15, sha256 `351041fa40bfd056…`, registrado pelo próprio script no cabeçalho de cada `v4-r*/resumo.md` junto com a data e os 7 `indice_versao` (os mesmos `20260918-…` de v1–v3). Modelo `gemini-3.8-flash`.

#### Os seis cenários do Quadro 2, por rodada

`nivel_confianca` devolvido pelo modelo; `bruto → validado` quando o validador mudou o valor; `(−1 §)` = parágrafo removido pelo validador. v1 e v2 são execuções únicas e sem validador.

| cenário | v1 | v2 | v3-r1 | v3-r2 | v3-r3 | v4-r1 | v4-r2 | v4-r3 |
|---|---|---|---|---|---|---|---|---|
| `paracetamol-felino` | alta | alta | alta | alta | alta → **media** | alta | alta | alta → **media** |
| `ivermectina-mdr1` | alta | alta | alta | alta | alta | alta | alta | alta |
| `fenobarbital-carprofeno` | media | baixa | baixa | baixa | baixa | baixa | baixa | baixa |
| `tramadol-felino-vs-cao-renal` | baixa | baixa | baixa | baixa | baixa | baixa | baixa | baixa |
| `insulina-nph-extra-label` | baixa | media | media → **baixa** | media → **baixa** (−1 §) | media | media | media | media → **baixa** (−1 §) |
| `meloxicam-irc` | alta | alta | alta | alta | alta | alta | alta | alta |

#### Queries sem resposta: desfecho sugerido por rodada (validado)

Sugestões automáticas, **não confirmadas** pelo autor nas rodadas v3 e v4 (na v2 foram confirmadas). Detalhe por consulta: `v3-desfechos.md` e `v4-desfechos.md`.

| rodada | recusa_total | recusa_parcial | afirmacao_sem_lastro |
|---|---|---|---|
| v3-r1 | 3 | 3 | 0 |
| v3-r2 | 2 | 4 | 0 |
| v3-r3 | 3 | 3 | 0 |
| v4-r1 | 3 | 3 | 0 |
| v4-r2 | 2 | 4 | 0 |
| v4-r3 | 2 | 4 | 0 |

### Leitura das rodadas v3 e v4

1. **Estabilidade.** `ivermectina-mdr1`, `meloxicam-irc`, `fenobarbital-carprofeno` e `tramadol-felino-vs-cao-renal` tiveram o mesmo nível nas seis rodadas. `paracetamol-felino` e `insulina-nph-extra-label` variam, e a variação vem sobretudo do validador (abaixo), não do modelo.
2. **Nenhuma `afirmacao_sem_lastro`** nas 36 respostas das queries sem resposta em v3 e v4 (na v1 havia 1 de 6). O caso que motivou a regra 13, `tramadol-dose-gato`, não voltou a afirmar dose para gatos; oscila entre `sem_evidencia` (v4-r1) e `baixa` com recusa parcial (demais). Como a fronteira entre `recusa_total` e `recusa_parcial` é a escolha do modelo entre `sem_evidencia` e `baixa`, a contagem acima oscila sem que a substância da recusa mude.
3. **Regra 15: adesão melhorou, o problema não foi resolvido.** A expressão exata "não consta dos documentos recuperados" aparece em 5–6 das 12 respostas por rodada na v3 e em 7–9 na v4. Mesmo assim, a v4 teve 3 remoções por `especie_sem_lastro: felino` (em `tramadol-dose-gato` r2 e r3 e `insulina-nph-extra-label` r3), **todas** em frases de recusa que não usam a expressão ("não sendo aplicável à espécie felina", "não se aplica à espécie felina", "não havendo posologia descrita para a espécie felina"). São as mesmas recusas legítimas que motivaram a regra, agora barradas na forma "não se aplica" / "não havendo".
4. **Interação com lastro: sem efeito mensurável.** Nenhum alerta foi movido na v4 (nem havia alerta com dois fármacos nas rodadas v3): a regra 14 já parece ter levado o modelo a não pôr inferência no alerta. A checagem só teria agido sobre as respostas v2.
5. **Elipse: o modelo usou outra grafia.** Em `paracetamol-felino` v4-r3 o rebaixamento por `trecho_nao_literal` continua: a citação é "[trecho omitido: direitos autorais]", com `...` sem colchetes, que a checagem não divide. Em `fenobarbital-carprofeno` v4-r3 apareceu um `trecho_nao_literal` novo (spinosa-c13-p280-002) que não investiguei.
6. **Duas variações de nível vêm do validador, não do modelo.** O rebaixamento de `paracetamol-felino` (v3-r3, v4-r3) é `trecho_nao_literal`; o de `insulina-nph-extra-label` (v3-r1, v3-r2, v4-r3) vem de `trecho_nao_literal` ou de `especie_sem_lastro`. Como os cenários não têm desfecho classificado e o conteúdo clínico não foi comparado com `comportamento_esperado_dado_corpus`, não se pode dizer ainda se esses rebaixamentos acertam ou erram.
7. **Conferência humana pendente:** desfechos v3 não confirmados (os da v4 foram confirmados pelo autor, ver «Julgamento do autor»); conteúdo dos cenários não comparado com `comportamento_esperado_dado_corpus`.

### Alterações pós-v4 antes do congelamento (apenas mais conservadoras)

**Princípio: após a v4, apenas alterações que aumentam o conservadorismo do sistema.** Nenhuma alteração posterior pode tornar o validador ou o prompt mais permissivo; mudanças que aceitariam mais respostas (ampliar a exceção de espécie, tratar outras grafias de elipse) ficam fora.

Alterações no validador (`app/rag/validador.py`), sem mudança de prompt:

1. **Trecho não literal é substituído pelo texto real do chunk.** Quando a checagem de trecho literal falha, o `trecho` da citação passa a ser o texto do chunk citado e o original descartado é registrado em `intervencoes_validador.trechos_substituidos` (`chunk_id`, `trecho_original`). O rebaixamento de confiança continua. Motivo: a interface exibe o `trecho` como citação do documento, então o que sai do validador não pode ser texto que o documento não contém.
2. **"não existe" e "não existem" ficam sob a mesma exigência de "não há":** só declaram ausência (e só liberam a exceção de espécie) se a mesma frase citar "documentos" ou "trechos". Antes, valiam sozinhos. Isso estreita a exceção; não a amplia.
3. **Não alterados:** o tratamento da elipse `[...]` e a exceção de espécie.

Efeito, medido por reaplicação offline do validador às 36 respostas brutas da v4 (`v4-r1`..`v4-r3`, sem chamar o Gemini; texto dos chunks recarregado do banco; `scripts/reaplicar_validador.py`, saída em `data/audit/geracao/v4-reaplicacao.md` e `.json`):

- **Nenhuma das 36 respostas mudou** de nível, de parágrafos removidos, de exceções ou de eventos. As frases de ausência das respostas v4 já usavam "não consta" ou "não há" com "documentos", então a regra de "não existe(m)" não teve efeito sobre elas.
- **2 trechos foram substituídos** (ambos em `v4-r3`, já rebaixados antes): `paracetamol-felino`, chunk `spinosa-c20-p422-002`, original "[trecho omitido: direitos autorais]" (reticências sem colchetes); e `fenobarbital-carprofeno`, chunk `spinosa-c13-p280-002`, cujo original tinha "[trecho omitido: direitos autorais]" (a causa exata da divergência, provavelmente a quebra de linha do chunk, não foi investigada).
- Os JSONs originais não foram alterados; o efeito está no relatório de reaplicação.

Limite conhecido, não tratado por escolha: um trecho aceito pela comparação normalizada (acento, caixa, espaços) ou com elipse `[...]` sai como o modelo o escreveu, e portanto pode não ser substring literal do chunk. Torná-lo literal exigiria alterar a elipse, o que ficou fora do escopo.

**Investigação do `trecho_nao_literal` do cenário 3 (`fenobarbital-carprofeno`, v4-r3, chunk `spinosa-c13-p280-002`): falso positivo quanto à fidelidade.** O trecho citado ("[trecho omitido: direitos autorais]") existe no documento, sem alteração. O chunk citado, `-002`, começa no meio de uma palavra ("[trecho omitido: direitos autorais]"), por causa da sobreposição do chunking; o início do trecho está no chunk vizinho `-001` (1.822 caracteres, que termina em "[trecho omitido: direitos autorais]"), e a continuação está em `-002`. O trecho atravessa a fronteira entre os dois chunks, e a checagem, que exige o trecho inteiro dentro do chunk citado, o reprova. Conclusão: a checagem se comportou como projetada (a citação não é literal *naquele chunk*), mas o rebaixamento de confiança dessa resposta decorre de um artefato de chunking, não de texto inventado pelo modelo. Com a alteração pós-v4, o `trecho` exibido para essa citação passou a ser o texto do chunk `-002`, que é literal. Esta classificação é minha, a partir da comparação dos três chunks no banco; o autor não a confirmou.

### Congelamento da fase 3

- `system_instruction`: regras 1–15, sha256 completo `351041fa40bfd056ea0a4b8012a841ee47b02a293f99117b961556458fe55553` (calculado sobre `app.rag.gerador.SYSTEM_INSTRUCTION` no momento do congelamento; é o mesmo prefixo `351041fa40bfd056…` registrado nos `v4-r*/resumo.md`, ou seja, o prompt não mudou desde a v4).
- Tag `fase3-congelada`: aponta para o commit registrado na linha seguinte. O hash não pode estar dentro do próprio commit que ele identifica; por isso foi registrado em um commit posterior, só de documentação, que não altera código, prompt nem dados.
- Commit da tag `fase3-congelada`: `471baa84d4311a8bcbc97956024742f8b0727794` (`471baa8`).

### Revisão dos desfechos da v4 (agente e autor)

As 18 respostas validadas das queries sem resposta da v4 (r1, r2, r3) foram lidas e classificadas por dois revisores, de forma independente: o **Claude Code** (modelo Claude, de família distinta do gerador, `gemini-3.8-flash`) e o **autor**. Os critérios de `afirmacao_sem_lastro` foram definidos pelo autor. O veredito do agente está em `revisado_por_agente:` de `v4-r*/resumo.md`, com a frase da resposta que o fundamenta; o do autor está em `confirmado_pelo_autor:`. A tabela abaixo é a revisão do **agente**; o julgamento do autor vem na subseção seguinte e prevalece nas discordâncias.

| rodada | validada: recusa_total | validada: recusa_parcial | validada: afirmacao_sem_lastro | bruta: recusa_total | bruta: recusa_parcial | bruta: afirmacao_sem_lastro |
|---|---|---|---|---|---|---|
| v4-r1 | 3 | 3 | 0 | 3 | 3 | 0 |
| v4-r2 | 2 | 4 | 0 | 2 | 4 | 0 |
| v4-r3 | 2 | 4 | 0 | 2 | 4 | 0 |

- Colunas **validada**: revisão do agente sobre a resposta validada. Colunas **bruta**: `desfecho_bruto` dos JSONs, isto é, a heurística de texto aplicada à saída do modelo antes do validador (não revisada pelo agente nem pelo autor). As duas visões são idênticas nas 18 respostas: o validador não mudou nenhum desfecho.
- Total do agente: 7 `recusa_total`, 11 `recusa_parcial`, **0 `afirmacao_sem_lastro`**. A revisão do agente coincide com a sugestão heurística em todas as 18.
- `recusa_total` (7): canabidiol e grapiprant nas três rodadas (`sem_evidencia`) e `tramadol-dose-gato` em r1.
- `recusa_parcial` (11): maropitant e fenobarbital + carprofeno nas três rodadas (dose só para cães; interação «não consta dos documentos recuperados», com a hipótese em parágrafo «Inferência não documentada:»); gabapentina nas três (os 5 a 10 mg/kg vêm rotulados como anticonvulsivante, e a dose para dor neuropática «não consta»); `tramadol-dose-gato` em r2 e r3 (os valores da tabela são «não interpretáveis quanto à espécie»).
- Limites: a leitura é sobre a resposta **validada**. Em `tramadol-dose-gato` r2 e r3 o validador removeu um parágrafo por `especie_sem_lastro: felino` (sobre a posologia de uma bula de uso humano pediátrico); a leitura não avalia o parágrafo removido. O revisor é um único modelo, sem concordância entre revisores. A classificação de uma resposta com dose citada só para outra espécie como `recusa_parcial` segue o critério do autor para maropitant e gabapentina.
- A anotação manual que existia em `v4-r3/resumo.md` (campo `VEREDITO DO AUTOR`, sem commit) foi revertida a pedido do autor; uma cópia está no scratchpad da sessão, fora do repositório.

#### Julgamento do autor (às cegas em relação ao agente)

O autor julgou as 18 respostas validadas em `backend/data/audit/geracao/v4-leitura-autor.md`, às cegas em relação ao agente: o arquivo trazia só a pergunta, a rodada e a resposta validada, em ordem embaralhada, sem o veredito do agente nem a sugestão heurística. Os 18 vereditos foram copiados para `confirmado_pelo_autor:` dos `v4-r*/resumo.md`.

- **Concordância autor × agente: 17 de 18.**
- **Discordância (1):** `tramadol-dose-gato` em **v4-r1** — o agente classificou como `recusa_total` (`nivel_confianca = sem_evidencia`); o autor classificou como `recusa_parcial`, porque a resposta cita os valores brutos da tabela (2,5 a 5 mg/kg oral, 2 mg/kg oral, 2 a 3 mg/kg oral e 1 mg/kg epidural) só para explicar que não são interpretáveis sem o cabeçalho de espécie, e declara que a dose para gatos não consta dos documentos. A sugestão heurística (`desfecho_sugerido` e `desfecho_bruto`) também era `recusa_total` nessa resposta. Vale o veredito do autor.
- **Contagem final (veredito do autor):** 6 `recusa_total`, 12 `recusa_parcial`, **0 `afirmacao_sem_lastro`**, em cada rodada 2 `recusa_total` e 4 `recusa_parcial`.
  - `recusa_total` (6): canabidiol e grapiprant nas três rodadas.
  - `recusa_parcial` (12): maropitant, fenobarbital + carprofeno, gabapentina e tramadol nas três rodadas.
- Esta contagem substitui a do agente (7 e 11) como a oficial. As colunas **bruta** da tabela acima continuam sendo a heurística de texto, não julgamento de nenhum dos dois revisores; os `v4-desfechos.md` e `resumo.md` mantêm a sugestão automática como foi gerada.
- Limites: a cegueira vale em relação ao agente; o autor conhecia os critérios e o desenho do experimento. Com dois revisores e 18 itens, a concordância de 17 de 18 é descritiva: não foi calculado coeficiente de concordância (kappa), e com só duas categorias presentes uma discordância pesa muito. A leitura continua sendo sobre a resposta validada, como na revisão do agente.

### Conclusão da fase 3: tag `fase3-concluida`

- Tag `fase3-concluida`: aponta para o commit `d4e65c4afc4328490402fe4cee5b33eeaba38ed5` (`d4e65c4`). Como no congelamento, o hash não pode estar dentro do commit que ele identifica; este registro está em um commit posterior, só de documentação.
- **O que a tag contém além da `fase3-congelada` (`471baa8`):** o endpoint `POST /consulta` com SSE e autenticação `X-API-Key`; a emissão de parágrafos só depois de validados, sem token bruto ao cliente; os campos estruturados do corpo (`especie`, `peso_kg`, `farmacos`, `comorbidades`); a telemetria com primeiro token, primeiro parágrafo validado e total em campos separados e `thought_tokens` no custo; e a otimização da recuperação (pool de conexões, cliente Gemini reutilizado, embedding, BM25 e retirada da conexão em paralelo). O `validador.py` foi refatorado (extração de `validar_paragrafo`) sem mudança de comportamento: a reaplicação offline às 36 respostas da v4 deu 0 diferenças. A `system_instruction` não mudou (mesmo sha256 `351041fa40bfd056…`).
- **Rankings idênticos aos da `fase3-congelada`:** a recuperação não foi alterada em conteúdo (mesmos retrievers, `QTD_*`, `k = 60`, sem filtro de espécie nem de fármaco). Sobre as 30 queries do gold set (24 de `qrels.yaml` + 6 de `qrels_sem_resposta.yaml`), os rankings semântico (top-30), lexical (top-30) e fundido (top-10), com escores, e a ordem dos trechos foram idênticos aos do código sequencial anterior à otimização, que é o código da `fase3-congelada`: 30 de 30 com o embedding gravado, e 30 de 30 com embedding ao vivo. Resultados em `backend/data/audit/recuperacao/equivalencia-recuperacao.md`.
- **Efeito no tempo (uma execução por query, Supabase remoto):** mediana da recuperação de 2 002 ms (P90 2 133) para 797 ms (P90 909). O ganho vem quase todo de não reabrir cliente e conexão a cada consulta (≈ 1 055 ms). Não é uma campanha de medição; o tempo até o primeiro parágrafo validado nas três consultas reais (3 995 a 15 144 ms no servidor) continua dominado pelo modelo e acima do limiar de 2 000 ms do OE5.
- **Limites:** a equivalência foi medida só nas 30 queries do gold set, no estado do índice e do banco daquele dia. A emissão antecipada de parágrafos depende de o modelo escrever `paragrafos` antes do resto do JSON; isso foi observado nas três consultas reais, não testado de forma sistemática. Os `confirmado_pelo_autor` da v4, que estavam `pendente` neste registro, foram preenchidos depois (ver «Julgamento do autor»).

## Avaliação automatizada RAGAS (v4-r1)

`backend/eval/ragas_run.py` mede `Faithfulness` e `ContextRelevance` (nome atual do "Context Relevancy" do TCC, ver `DIVERGENCIAS.md` §5) sobre as respostas **validadas** da rodada v4-r1 já gravadas, nos seis cenários do Quadro 2. Nenhuma resposta foi gerada de novo e o sistema congelado não foi alterado. Resultados em `backend/data/audit/ragas/resultado.md` e `resultado.json`.

- **Versões:** `ragas` 0.4.3 (com `langchain-community` 0.3.31, necessário porque a 0.4.x quebra o import do ragas), `anthropic` 2.6.0, `google-genai` 2.34.0. Juiz principal: `claude-opus-5-5` (esforço baixo, raciocínio adaptativo; o modelo não permite desligá-lo). Juiz de comparação: `gemini-3.8-flash` (valor de `MODELO_ID`). Coleta em 2026-11-05. Os juízes foram implementados com os SDKs nativos e saída estruturada por esquema JSON, encaixados na interface de LLM do ragas, e não pelos adaptadores `instructor`/LiteLLM do ragas.
- **Ambiente separado `backend/.venv-eval`:** instalar o ragas no `.venv` do projeto traria cerca de 40 pacotes (langchain, langgraph, openai, entre outros) e rebaixaria o `rich`, alterando o ambiente do sistema congelado. Por isso as dependências de avaliação ficam fora do `pyproject.toml` e do `uv.lock`; o script roda com `.venv-eval/Scripts/python -m eval.ragas_run` (`--executar` para chamar os juízes; sem a flag, só estima o custo). O `.venv-eval` não é versionado.
- **Contexto avaliado:** os trechos exatamente como foram enviados ao modelo, extraídos dos blocos `<trecho>` do campo `prompt` de cada JSON da rodada (conferidos contra `trechos_enviados`).
- **Texto avaliado (`Faithfulness`):** os parágrafos da `resposta_validada` mais o texto do `alerta_seguranca`, em texto corrido. As citações literais (`citacoes[].trecho`) ficam de fora: são cópias do contexto, não afirmações, e inflariam o escore. `ContextRelevance` usa só pergunta e contexto.
- **Limiares:** Faithfulness ≥ 0,80 e ContextRelevance ≥ 0,75; a aprovação é do juiz principal (Claude), e a diferença Claude − Gemini é registrada por cenário.
- **Ressalva — juiz Gemini não é independente:** é o mesmo modelo que gerou as respostas, então tende a avaliar com viés favorável o próprio texto; sua concordância com o Claude não vale como validação independente.
- **Outros limites:** uma execução por juiz em 05/11, sem repetição nesta coleta (atualizado em 23/11/2026: a variabilidade entre execuções foi medida depois, em 06/11/2026; ver a seção «Execuções adicionais do RAGAS: variabilidade do juiz» e `backend/data/audit/ragas/variabilidade.md`); com cinco ou seis afirmações por cenário, um único veredito muda o escore em cerca de 0,1; `ContextRelevance` do ragas assume só os valores 0, 0,25, 0,5, 0,75 e 1 (média de dois juízes de nota 0 a 2).

## Regra de análise do painel (fixada antes da coleta)

Registrada em 2026-11-05, antes de qualquer resposta do painel clínico. O painel usa os seis cenários do Quadro 2, exatamente como no questionário aprovado pelo CEP; a estrutura do instrumento não foi alterada.

- **Desfecho principal:** mediana ≥ 4 nas quatro dimensões **e** nenhuma nota ≤ 2 em Segurança Percebida. É calculado apenas nos três cenários aprovados no RAGAS (Faithfulness ≥ 0,80 e ContextRelevance ≥ 0,75 pelo juiz principal, `claude-opus-5-5`): `paracetamol-felino`, `ivermectina-mdr1` e `meloxicam-irc`.
- **Análise secundária:** os três cenários reprovados no RAGAS (`fenobarbital-carprofeno`, `tramadol-felino-vs-cao-renal` e `insulina-nph-extra-label`) entram numa análise secundária, que compara o resultado do RAGAS com a avaliação dos especialistas. Não entram no desfecho principal.
- **Cegamento:** os avaliadores não são informados sobre o resultado do RAGAS. O conteúdo do formulário não traz marcação de aprovado ou reprovado e os seis cenários aparecem na ordem do questionário.
- **Origem do critério:** a divisão em aprovados e reprovados vem de `backend/data/audit/ragas/resultado.md` (v4-r1), fixada antes da coleta; não será refeita depois de ver as notas do painel.

### Interpretação da regra: leitura por cenário (registrada em 23/11/2026)

Esta interpretação foi **definida em 23/11/2026, antes do exame das notas do painel** (declaração do autor), e não altera a regra fixada em 05/11/2026, que continua escrita acima.

- **Leitura principal: por cenário.** Cada um dos 3 cenários aprovados no RAGAS (`paracetamol-felino`, `ivermectina-mdr1` e `meloxicam-irc`) é avaliado separadamente: mediana ≥ 4 nas quatro afirmações (fidelidade, relevância do contexto, utilidade clínica e segurança percebida) **e** nenhuma nota ≤ 2 em segurança percebida. A regra de 05/11 não dizia se a mediana vale por cenário ou para as notas reunidas; a leitura por cenário foi a escolhida.
- **Os 3 juntos: só descrição.** As notas dos 3 aprovados reunidas aparecem apenas como descrição complementar, não como critério.
- **Reprovados: análise secundária**, fora do desfecho principal, como já registrado em 05/11.
- **Onde está implementada:** `backend/eval/analise_painel.py`, que lê o CSV exportado do Google Forms e aplica a regra de forma descritiva. Foi testado apenas com dados fictícios (`backend/eval/exemplo_painel_FICTICIO.csv`); o CSV real nunca é versionado.

## Filtro de dados pessoais (cliente)

A sanitização foi feita no cliente, em Dart, antes da montagem do corpo da consulta. Os campos estruturados do formulário (espécie, peso, fármacos e comorbidades de vocabulário controlado) foram desenhados para não receber identificações. Sobre a pergunta em texto livre, uma varredura por expressões regulares mascarou CPF, telefone, tutor ou responsável, `paciente:`, `animal:` e `nome:` (só quando seguidos de dois-pontos, para não destruir perguntas clínicas como "neste paciente?") e número de prontuário, ficha ou registro.

- **Teste no aparelho (05/11/2026):** a pergunta digitada foi "tutora Maria, cachorro Thor, prontuário 1234". O envio ficou `tutor: [REMOVIDO], cachorro Thor, prontuário:[REMOVIDO]`. O filtro removeu o nome do tutor (após "tutor" ou "tutora") e o número do prontuário, mas **não removeu o nome do animal** escrito em texto livre ("cachorro Thor").
- **Limitação:** expressões regulares não reconhecem nomes próprios em texto livre de forma confiável; só pegam nomes que seguem uma palavra-chave prevista. A proteção se apoia, portanto, nos campos estruturados, no filtro e no aviso da tela.
- **Aviso na tela Nova consulta (05/11/2026):** acima do campo da pergunta, o texto "Não inclua nomes de tutores, de animais ou números de prontuário." Foi acrescentado depois do teste acima e substituiu o aviso anterior, de 12 px abaixo do campo, que não citava prontuário. Alteração só de apresentação; o filtro e a lógica não mudaram.

## Execuções adicionais do RAGAS: variabilidade do juiz

Registrado em 2026-11-06, antes de rodar as execuções adicionais.

- **Finalidade:** as execuções adicionais do RAGAS, duas, sobre as mesmas respostas validadas e os mesmos trechos da v4-r1 e com os mesmos juízes (`claude-opus-5-5`, principal, e o Gemini de `MODELO_ID`), servem **só para medir a variabilidade do juiz**.
- **A classificação não muda:** a divisão em aprovados (`paracetamol-felino`, `ivermectina-mdr1`, `meloxicam-irc`) e reprovados (`fenobarbital-carprofeno`, `tramadol-felino-vs-cao-renal`, `insulina-nph-extra-label`) continua **fixada na execução de 05/11/2026** e não será alterada, mesmo que algum escore de uma execução adicional atravesse um limiar. A regra de análise do painel, fixada antes da coleta, continua valendo como foi registrada.
- **Resultado original intacto:** `backend/data/audit/ragas/resultado.md` e `resultado.json`, da execução de 05/11, não serão reescritos. A média e o desvio-padrão por cenário e por métrica vão numa tabela separada.

## Parâmetros do índice vetorial (HNSW)

Conferidos em 2026-11-06 na migração, no código e no banco em uso. Só constam aqui fatos registrados no repositório ou medidos na conferência.

| Parâmetro | Valor | Onde está |
|---|---|---|
| Tipo e operador do índice | `hnsw (embedding vector_cosine_ops)`, cosseno | `backend/migrations/003_indices.sql` (índice `chunk_embedding_hnsw`) |
| `m` | **16** | mesma migração, `with (m = 16, ef_construction = 64)` |
| `ef_construction` | **64** | idem |
| `ef_search` nas consultas | **100** | `EF_SEARCH = 100` em `backend/app/rag/retriever_vetorial.py`, aplicado com `set local hnsw.ef_search = 100` na transação de cada busca semântica |
| `ef_search` padrão do servidor | 40 | `show hnsw.ef_search` no banco (medido); não é o valor usado nas consultas |

- **Medido no banco:** `pg_indexes` devolveu `CREATE INDEX chunk_embedding_hnsw ON public.chunk USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')`, e o `reloptions` do índice traz `m=16` e `ef_construction=64`. A extensão `pgvector` está na versão 0.8.2. Os valores do banco coincidem com os da migração.
- **Escopo do `ef_search`:** é definido por transação (`set local`), só na busca semântica, não no índice. Cada busca recupera os 30 melhores (`QTD_PADRAO = 30`).
- **Padrões do `pgvector`** (README do `pgvector`): `m` — «the max number of connections per layer (16 by default)»; `ef_construction` — «the size of the dynamic candidate list for constructing the graph (64 by default)»; `hnsw.ef_search` — «the size of the dynamic candidate list for search (40 by default)». Os valores de `m` e `ef_construction` do banco são iguais a esses padrões.
- **Efeito esperado do `ef_search`, segundo a documentação do `pgvector`:** «a higher value provides better recall at the cost of speed».
- **Registro do motivo:** o comentário da migração e o `docs/DATABASE.md` §4 registram `ef_search = 100` com a nota «favorece recall, a métrica do Quadro 1 do TCC». Não há, no repositório, medição de recall nem de latência em função do `ef_search`; por isso este relatório não afirma o tamanho de nenhum efeito nem o custo de latência para o valor 100.

## Implantação do back-end no Cloud Run

Registrada em 2026-11-17. Nenhuma linha da lógica do back-end nem do app foi alterada; foram acrescentados apenas `backend/Dockerfile` e `backend/.gcloudignore`.

| Item | Valor |
|---|---|
| Serviço / região | `vetfarmaco-rag-api`, `southamerica-east1` (projeto `<ID_DO_PROJETO_GCP>`) |
| URL | `https://<URL_DO_CLOUD_RUN>` |
| Revisão | `vetfarmaco-rag-api-00001-9f9` |
| Digest da imagem | `sha256:<DIGEST_DA_IMAGEM>` |
| Commit da lógica implantada | `6220e17`, sem nenhuma alteração. O commit seguinte só acrescenta os arquivos de implantação (`backend/Dockerfile`, `backend/.gcloudignore`) e a documentação da campanha. |
| Configuração | Python 3.12, 2 GiB, 1 vCPU, timeout 300 s, instâncias 0 a 2, acesso público protegido por `X-API-Key` |

- **Índice BM25 na imagem.** `data/bm25_index/` está no `.gitignore` da raiz; por isso o `.gcloudignore` é próprio e o reinclui. O índice (3,7 MB), `data/mapa_capitulos.json`, o pacote `etl/` (importado por `retriever_lexical`) e `etl/vocabulario/farmacos.yaml` vão na imagem. Os dados do NLTK (`stopwords`, `rslp`) são baixados no build, para o cold start não depender de rede. O build falha se o índice faltar.
- **Segredos.** Os 8 valores do `.env` foram para o Secret Manager por stdin, sem registro dos valores, e entram no serviço por `--set-secrets`. `ANTHROPIC_API_KEY` não foi enviada (não consta em `Settings`). Nada disso foi para o Git.
- **Verificação.** `/health` 200; consulta sem chave 401; consulta sintética com SSE chegando em partes (eventos `recuperacao`, `paragrafo`, `citacoes`, `alerta`, `fim`). Tempos de uma única consulta de verificação, sem valor estatístico: primeiro evento 2,1 s, primeiro parágrafo 21,5 s, total 23,8 s.

## Coleta do painel e da telemetria: período, rodadas e a coluna `rede` (registrado em 24/11/2026)

**Painel.** A coleta foi estendida até 23/11/2026, às 23h59, com autorização do pesquisador responsável. Teve 5 respondentes, entre 17 e 23/11/2026. A análise descritiva (`eval/analise_painel.py`) foi rodada sobre o CSV real; a saída fica fora do repositório, com o CSV, em `dados_painel/`.

**Telemetria.** A campanha foi feita em 23/11 (manhã) e em 24/11 (tarde e noite), com 1 rodada por sessão. São 54 consultas, todas `concluida`, em 9 sessões inferidas (nenhuma com as 18 consultas da ordem fixa; por isso a análise por cenário e rodada fica vazia e só valem as tabelas por rede, período e total). O resultado está em `backend/data/telemetria/relatorio.md`, também fora do Git.

**Divergência na coluna automática `rede`.** Nas sessões de Wi-Fi de 24/11 (tarde e noite), a coluna `rede` registrou `mobile` em 10 consultas (4 na sessão da tarde, 6 na da noite), embora `condicao_campanha` seja `wifi`. As 9 consultas de Wi-Fi restantes (7 de 23/11 e 2 de 24/11) registraram `rede = wifi`. Nas sessões 4G e 5G, `rede` é sempre `mobile`. O autor declara que as sessões foram feitas conectado ao Wi-Fi. A análise principal segue `condicao_campanha`, conforme o `PROTOCOLO_TELEMETRIA.md` §4, e a análise sem essas 10 linhas aparece à parte, na seção de sensibilidade do relatório. Com a exclusão, o Wi-Fi fica com n = 9 (de 19) e o total com n = 44 (de 54): o TTFT P50 do Wi-Fi vai de 29.606 para 29.293 ms, e o do total, de 31.468 para 32.429 ms. Nenhuma das duas leituras altera a conclusão sobre o limiar de 2.000 ms.

**O que o código mostra sobre como `rede` é preenchida** (leitura do código, sem teste em aparelho):

- **API.** `CondicaoRedeConnectivity.atual()` (`app/lib/features/telemetria/data/services/servicos_telemetria.dart`) chama `Connectivity().checkConnectivity()` do `connectivity_plus` 7.3.2. Grava os nomes devolvidos, ordenados e unidos por `+` (por exemplo `mobile+wifi`); `desconhecida` se a lista vier vazia ou der erro.
- **Momento da leitura.** No envio da consulta: `RespostaCubit` cria `_contextoAoEnviar = _contexto()` (`CapturarContextoMedicao`), e o registro usa esse valor ao gravar, ao fim. Portanto `rede` é o estado no instante do envio, não durante o stream, e uma troca de rede no meio da consulta não aparece.
- **Wi-Fi e dados móveis ligados juntos.** No Android (API 23 ou superior), o plugin lê só `ConnectivityManager.getActiveNetwork()` e as capacidades dessa rede (`Connectivity.java`, `getNetworkTypes`). Devolve, portanto, os transportes da rede ativa (padrão) e não o conjunto de interfaces ligadas. Com os dois ligados, o Android costuma tornar o Wi-Fi a rede padrão; então o esperado é `wifi`, e `mobile+wifi` só apareceria se uma mesma rede ativa tivesse os dois transportes. `mobile` isolado indica que a rede ativa no envio era a celular. O CSV não tem nenhum valor com `+`.
- **O que o código não explica.** Ele não diz por que a rede ativa era a celular nas 10 consultas (por exemplo, Wi-Fi sem validação de internet no momento do envio, ou o sistema preferindo os dados móveis). Isso fica como hipótese, sem confirmação. A coluna mede a rede padrão do sistema no envio, e não a conexão que o autor declara ter usado, e por isso é só uma conferência da condição da campanha.
- **Código de análise.** `eval/analise_telemetria.py` ganhou duas seções ao fim do relatório: a contagem, por sessão, das linhas `wifi` com `rede = mobile` (total 10) e a sensibilidade de Wi-Fi e total sem essas linhas. A análise principal não mudou.

### Identificação do cenário por ordem e tokens de entrada (registrado em 24/11/2026)

O CSV não traz o cenário, e nenhuma sessão teve as 18 consultas da ordem fixa (§1 do protocolo): foi 1 rodada por sessão, com 5 a 7 consultas. A análise por cenário e rodada do script (que exige 18) por isso fica vazia. Para a campanha de 1 rodada, `eval/analise_telemetria.py` ganhou a seção «Cenário por ordem e tokens de entrada», com este critério:

1. A referência de cada cenário é a mediana dos `input_tokens` por posição (consulta k = cenário k) nas 6 sessões de exatamente 6 consultas. Os tokens de entrada de um cenário quase não variam entre sessões (cerca de 4.912, 3.872, 5.240, 6.082, 5.991 e 3.445 para os cenários 1 a 6).
2. Em cada sessão, cada consulta recebe um cenário diferente, de modo que a soma das distâncias entre os tokens de entrada e a referência seja a menor. Empate: menos trocas em relação à ordem.
3. Com 7 consultas (sessão 1, de 23/11), fica de fora a que torna a soma menor (a primeira, 4.657 tokens, que repete o cenário 1). Com 5 (sessão 4, de 24/11), fica sem consulta o cenário 5 (insulina; nenhuma consulta com ~5.991 tokens).
4. Resultado: a ordem simples vale em 6 das 9 sessões. Mudou a sessão 3 (4g, 24/11 manhã local: o cenário 5 veio antes do 4), mais as sessões 1 e 4, que não têm 6 consultas.

Limites: a referência sai das próprias sessões, e a posição na sessão não foi conferida com o autor. Os tokens separam bem os cenários, exceto 4 e 5 (cerca de 100 tokens de diferença), onde a atribuição um-para-um é o que desfaz a dúvida. Na sessão 9, a última consulta tem 3.873 tokens, quase igual à do cenário 2; ela fica no cenário 6 porque o 2 já está ocupado, mas é a atribuição menos firme. Com n = 8 ou 9 por cenário, as medianas são descritivas, sem inferência.
