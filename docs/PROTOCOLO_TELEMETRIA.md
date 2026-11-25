# PROTOCOLO_TELEMETRIA.md — Campanha de telemetria (etapa 7a, OE5)

Evidência do OE5 (`CRITERIOS_DE_ACEITE.md`): tempo até o primeiro evento, TTFT (primeiro
parágrafo validado) e tempo total, por condição de rede, com P50/P90/P99 e custo. A
análise sai do CSV exportado pelo app, fora dele, com `backend/eval/analise_telemetria.py`.

## 0. Pré-requisitos (checar antes da primeira sessão)

| Item | Estado em 13/11/2026 |
|---|---|
| Back-end no Cloud Run (HTTPS) | **Implantado em 17/11/2026** (ver §0.1). Itens 1 a 3 abaixo concluídos. |
| APK de release apontando para ele | **Não.** O `app-release.apk` (06/11) não contém URL de back-end; a única URL no binário é o texto de exemplo `http://10.0.2.2:8000`. |

O que falta, na ordem:

1. `Dockerfile` do back-end (Python 3.12, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`),
   incluindo `data/bm25_index/` (hoje no `.gitignore`, então precisa ser gerado ou copiado
   para o build) e tudo o mais que o `lifespan` de `app/main.py` carrega na partida.
2. `gcloud` instalado e autenticado; projeto com faturamento; deploy do serviço com as
   variáveis de `.env.example` (`MODELO_ID`, `GEMINI_API_KEY`, `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `DATABASE_URL`, `APP_API_KEY`, `PRECO_IN_USD`, `PRECO_OUT_USD`)
   guardadas no Secret Manager, nunca na imagem.
3. Conferir `curl https://<url>/health` → `{"status":"ok","modelo_id":"gemini-3.8-flash"}` e
   uma consulta real por `curl` com `X-API-Key`.
4. Gerar o APK com o endereço embutido (o manifesto de release não permite HTTP em claro;
   o Cloud Run é HTTPS, então não há problema):
   `flutter build apk --release --dart-define=API_BASE_URL=https://<url> --dart-define=CLIENT_API_KEY=<chave>`.
   Alternativa sem recompilar: digitar o endereço em `Ajustes`.
5. Conferir no aparelho, em `Ajustes`, que o endereço mostrado é o do Cloud Run e rodar uma
   consulta de teste (não entra na campanha).

Registrar na planilha da campanha: aparelho, Android, operadora, versão do APK, URL do
serviço, região do Cloud Run, `modelo_versao` (rodapé da resposta).

### 0.1 Registro do deploy (17/11/2026)

| Item | Valor |
|---|---|
| Projeto GCP | `<ID_DO_PROJETO_GCP>` (o Gemini também é cobrado neste projeto) |
| Serviço / região | `vetfarmaco-rag-api` / `southamerica-east1` |
| URL | `https://<URL_DO_CLOUD_RUN>` |
| Revisão | `vetfarmaco-rag-api-00001-9f9` (criada em 2026-11-17 12:59 UTC) |
| Imagem | `southamerica-east1-docker.pkg.dev/<ID_DO_PROJETO_GCP>/cloud-run-source-deploy/vetfarmaco-rag-api@sha256:<DIGEST_DA_IMAGEM>` |
| Commit da lógica implantada | `6220e17`, sem alteração. O commit seguinte só acrescenta os arquivos de implantação (`backend/Dockerfile`, `backend/.gcloudignore`) e a documentação da campanha. |
| Recursos | 2 GiB, 1 vCPU, timeout 300 s, min 0, max 2, `--allow-unauthenticated` (proteção: `X-API-Key`) |
| Segredos (Secret Manager, `:latest`) | `MODELO_ID`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `APP_API_KEY`, `DATABASE_URL`, `PRECO_IN_USD`, `PRECO_OUT_USD`; leitura concedida por segredo à conta de serviço do Compute |

Conferência feita com `curl`: `/health` devolveu 200 com `modelo_id: gemini-3.8-flash`; `POST /consulta` sem chave devolveu 401; uma consulta sintética (meloxicam, felino) devolveu SSE em partes. Instante do evento a partir do envio: `recuperacao` em 2,1 s, primeiro `paragrafo` em 21,5 s, `citacoes` em 23,8 s, `fim` em 23,8 s. É uma única consulta de verificação, **não** uma medição da campanha (não entra nos CSVs).

