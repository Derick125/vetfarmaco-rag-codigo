# ROTEIRO_MODO_AVIAO.md — Roteiro manual de leitura offline

Evidência do OE2 (`CRITERIOS_DE_ACEITE.md`): com o modo avião ligado, uma consulta já
respondida é servida do `hive_ce` com o selo de data, e uma consulta nova mostra o estado
offline sem travar. A lógica está coberta por testes automatizados
(`app/test/features/historico/historico_test.dart`); este roteiro confirma o
comportamento **no aparelho** e deve ser gravado (vídeo de tela) como evidência.

## Preparação

1. Back-end rodando e alcançável pelo aparelho (`uvicorn app.main:app --host 0.0.0.0`).
2. App instalado com o endereço e a chave do cliente:
   `flutter run --dart-define=API_BASE_URL=http://<ip>:8000 --dart-define=CLIENT_API_KEY=<chave>`
3. Termo de uso aceito e introdução concluída ou pulada (o app abre na tela `Início`). Wi-Fi ligado.
4. Em `Ajustes` → `Condição de rede da campanha`, marcar a condição real (Wi-Fi, 4G ou 5G):
   ela é gravada em cada registro de telemetria (coluna `condicao_campanha` do CSV).
5. Anotar: aparelho, versão do Android, versão do modelo (rodapé da resposta), data.

## Passos

| # | Ação | Resultado esperado |
|---|---|---|
| 1 | Na tela `Início`, tocar `Nova consulta`. Em `/consulta`: espécie **felino**, peso **4,2**, fármaco **meloxicam**, pergunta `É seguro repetir meloxicam neste paciente?`. Abrir `Ver o que será enviado`. | JSON com `especie`, `peso_kg`, `farmacos`, `complexidade_dica`; nenhum nome nem número de prontuário. |
| 2 | Tocar `Consultar a literatura`. | `Buscando na literatura…` → `N trechos recuperados. Redigindo…` → parágrafos aparecem um a um, cada um com trilho sólido e âncora numerada. |
| 3 | Tocar uma âncora. | Folha de evidência com trecho em serifa, fonte, capítulo/página e `chunk_id`. |
| 4 | Ao fim, rodapé com `Confiança … · <modelo> · <data> · tempos`. Tocar `Salvar`. | Botão vira `Salva`. |
| 5 | Voltar e abrir `Histórico` (atalho na tela `Início` ou ícone no topo de `/consulta`). | A consulta aparece com resumo, data e ponto de alerta (vermelho só se houve alerta). |
| 6 | **Ligar o modo avião** (Wi-Fi e dados desligados). | — |
| 7 | Na tela `Início`, tocar `Nova consulta`; em `/consulta`, refazer **exatamente** a consulta do passo 1 e tocar `Consultar a literatura`. | Resposta aparece do cache com o selo `Resposta armazenada em dd/MM · pode estar desatualizada` no topo e botão `Atualizar` (não há `Salvar`). |
| 8 | Em `/consulta` (tela `Início` → `Nova consulta`), fazer uma consulta **diferente** (ex.: outro fármaco) e enviar. | `Sem conexão. Esta consulta precisa da rede.` com `Ver histórico` e `Tentar de novo`; sem travar nem tela branca. |
| 9 | Tocar `Ver histórico`. | Faixa `⦿ offline — exibindo respostas salvas`; a consulta salva abre normalmente. |
| 10 | Deslizar uma linha para a esquerda. | A linha é removida; sem itens, `Nenhuma consulta salva ainda.` |
| 11 | **Desligar o modo avião**, voltar ao passo 7 e tocar `Atualizar`. | Nova resposta pela rede, **sem** selo de cache. |
| 12 | Em `Ajustes` → `Telemetria das consultas` → `Exportar CSV`. | Folha de compartilhamento; o CSV abre em planilha com uma linha por consulta, incluindo a do passo 7 com `desfecho = cache`, e as colunas `condicao_campanha` e `modelo_versao` preenchidas (a de cache e a de falha offline usam o modelo da resposta guardada ou o último informado pelo `/health`) e `thinking_level` (`low`/`high`) nas linhas em que o servidor chegou a decidi-lo. |

## Critério de aprovação

- Passos 7 e 8 funcionam sem travar e com os textos exatos acima.
- O selo do passo 7 está visível o tempo todo (não some ao rolar).
- Nenhum dado de paciente real foi usado (CLAUDE.md §4.8).
- O CSV do passo 12 tem `modelo_versao` e `data` preenchidos nas consultas que chegaram
  ao `fim`, e `thinking_level` em toda linha que passou pela recuperação.

## Registro da execução

| Campo | Valor |
|---|---|
| Data | 29/10/2026 |
| Aparelho / Android | Xiaomi 22101320G / Android 14 |
| Versão do modelo | gemini-3.8-flash |
| Resultado dos passos 7 e 8 | Aprovados (repetidos com a versão que grava `thinking_level`): selo de cache visível ao rolar; consulta nova mostrou `Sem conexão` sem travar. CSV com `thinking_level` nas consultas concluídas e no cache, e `modelo_versao` também nas linhas de falha. |
| Vídeo | _caminho/link_ |