## 1. Perguntas fixas

As seis situações do painel (`backend/eval/scenarios.yaml`, Quadro 2 do TCC). Digitar
**exatamente** estes dados em `Nova consulta`, sempre na mesma ordem (1 → 6):

| # | Id | Espécie | Fármaco(s) | Pergunta |
|---|---|---|---|---|
| 1 | `paracetamol-felino` | felino | paracetamol | Posso dar paracetamol para gato com dor? |
| 2 | `ivermectina-mdr1` | canino | ivermectina | Posso usar ivermectina em Collie? |
| 3 | `fenobarbital-carprofeno` | canino | fenobarbital, carprofeno | Cão epiléptico em uso de fenobarbital pode receber carprofeno? |
| 4 | `tramadol-felino-vs-cao-renal` | felino e canino | tramadol | Qual a dose de tramadol para gato e para cão com insuficiência renal? |
| 5 | `insulina-nph-extra-label` | felino | insulina NPH | Posso usar insulina NPH humana em gato diabético? Qual a dose inicial? |
| 6 | `meloxicam-irc` | felino | meloxicam | Posso repetir meloxicam em gato com doença renal crônica? |

Peso e demais campos: o mesmo valor sintético em toda repetição (sem dado de paciente
real, CLAUDE.md regra 8). Não tocar em `Salvar`.

> O CSV **não** traz o cenário. A ordem fixa 1→6 dentro de cada rodada é o que permite
> recuperá-lo depois; se uma consulta falhar, repita-a antes de seguir para a próxima.

## 2. Matriz

3 redes × 3 períodos × 3 rodadas × 6 perguntas = **162 consultas** (9 por pergunta e rede,
próximo das ~10 repetições do `PLANO_DE_FASES.md`).

| Eixo | Valores | Como garantir |
|---|---|---|
| Rede | Wi-Fi, 4G, 5G | Marcar em `Ajustes` → `Condição de rede da campanha` **antes** de cada sessão. O app não distingue 4G de 5G sozinho: conferir o indicador do sistema (4G/5G) e fixar o modo de rede em `Configurações` → `Rede móvel`; com Wi-Fi, desligar os dados móveis. |
| Período | manhã 06–12h, tarde 12–18h, noite 18–06h (horário de Brasília) | O período é derivado da coluna `data`, não digitado. Uma sessão não cruza a fronteira de período. |
| Rodada | 1, 2, 3 | Uma rodada = as 6 perguntas em ordem. As 3 rodadas de uma célula rede×período são feitas em sequência; esperar o fim de cada resposta antes de enviar a próxima. |

Total de sessões: 3 redes × 3 períodos = 9 (cada uma com 18 consultas, ~15–25 min). Ordem
sugerida: alternar as redes dentro do mesmo dia (ex.: manhã Wi-Fi, 4G, 5G) para que
variação de dia e de carga do Gemini não se confunda com variação de rede.

Cada sessão:

1. Subir a instância mínima (§5) e aguardar `/health` responder.
2. Uma consulta de aquecimento (não entra: ver §3) para a conexão TLS e o modelo.
3. Marcar a condição de rede; conferir o sinal (anotar barras/dBm se possível).
4. 3 rodadas × 6 perguntas.
5. Exportar o CSV (§4) e conferir que a contagem bate com 18 linhas novas.

## 3. Nenhuma medição vinda do cache

Como o cache funciona hoje: o app **só** serve do `hive_ce` quando a requisição falha (queda
de rede, erro do back-end); com a rede boa toda consulta vai ao servidor
(`resposta_cubit.dart`, `_tentarCache`). Uma linha de cache grava `desfecho = cache` e
`rede = none`, sem tempos de servidor. Portanto:

1. **Nunca usar modo avião** nem desligar a rede durante a campanha (isso é o passo do
   `ROTEIRO_MODO_AVIAO.md`, outra evidência).
2. Se aparecer o selo `Resposta armazenada em dd/MM · pode estar desatualizada`, a consulta
   falhou na rede: descartar e repetir.
3. Se possível, limpar as respostas guardadas (`Histórico`, deslizando as linhas) antes da
   primeira sessão, para que uma falha de rede não seja mascarada por uma resposta salva.
   Não confirmei no código se toda resposta vai ao `hive_ce` ou só as salvas; a regra 2 e
   o filtro da regra 4 cobrem os dois casos.
4. **Filtro obrigatório na análise:** `analise_telemetria.py` remove toda linha com
   `desfecho = cache` e informa quantas removeu. Só `desfecho = concluida` entra nas
   estatísticas de tempo.
5. Conferência cruzada por linha: linha válida tem `primeiro_token_servidor_ms`,
   `input_tokens` e `custo_usd` preenchidos; cache e falha não têm.
6. Limite que o app não controla: o Gemini pode aplicar cache implícito de contexto a
   prompts repetidos, o que reduziria o tempo de servidor nas rodadas 2 e 3. O CSV não
   registra tokens em cache. Declarar isto na seção de limitações e comparar rodada 1 × 2/3
   no relatório.

## 4. Nomenclatura dos CSVs

O export do app é **cumulativo** (todos os registros do aparelho) e o nome padrão é
`telemetria_vetfarmaco.csv` (ou `... (1).csv`). Renomear logo após exportar:

```
telemetria_<rede>_<periodo>_<AAAAMMDD>.csv
```

- `<rede>`: `wifi`, `4g`, `5g`
- `<periodo>`: `manha`, `tarde`, `noite`
- `<AAAAMMDD>`: data da sessão

Ex.: `telemetria_4g_manha_20261118.csv`. Guardar em `backend/data/telemetria/campanha/`.
Os arquivos exploratórios de 29/10 vão para `backend/data/telemetria/exploratorio/` e
**não** entram na análise final. Por ser dado de pesquisa, acrescentar
`backend/data/telemetria/` ao `.gitignore`, como já é feito com o painel.

O nome serve à organização. A análise **não confia nele**: rede vem de
`condicao_campanha`, período de `data`, e duplicatas (por causa do export cumulativo) são
removidas por `consulta_id`. Se o nome e as colunas divergirem, vale a coluna.

## 5. Instância mínima no Cloud Run

Evita a partida a frio (carga do índice BM25 no `lifespan`), que inflaria o primeiro
evento da primeira consulta. Serviço e região reais, conforme §0.1.

```bash
# Ligar (antes da sessão)
gcloud run services update vetfarmaco-rag-api --region southamerica-east1 --min-instances=1

# Conferir
gcloud run services describe vetfarmaco-rag-api --region southamerica-east1 \
  --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])"
curl -s https://<url>/health

# Desligar (fim da campanha; volta ao scale-to-zero do orçamento)
gcloud run services update vetfarmaco-rag-api --region southamerica-east1 --min-instances=0
```

Ligar na véspera ou ≥ 10 min antes da primeira sessão; desligar no mesmo dia em que
terminar a última, pois a instância ociosa é cobrada. Registrar data/hora de ligar e
desligar na planilha da campanha, para entrar no custo total (reserva de R$ 150,00,
TCC §6). Estimativa com os dados exploratórios: ~US$ 0,02–0,04 por consulta → 162
consultas ≈ US$ 4–7, bem abaixo da reserva (os `thought_tokens` dominam o custo).

## 6. Análise

```bash
cd backend
python -m eval.analise_telemetria data/telemetria/campanha/*.csv --saida data/telemetria/relatorio.md
```

Saída: auditoria (linhas lidas, duplicadas, **cache descartado**, falhas), P50/P90 do
primeiro evento, TTFT e total por rede × período (e por rede, todos os períodos), veredito
do critério P50 < 2.000 ms em 4G/5G, e correlação (Pearson e Spearman) do TTFT com
`thought_tokens`. Fuso padrão −3; ajustar com `--fuso`. P99 e custo de latência da
validação ainda não estão no script (ver `CRITERIOS_DE_ACEITE.md`, OE5).

## 7. Critério de conclusão

- 9 sessões feitas, 162 consultas, 18 por célula rede × período; células com menos de 15
  linhas `concluida` são completadas ou a lacuna é declarada.
- Relatório gerado, com a contagem de cache descartado e de consultas sem parágrafo
  validado reportadas.
- `modelo_versao` e `data` preenchidos em toda linha usada (TCC §4.7).
