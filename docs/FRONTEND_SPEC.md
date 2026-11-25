# FRONTEND_SPEC.md — Telas, design system e camada de apresentação

Especificação normativa da interface do aplicativo Flutter. Cada tela tem uma ficha com
objetivo, rota, BLoC, estados, layout, textos de interface e regras de segurança
clínica. O Claude Code deve implementar as telas na ordem das fichas.

---

## Parte I — Direção de design

### 1. O problema que a interface precisa resolver

O TCC não é sobre "um chat com IA". É sobre **distinguir uma resposta ancorada em
evidência de uma resposta que apenas parece correta** — a Falácia da Acurácia (§1.3),
com o gap de 14% entre sucesso percebido e ancoragem efetiva. Uma interface de chat
convencional é ativamente hostil a essa pesquisa: ela apresenta texto gerado e texto
fundamentado com exatamente a mesma aparência, o que reproduz no visual o erro de
atribuição que o trabalho quer medir.

Daí a decisão central de design: **a proveniência é o elemento visual principal, não um
rodapé.** O usuário deve conseguir dizer, olhando por meio segundo, quais frases têm
lastro documental e quais não têm.

Contexto de uso, que restringe tudo o mais: clínica de pequenos animais no Sertão
Central cearense, celular Android na mão, muitas vezes uma mão só, luz ambiente forte,
rede 4G instável, decisão sob pressão de tempo. Isso exige contraste alto, alvos de
toque grandes, zero dependência de cor isolada para transmitir risco, e estados de
espera que informam em vez de entreter.

### 2. Tokens

**Cor.** A paleta vem do vocabulário material da rotina veterinária, não de uma paleta
genérica de app de saúde. Cor de risco é semântica estrita: nunca decorativa, nunca
aplicada a algo que não seja um alerta real.

| Token | Hex | Papel |
|---|---|---|
| `paper` | `#F4F6F4` | fundo — branco de receituário, levemente esverdeado |
| `surface` | `#FFFFFF` | superfícies elevadas (folhas, campos) |
| `ink` | `#1A211F` | texto principal — tinta verde-escura, não preto |
| `inkMuted` | `#5A6663` | texto secundário, metadados |
| `rule` | `#D3DAD6` | traços estruturais |
| `metileno` | `#17506B` | ação primária, links, âncoras de citação |
| `ancorado` | `#2C6248` | evidência confirmada |
| `iodo` | `#A65A15` | cautela: ajuste de dose, uso extra-label |
| `contra` | `#96131F` | contraindicação absoluta |

`metileno` é o azul de metileno; `iodo` é o âmbar da povidona-iodo. São referências
diretas ao material da clínica. `iodo` é usado **somente** em blocos de cautela — nunca
como cor de marca ou realce decorativo.

**Tipografia.** Duas famílias, com uma divisão de trabalho que carrega significado:

- **IBM Plex Sans** — toda a interface e **todo o texto gerado pelo modelo**.
- **IBM Plex Serif** — **exclusivamente os trechos recuperados do corpus**, citados
  literalmente.

Ou seja: o usuário aprende, em uma sessão, que serifa significa "isto está no livro" e
sem serifa significa "isto o modelo escreveu". A tipografia passa a fazer parte do
mecanismo de mitigação da Falácia da Acurácia, não apenas a vesti-lo.

Escala (Elements of Typographic Style, razão ~1.25): 12 / 14 / 16 / 20 / 25 / 31.
Corpo em 16/1.5. Serifa recebe 1.6 de altura de linha. Números de dose usam
`FontFeature.tabularFigures()` — alinhamento em coluna e distinção 0/O, que importa
quando o valor é `0,02 mg/kg`.

**Layout.** Coluna única, mobile-first (base 380 px), alinhamento à esquerda, medida de
linha ≤ 68 caracteres. Espaçamento em múltiplos de 4. Raio de canto: 4 px em campos e
botões, 0 em blocos de alerta (o alerta tem cara de carimbo, não de cartão). **Não use
o kit de cartões arredondados com sombra cinza** — a separação de conteúdo é feita pelo
trilho de evidência e por blocos de preenchimento sólido.

**Movimento.** *(Emenda proposta, pendente de aprovação — Parte V §25.)* Um único momento orquestrado: o streaming da resposta, em que cada
parágrafo concluído "trava" sua âncora de citação no trilho com uma transição de 120 ms.
Nada mais anima sozinho. Transições que respondem a toque (abrir a evidência, expandir
o histórico) são bem-vindas. `MediaQuery.disableAnimations` é respeitado.

### 3. O elemento memorável: o trilho de evidência

Toda resposta é renderizada com um trilho vertical de 3 px à esquerda. O trilho é
segmentado por parágrafo:

- Segmento **sólido `ancorado`** + âncora numerada → o parágrafo tem citação validada.
  Tocar a âncora abre o trecho original.
- Segmento **hachurado `iodo`** → o parágrafo não tem citação. Isso deve ser raro; o
  back-end já rejeita respostas sem lastro. Quando aparece, vem acompanhado do rótulo
  `sem lastro documental`.
- Segmento **sólido `contra`** → o parágrafo é um alerta de segurança e é promovido para
  o topo da resposta.

Este é o único lugar onde a interface gasta ousadia. Todo o resto — campos, listas,
histórico — é deliberadamente quieto.

### 4. O que foi descartado, e por quê

*(Emenda proposta, pendente de aprovação — Parte V §24: a pergunta do usuário passa a ser um balão; a resposta do modelo continua **sem** balão, com o trilho de evidência.)*

Foram rejeitadas, por serem defaults e não escolhas: fundo creme com serifa de alto
contraste e acento terracota; bolhas de chat; cartões arredondados idênticos com sombra
suave; rótulos em caixa-alta espaçada acima de cada seção; seta "→" grudada nos botões;
ícone de robô ou de "IA brilhante". Nenhum acrescenta informação, e o formato de bolhas
de chat especificamente empurra a interface na direção errada — ele apaga a diferença
entre afirmação e evidência.

---

## Parte II — Contratos que a interface consome

### 5. Modelo da resposta

O back-end entrega, via SSE, os campos definidos em `RAG_SPEC.md` §7. O app modela isso
com `freezed`:

```dart
@freezed
class RespostaClinica with _$RespostaClinica {
  const factory RespostaClinica({
    required String consultaId,
    required List<ParagrafoResposta> paragrafos,
    required List<Citacao> citacoes,
    required NivelConfianca nivelConfianca,
    AlertaSeguranca? alertaSeguranca,
    required String modeloVersao,   // obrigatório: TCC §4.7
    required DateTime geradaEm,
    @Default(false) bool origemCache,
  }) = _RespostaClinica;
}

@freezed
class ParagrafoResposta with _$ParagrafoResposta {
  const factory ParagrafoResposta({
    required String texto,
    required List<String> chunkIds,   // vazio ⇒ trilho hachurado
  }) = _ParagrafoResposta;
}

@freezed
class Citacao with _$Citacao {
  const factory Citacao({
    required String chunkId,
    required int indice,          // número exibido na âncora
    required String trecho,       // literal, renderizado em serifa
    required String fonte,        // "Spinosa et al. (2017)" | "Bula — <fármaco>"
    String? capitulo,
    int? pagina,
  }) = _Citacao;
}

enum NivelConfianca { alta, media, baixa, semEvidencia }
```

**Regra de renderização inegociável:** se `nivelConfianca == semEvidencia` ou
`citacoes.isEmpty`, a tela **não** renderiza os parágrafos como resposta clínica. Ela
renderiza o estado *Sem evidência suficiente* (§14).

### 6. Eventos SSE e medição de TTFT

O cliente **nunca recebe token bruto**: o back-end acumula a saída do modelo e só emite
objetos completos, depois de validados (`RAG_SPEC.md` §7.1). Não existe evento `token`.

| Evento | Carga | Uso na UI |
|---|---|---|
| `recuperacao` | `{chunks, ms}` | atualiza o indicador de espera; **primeiro evento** do stream |
| `paragrafo` | `{indice, texto, chunkIds}` | renderiza o parágrafo já validado e trava a âncora no trilho; o primeiro **para o cronômetro de TTFT** |
| `citacoes` | `{citacoes: [{chunkId, indice, trecho, fonte, capitulo, pagina}]}` | preenche os trechos das âncoras (antes disso, tocar numa âncora não abre o trecho) |
| `alerta` | `AlertaSeguranca` | promove o bloco ao topo; **só chega depois da validação completa**, junto ao fim da resposta |
| `fim` | `{nivelConfianca, modelo, usage, custoUsd, tempos}` | fixa o nível de confiança, grava telemetria |
| `erro` | `{codigo, mensagem}` | estado de falha; **descarta os parágrafos já recebidos** |

Consequências para a tela `/consulta/:id` (§10): o nível de confiança só é conhecido no
`fim`, então a resposta transmitida aparece sem selo até lá; se o `fim` trouxer
`semEvidencia`, a tela troca para *Sem evidência suficiente* (§14) e some com os
parágrafos. Como o alerta de segurança chega depois dos parágrafos, o rodapé do estado
*Transmitindo* avisa que alertas de segurança aparecem ao final da resposta.

```dart
// Contrato de TTFT: envio da requisição → primeiro parágrafo VALIDADO recebido.
// (O primeiro token do modelo só existe no servidor — `RAG_SPEC.md` §7.1.)
final relogio = Stopwatch()..start();
int? ttftMs;            // primeiro evento `paragrafo`
int? primeiroEventoMs;  // primeiro evento do stream (`recuperacao`)

await for (final evento in _rag.consultar(req)) {
  primeiroEventoMs ??= relogio.elapsedMilliseconds;
  if (evento is ParagrafoEvent && evento.texto.trim().isNotEmpty) {
    ttftMs ??= relogio.elapsedMilliseconds;
  }
  // ...
}
```

Os valores são reportados juntos, sempre separados (TCC §1.4 H2 e Quadro 1):

| Medida | Onde | Campo |
|---|---|---|
| Tempo até o primeiro evento de stream | cliente | `primeiroEventoMs` |
| **TTFT do contrato** (primeiro parágrafo validado) | cliente | `ttftMs` |
| Primeiro token do modelo | servidor | `fim.tempos.msPrimeiroToken` |
| Primeiro parágrafo validado | servidor | `fim.tempos.msPrimeiroParagrafoValidado` |
| Total | cliente e servidor | `fim.tempos.msTotal` |

`ttftMs − fim.tempos.msPrimeiroParagrafoValidado` aproxima o custo de rede; a diferença
entre o primeiro token do modelo e o primeiro parágrafo validado é o custo de esperar o
parágrafo fechar e ser validado. **O `ttftMs` deste contrato é maior que o TTFT do TCC
(primeiro token), por construção** — ver `DIVERGENCIAS.md` §10.

---

## Parte III — Fichas de tela

Rotas via `go_router`. Cada tela tem um Cubit ou BLoC próprio em
`app/lib/features/<feature>/presentation/`.

### 7. `/` — Abertura

**Objetivo:** inicializar DI, abrir as caixas do `hive_ce`, ler a configuração e decidir
o destino.

**BLoC:** `BootstrapCubit` → `Carregando | ParaTermo | ParaConsulta | FalhaConfig`.

Sem logotipo animado. *(Proposta pendente de aprovação — Parte V §20: marca estática na
abertura, no máximo 1 s.)* Se a inicialização passar de 400 ms, exibe uma
linha de texto: `Preparando o acervo local`. Em `FalhaConfig` (endpoint ausente),
mostra a mensagem e um botão `Abrir ajustes` — nunca uma tela branca.

---

### 8. `/termo` — Termo de uso clínico

**Objetivo:** registrar aceite obrigatório antes do primeiro uso. Exigido pelo desenho
ético (TCC §4.9) e pela natureza de PoC (§4.8).

**BLoC:** `TermoCubit` → `NaoAceito | Aceito(DateTime)`. Persistido em `hive_ce`.

```
┌──────────────────────────────────────────┐
│ Antes de começar                         │  25/600
│                                          │
│ Este aplicativo é uma prova de conceito  │  16/1.5
│ acadêmica. Ele não emite prescrição e    │
│ não substitui o julgamento do médico     │
│ veterinário responsável.                 │
│                                          │
│ ▌ As respostas são geradas a partir de   │  bloco `iodo`,
│ ▌ trechos de literatura recuperados      │  preenchimento sólido
│ ▌ automaticamente. Confira sempre a      │
│ ▌ fonte citada antes de qualquer conduta.│
│                                          │
│ Nenhum dado de tutor ou de paciente é    │
│ enviado ao servidor: identificações são  │
│ removidas no próprio aparelho.           │
│                                          │
│ [ Entendi e aceito ]                     │  botão pleno, metileno
└──────────────────────────────────────────┘
```

O botão só habilita após rolagem até o fim. O aceite grava data/hora — o painel de
telemetria exporta esse registro para o dossiê do CEP.

---

### 9. `/consulta` — Nova consulta *(tela principal)*

**Objetivo:** compor uma consulta clínica em **campos estruturados**, e não em texto
livre. Esta é uma decisão de segurança, não de conveniência: a sanitização de PII por
regex sobre texto livre é comprovadamente frágil, ao passo que campos estruturados
permitem garantir que nome de tutor, nome do animal e número de prontuário simplesmente
**nunca entram** na carga enviada (Regra inviolável nº 3).

**BLoC:** `ConsultaBloc`
**Eventos:** `EspecieAlterada`, `PesoAlterado`, `FarmacoAdicionado`, `FarmacoRemovido`,
`ComorbidadeAlternada`, `PerguntaAlterada`, `ConsultaEnviada`.
**Estados:** `Editando(formulario, valido) | Enviando | Falha(Failure)`.

```
┌──────────────────────────────────────────┐
│ Nova consulta                    ⌂  ⚙    │
│                                          │
│ Espécie                                  │  14, inkMuted
│ [  Canino  ][ ✓ Felino ]                 │  segmentado, alvo 48px
│                                          │
│ Peso                                     │
│ [ 4,2 ] kg                               │  teclado numérico, tabular
│                                          │
│ Fármacos em questão                      │
│ [ meloxicam        ×] [ furosemida  ×]   │  chips + autocomplete
│ [ + adicionar fármaco            ]       │  do dicionário local
│                                          │
│ Condições relevantes                     │
│ [ ✓ insuficiência renal crônica ]        │  toggles do vocabulário
│ [   hepatopatia ] [   gestação ]         │  controlado
│ [   epilepsia ]   [   raça MDR1 ]        │
│                                          │
│ Pergunta                                 │
│ Não inclua nomes de tutores, de animais  │  14, inkMuted
│ ou números de prontuário.                │
│ ┌──────────────────────────────────────┐ │
│ │ É seguro repetir meloxicam neste     │ │
│ │ paciente?                            │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ [ Consultar a literatura ]               │
└──────────────────────────────────────────┘
```

**Validação:** espécie e pergunta obrigatórias; peso obrigatório quando a pergunta é
posológica; ao menos um fármaco recomendado (aviso, não bloqueio).

**Sanitização (executada em `ConsultaEnviada`, antes de sair do dispositivo):**

```dart
/// Mascara PII em campos estruturados e faz uma varredura defensiva
/// sobre o texto livre da pergunta. A varredura é best-effort e
/// NÃO substitui a estruturação dos campos — ver CLAUDE.md §4.3.
String sanitizarPergunta(String entrada) => entrada
    .replaceAll(RegExp(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'), '[CPF]')
    .replaceAll(RegExp(r'\b\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b'), '[TELEFONE]')
    .replaceAll(RegExp(r'(?i)\b(tutor|tutora|propriet[áa]rio|respons[áa]vel)\s*:?\s*[^\n,;.]+'), r'$1: [REMOVIDO]')
    .replaceAll(RegExp(r'(?i)\b(paciente|animal|nome)\s*:?\s*[^\n,;.]+'), r'$1: [REMOVIDO]')
    .replaceAll(RegExp(r'(?i)\b(prontu[áa]rio|registro|ficha)\s*n?[ºo°]?\s*[\w-]+'), r'$1: [REMOVIDO]');
```

O texto efetivamente enviado é exibido ao usuário em um expansor `Ver o que será
enviado` — transparência que sustenta a afirmação de privacidade do TCC §4.6 e serve de
evidência para o CEP.

**Roteamento do `thinking_level`** (TCC §3.2d): o app envia uma dica de complexidade —
`complexidade: "alta"` quando há dois ou mais fármacos ou uma comorbidade marcada;
`"baixa"` para consulta posológica simples. A decisão final é do back-end.

---

### 10. `/consulta/:id` — Resposta

**Objetivo:** exibir a resposta em streaming com proveniência visível. É aqui que a
tese vira interface.

**BLoC:** `RespostaBloc`
**Estados:** `Recuperando(chunks?) | Transmitindo(paragrafos, ttftMs) |
Concluida(RespostaClinica, telemetria) | SemEvidencia(consulta) | Falha(Failure) |
ExibindoCache(RespostaClinica)`.

```
┌──────────────────────────────────────────┐
│ ←  Meloxicam · felino · 4,2 kg           │  resumo da consulta
│                                          │
│ ██████████████████████████████████████   │  ← bloco `contra`, sólido,
│ █ CONTRAINDICAÇÃO RELATIVA             █ │     canto 0, texto branco
│ █ Uso repetido de meloxicam em gatos   █ │     promovido ao topo
│ █ foi associado a falência renal.      █ │
│ ██████████████████████████████████████   │
│                                          │
│ ┃① O meloxicam é um AINE inibidor      │  ┃ = trilho `ancorado`
│ ┃  preferencial de COX-2, com meia-vida │  texto em Plex Sans
│ ┃  prolongada em felinos.               │
│ ┃                                       │
│ ┃② Em pacientes com função renal        │
│ ┃  comprometida, a inibição de          │
│ ┃  prostaglandinas reduz a perfusão     │
│ ┃  renal, ampliando o risco.            │
│ ┃                                       │
│ ╏  A conduta depende do estágio IRIS.   │  ╏ = trilho hachurado
│ ╏  sem lastro documental                │  rótulo 12, `iodo`
│                                          │
│ ─────────────────────────────────────    │
│ Evidência recuperada                     │  14, inkMuted
│                                          │
│ ① "O uso repetido de meloxicam em        │  ← Plex Serif:
│    gatos foi associado a falência        │     texto do acervo
│    renal e óbito."                       │
│    Spinosa et al. (2017), cap. 22        │  12, inkMuted
│    [ Ver trecho completo ]               │
│                                          │
│ ② Bula — meloxicam 0,5 mg/mL             │
│                                          │
│ ─────────────────────────────────────    │
│ Confiança alta · gemini-3.8-flash        │  12, inkMuted
│ 1,4 s até o primeiro token · 5,2 s total │
│                                          │
│ [ Salvar ]  [ Nova consulta ]            │
└──────────────────────────────────────────┘
```

**Estado `Recuperando`:** nunca um spinner mudo. Texto que informa a etapa —
`Buscando na literatura…` → `12 trechos recuperados. Redigindo…`. Isso ocupa
honestamente o piso de deliberação interna do modelo, que não pode ser suprimido
(`thinking_level` mínimo é `low`; TCC §1.4 H2).

**Regras de segurança da tela:**

1. `alertaSeguranca` renderiza **antes** do primeiro parágrafo, sempre. Nunca no rodapé.
2. Nenhum valor de dose é exibido fora de um parágrafo com `chunkIds` não vazio.
3. Alerta nunca depende só de cor: bloco `contra` traz a palavra
   `CONTRAINDICAÇÃO`; bloco `iodo`, a palavra `CAUTELA`.
4. Resposta vinda do cache exibe um selo permanente:
   `Resposta armazenada em 12/03 · pode estar desatualizada`. Cache nunca se disfarça
   de resposta nova.
5. O rodapé sempre carrega a versão do modelo e a data (TCC §4.7).
6. Seleção e cópia do texto ficam habilitadas; o texto copiado **inclui as citações**.

---

### 11. `/evidencia/:chunkId` — Trecho recuperado

**Objetivo:** mostrar o trecho literal que sustenta a afirmação. Abre como
`DraggableScrollableSheet` a partir da âncora, sem perder o contexto da resposta.

**BLoC:** `EvidenciaCubit` → `Carregando | Carregado(Citacao) | Falha`.

Conteúdo: trecho completo em **IBM Plex Serif**, com o intervalo citado destacado por
fundo `ancorado` a 12% de opacidade; abaixo, os metadados (fonte, capítulo, página,
`chunk_id`) e a pontuação de recuperação (`similaridade`, `bm25`, `rrf`). Mostrar as
três pontuações é deliberado: é o que permite ao avaliador humano do painel julgar
*por que* aquele trecho apareceu — insumo direto da dimensão *Relevância do Contexto*
(TCC §4.4).

---

### 12. `/historico` — Consultas anteriores

**Objetivo:** acesso offline às respostas em cache (`hive_ce`), sustentando H2 do TCC.

**BLoC:** `HistoricoBloc` → `Carregando | ComItens(List<ResumoConsulta>) | Vazio | Falha`.

Lista densa, sem cartões: uma linha por consulta com fármacos, espécie, data e um ponto
colorido indicando se houve alerta de segurança. Deslizar para a esquerda remove.
Cabeçalho fixo mostra `⦿ offline — exibindo respostas salvas` quando
`connectivity_plus` reporta ausência de rede.

**Estado vazio:** `Nenhuma consulta salva ainda.` + `[ Fazer a primeira consulta ]`.
Convite à ação, não decoração.

---

### 13. `/ajustes` — Ajustes

**BLoC:** `AjustesCubit`.

Seções: endereço do back-end e chave do cliente; nível de raciocínio (`automático` /
`low` / `medium` / `high` — o modo manual existe para o protocolo experimental);
tamanho e limpeza do cache; `Modo pesquisador` (revela a telemetria); versão do app,
do modelo e do índice do corpus; reexibição do termo de uso.

A chave da API do Gemini **não aparece aqui** — ela vive apenas no back-end.

---

### 14. `/telemetria` — Painel do pesquisador

**Objetivo:** instrumentar a coleta prevista em TCC §4.4a sem depender de ferramenta
externa. Visível apenas com `Modo pesquisador` ativo.

**BLoC:** `TelemetriaCubit` → `Carregando | Consolidada(Estatisticas) | Vazia`.

Exibe, por condição de rede (Wi-Fi / 4G / 5G): n de consultas, TTFT em P50/P90/P99,
tempo total, tempo de busca vetorial, banda e custo acumulado em USD. Uma linha de
referência marca o limiar de **2 s** do Quadro 1. Botão `Exportar CSV` (`share_plus`)
para levar os dados à análise estatística.

Gráfico: barras horizontais simples de percentis. Sem gradiente, sem animação de
entrada.

---

### 15. Estados transversais

| Estado | Quando | Tratamento |
|---|---|---|
| **Sem evidência** | `nivelConfianca == semEvidencia` | Título `Sem evidência suficiente no acervo.` + explicação de que o sistema deixou de responder deliberadamente + `[ Refazer a pergunta ]`. **Isto é sucesso, não erro** — apresente sem cor de falha. |
| **Offline com cache** | sem rede, consulta já respondida | Serve o cache com selo de data. |
| **Offline sem cache** | sem rede, consulta nova | `Sem conexão. Esta consulta precisa da rede.` + acesso ao histórico. |
| **Tempo esgotado** | > 30 s sem `fim` | Mantém o texto parcial, marca `resposta incompleta`, oferece `Tentar de novo`. Nunca descarta texto já exibido. |
| **Falha do servidor** | 5xx / erro do SDK | Mensagem do que aconteceu e o que fazer. Sem código cru, sem pedido de desculpas. |
| **Limite de uso** | 429 | `A cota da API foi atingida. Tente em alguns minutos.` |

---

## Parte IV — Implementação

### 16. Estrutura de pastas (feature-first)

```
app/lib/
├── core/
│   ├── di/injection.dart
│   ├── error/failures.dart
│   ├── network/{dio_client.dart, sse_parser.dart, connectivity.dart}
│   ├── privacy/sanitizer.dart
│   ├── telemetry/{telemetry_recorder.dart, ttft_stopwatch.dart}
│   └── theme/{tokens.dart, app_theme.dart, typography.dart}
├── features/
│   ├── termo/{data,domain,presentation}
│   ├── consulta/{data,domain,presentation}
│   ├── resposta/{data,domain,presentation}
│   ├── historico/{data,domain,presentation}
│   ├── ajustes/{data,domain,presentation}
│   └── telemetria/{data,domain,presentation}
├── shared/widgets/
│   ├── trilho_evidencia.dart        ← o widget central
│   ├── ancora_citacao.dart
│   ├── bloco_alerta.dart
│   ├── trecho_serifado.dart
│   ├── selo_cache.dart
│   └── campo_farmaco.dart
└── main.dart
```

### 17. Tema

```dart
abstract final class Tokens {
  static const paper     = Color(0xFFF4F6F4);
  static const surface   = Color(0xFFFFFFFF);
  static const ink       = Color(0xFF1A211F);
  static const inkMuted  = Color(0xFF5A6663);
  static const rule      = Color(0xFFD3DAD6);
  static const metileno  = Color(0xFF17506B);
  static const ancorado  = Color(0xFF2C6248);
  static const iodo      = Color(0xFFA65A15);
  static const contra    = Color(0xFF96131F);

  static const espaco = [4.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0];
}

final appTheme = ThemeData(
  scaffoldBackgroundColor: Tokens.paper,
  colorScheme: const ColorScheme.light(
    primary: Tokens.metileno,
    error: Tokens.contra,
    surface: Tokens.surface,
    onSurface: Tokens.ink,
  ),
  textTheme: TextTheme(
    displaySmall: GoogleFonts.ibmPlexSans(fontSize: 31, height: 1.2, fontWeight: FontWeight.w600),
    titleLarge:   GoogleFonts.ibmPlexSans(fontSize: 20, height: 1.3, fontWeight: FontWeight.w600),
    bodyLarge:    GoogleFonts.ibmPlexSans(fontSize: 16, height: 1.5),
    bodySmall:    GoogleFonts.ibmPlexSans(fontSize: 12, height: 1.4, color: Tokens.inkMuted),
  ),
);

/// Estilo exclusivo dos trechos recuperados do acervo.
final estiloEvidencia = GoogleFonts.ibmPlexSerif(fontSize: 16, height: 1.6, color: Tokens.ink);

/// Valores de dose: figuras tabulares.
final estiloDose = GoogleFonts.ibmPlexSans(
  fontSize: 16,
  fontFeatures: const [FontFeature.tabularFigures()],
);
```

### 18. Acessibilidade — piso de qualidade

- Contraste mínimo 4.5:1 em texto de corpo; os pares `ink`/`paper` e branco/`contra`
  já satisfazem.
- Alvos de toque ≥ 48×48 dp.
- Risco nunca comunicado só por cor: sempre há palavra (`Contraindicação`, `Cautela`) e
  forma (sólido vs. hachurado).
- `Semantics` nas âncoras: `"citação 1, Spinosa 2017, capítulo 22, abrir trecho"`.
- Layout funcional até `textScaleFactor` 2.0 — trilho e blocos não podem quebrar.
- Animações desativadas quando o sistema pede.

### 19. Testes da camada de apresentação

- `bloc_test` para cada BLoC: sequência de estados no caminho feliz, no caminho
  `semEvidencia`, com queda de rede e com resposta em cache.
- Teste de widget do `TrilhoEvidencia`: parágrafo com citação renderiza segmento sólido
  e âncora; parágrafo sem citação renderiza hachura e o rótulo `sem lastro documental`.
- Teste de widget: dose presente em parágrafo sem `chunkIds` **não** é renderizada.
- Teste de unidade do `sanitizarPergunta` com os seis cenários do Quadro 2 acrescidos de
  PII sintética.
- Teste do `TtftStopwatch`: o cronômetro para no primeiro evento `paragrafo` com texto, não no
  primeiro evento do stream (`recuperacao`).
- Golden tests das telas 9 e 10 em 380 px e em `textScaleFactor` 2.0.

Cobertura mínima de 70% incide sobre `domain/` e `data/` (Quadro 1 do TCC); a
apresentação é coberta por `bloc_test` e golden tests sem limiar formal.

---

## Parte V — Evolução visual e telas novas *(implementada em 05/11/2026; decisões do autor no §27)*

Escopo: **só a camada de apresentação**. Nada em `domain/`, `data/`, BLoCs existentes,
telemetria, contrato com o back-end ou back-end. Sem login, cadastro nem coleta de dados
pessoais. As telas novas ficam **fora do fluxo de consulta medido** (não tocam
`TtftStopwatch` nem `RegistroTelemetria`). Os textos conferidos por `ROTEIRO_MODO_AVIAO.md`
não mudam. Contraste WCAG AA (texto 4,5:1; componentes e ícones 3:1) e alvos ≥ 48 dp.

**Decisões do autor (§27)** — esta parte emenda o §4 e o §2 nos pontos marcados; as
emendas foram aprovadas e implementadas.

### 20. `/` — Abertura com marca *(emenda ao §7)*

Marca (símbolo + `VetFarmaco`) uma vez por execução do app, enquanto o `BootstrapCubit`
inicializa. Sem atraso artificial: ao terminar a inicialização, o app segue; a marca fica
no mínimo 300 ms (para não piscar); a marca nunca atrasa o app além disso, e a
inicialização, se demorar, é que manda. Ilustração discreta em traço (§26).
`Preparando o acervo local` continua se a inicialização passar de 400 ms. *Fade* de
120 ms; `disableAnimations` o pula. `FalhaConfig` não muda.

### 21. `/introducao` — Primeiro uso

Depois do termo de uso, uma única vez, **pulável** (`Pular`, 48 dp, em todos os cartões).
Três cartões em `PageView` com indicador de página e `Próximo` / `Começar`:

1. **Consulta** — espécie, peso, fármacos e pergunta; a resposta sai só dos trechos recuperados. Cada consulta é independente.
2. **Trilho de evidência** — trilho sólido + citação numerada = parágrafo com citação; tocar o número abre o trecho em serifa.
3. **Modo offline** — respostas salvas ficam no aparelho; consulta nova precisa de rede.

Visual de cada cartão: cão em traço (cartão 1), exemplo do próprio trilho de evidência
(cartão 2) e gato em traço (cartão 3) (§26). Destino ao concluir ou pular: `/consulta`.
Não coleta nada e não reaparece.

### 22. `/sobre` — Sobre o aplicativo *(acessível por Ajustes)*

Item `Sobre o aplicativo` em Ajustes, abaixo de `Telemetria das consultas`. Seções:

- **De onde vêm as respostas** — Spinosa et al. (2017) e seis bulas (carprofeno, fenobarbital, insulina NPH, ivermectina, meloxicam e tramadol); cada afirmação traz a citação do trecho de origem.
- **Ferramenta de apoio** — prova de conceito acadêmica; não emite prescrição e não substitui o julgamento clínico do médico veterinário.
- **Privacidade** — identificações de tutor e animal são removidas no próprio aparelho antes do envio; o app não tem login nem cadastro. Limite: nomes próprios em texto livre não são reconhecidos de forma confiável (ver `relatorio_metodologia.md`), por isso a tela pede para não os incluir.
- **Limites do sistema** — acervo pequeno (sete documentos); parte das bulas é de uso humano ou de outra espécie; sem sustentação no acervo o sistema diz `Sem evidência suficiente no acervo.`; cada consulta é independente (sem memória de conversa); consulta nova exige rede.
- **Versões** — app, modelo e índice, só leitura.

O texto final passa por revisão do autor antes de entrar no código.

### 23. Refinamentos visuais das demais telas

Sem mudar comportamento, rotas, textos do roteiro nem estados: hierarquia tipográfica
(títulos de seção 20/600, rótulos 14/600, metadados 12) e espaçamento na escala de 4;
estados vazios e de carregamento com texto + ilustração/esqueleto, sem *spinner* solto;
**tema escuro**:

| Token | Claro | Escuro | Contraste do escuro |
|---|---|---|---|
| `paper` | `#F4F6F4` | `#101614` | — |
| `surface` | `#FFFFFF` | `#1A2220` | — |
| `ink` | `#1A211F` | `#E6ECE9` | 15,3 |
| `inkMuted` | `#5A6663` | `#A2B0AA` | 8,1 |
| `rule` | `#D3DAD6` | `#3A4743` | decorativo |
| `metileno` | `#17506B` | `#86C1DE` (texto/ação); botão com texto `paper` | 9,3 |
| `ancorado` | `#2C6248` | `#86C7A2` | 9,3 |
| `iodo` | `#A65A15` | `#E3A862` (texto/trilho); bloco sólido igual ao claro | 8,8 |
| `contra` | `#96131F` | `#F28B93` (texto/trilho); bloco sólido igual ao claro | 7,8 |

Blocos de alerta sólidos mantêm o preenchimento do tema claro com texto branco (5,1:1 em
`iodo`, 8,7:1 em `contra`).

### 24. `/consulta/:id` — Resposta em formato de conversa *(emenda aos §4 e §10)*

A rota, os estados do `RespostaCubit` e os eventos SSE **não mudam**; muda só a
composição. Uma consulta = uma troca: pergunta e resposta. Não há campo de resposta em
continuação.

```
┌──────────────────────────────────────────┐
│ ▌ Resposta armazenada em 04/11 · …       │  selo (só do cache), fixo
│ ■ CONTRAINDICAÇÃO                        │  alerta, fixo no topo
│ ■ O paracetamol é contraindicado …       │  (sólido, canto 0)
├──────────────────────────────────────────┤
│          ┌───────────────────────────┐   │
│          │ Posso dar paracetamol …   │   │  balão do usuário, à direita
│          │ [felino] [4,2 kg] [parac.]│   │  chips: espécie, peso, fármacos
│          └───────────────────────────┘   │
│ (◉) ▌ A administração de paracetamol …   │  avatar = ícone do app
│     ▌                          (1) (2)   │  trilho + citações numeradas
│     ▌ O quadro de intoxicação …    (3)   │
│                                          │
│ Confiança alta · gemini-… · 05/11 · ▾    │  rodapé recolhível
│ ──────────────────────────────────────── │
│ Cada consulta é independente: o sistema  │
│ não guarda a conversa.                   │
│ [ Salvar ] [ Copiar com citações ]       │
│ [ Nova consulta ]                        │
└──────────────────────────────────────────┘
```

- **Pergunta (balão à direita):** é texto do usuário, então pode ser balão (raio 12, canto da base 2; fundo `metileno`, texto branco). Mostra a pergunta **já sanitizada** (a de `CorpoConsulta`, a que foi enviada), nunca o texto cru. Abaixo, chips de espécie, peso e fármacos (e comorbidades, se houver; só leitura, sem toque).
- **Resposta (à esquerda, sem balão):** avatar de 32 dp com o ícone do app e, ao lado, a coluna de parágrafos **com o trilho de evidência do §3** (sólido `ancorado`; hachurado `iodo` + `sem lastro documental`). O texto do modelo é Plex Sans; serifa só na folha de evidência. O trilho e a tipografia carregam a diferença entre afirmação e evidência; por isso a resposta **não** vira bolha de chat (§4).
- **Citações:** chips numerados ao fim de cada parágrafo (28 dp visual, 48 dp de toque, `Semantics` do §18), que abrem a folha de evidência.
- **Alerta:** um cartão único no topo da resposta (primeiro item da lista), com fundo levemente tingido pelos tokens do tema (`contra` para contraindicação, `iodo` para cautela, a 10% sobre o fundo; nunca vermelho puro), barra de 4 dp à esquerda, o mesmo raio de 12 dp dos balões e chips e sem sombra. O cabeçalho aparece uma vez: ícone da gravidade mais alta (círculo com exclamação para contraindicação, triângulo de aviso para cautela) e o título, `Alerta de segurança` ou `N alertas de segurança`, em `titleSmall` seminegrito. Os itens ficam ordenados por gravidade, com a contraindicação primeiro (dentro da mesma gravidade, na ordem de chegada). Cada item traz só o rótulo da gravidade em caixa normal (`Contraindicação` ou `Cautela`), com o ícone dela quando há mais de um alerta (com um só, o ícone fica no cabeçalho e a linha da gravidade tem só o rótulo), o texto literal do alerta em `bodyMedium`, completo, sem truncar, sem maiúsculas, exclamação, emoji nem animação piscando, e, no fim, a linha `Fonte:` com os chips numerados daquele alerta (os mesmos das citações, em tamanho menor de 22 dp e área de toque de 48 dp; abrem a folha de evidência e aparecem quando o evento `citacoes` chega). Entra com o mesmo *fade* dos parágrafos. Vários alertas ficam no mesmo contêiner, separados por divisor. Quando o usuário rola além do cartão, aparece uma barra compacta fixa, `1 alerta de segurança · ver` (ou `N alertas…`), de 48 dp, com o mesmo raio de 12 dp e a cor da gravidade mais alta, que rola de volta ao cartão: o alerta nunca fica escondido sem um caminho de um toque. Contraste ≥ 4,5:1 nos dois temas, conferido por teste. *(Hoje o estado da resposta guarda um alerta por resposta; o layout de vários alertas fica pronto no widget.)*
- **Espera:** esqueleto (3 barras com brilho de 1,2 s) no lugar do primeiro parágrafo, até o evento `paragrafo` com texto. Acima, um indicador de duas etapas ligado aos estados reais: etapa 1 `Buscando na literatura…` até o evento `recuperacao`; etapa 2 `N trechos recuperados. Redigindo…` até o primeiro `paragrafo`. Os dois textos são exatamente os do roteiro. O esqueleto some em 120 ms quando o parágrafo chega. Com `disableAnimations`, o esqueleto fica estático.
- **Parágrafos:** cada um entra com *fade* + deslize de 8 dp em 180 ms, ao chegar. Sem efeito de digitação. A âncora trava no trilho em 120 ms (§2).
- **Rodapé recolhível:** a linha `Confiança … · <modelo> · <data> · tempos` do roteiro **continua visível por padrão**, idêntica à de hoje; o recolhível só abre detalhes além dela. Se `EventoFim` não tiver detalhe extra, o rodapé fica sem recolhimento.
- **Fim da consulta:** divisor, a frase `Cada consulta é independente: o sistema não guarda a conversa.` e as ações atuais (`Salvar`/`Salva`, `Atualizar`, `Copiar com citações`, `Nova consulta`, mesmos textos). Sem campo de texto.
- **Outros estados** (`Sem evidência suficiente no acervo.`, `Sem conexão. Esta consulta precisa da rede.`, falha, tempo esgotado): mesmos textos e botões; aparecem na coluna da resposta. **Sem ilustração** (§26).
- **Resposta aberta do histórico:** mesmo layout, sem esqueleto, com o selo de cache.
- Golden tests em 380 px e em `textScaleFactor` 2.0 (balão ocupa a largura toda; chips quebram linha).

### 25. Movimento *(emenda ao §2)*

Hoje: um único momento orquestrado, o streaming. Proposta: acrescentar, todos ≤ 250 ms e
desligados por `MediaQuery.disableAnimations`:

| Onde | Movimento |
|---|---|
| Entre telas | transição de 220 ms (deslize curto + *fade*); a resposta continua iniciando a consulta em paralelo, como hoje |
| Histórico | itens entram em cascata (40 ms entre itens, no máximo 8 itens, só na primeira carga) |
| Folha de evidência | desliza de baixo (já é *bottom sheet*; só se define a duração, 220 ms) |
| Resposta | os da §24 |

**Telemetria:** nenhuma animação pode atrasar o registro dos tempos. Regras de
implementação: (1) animação é só de widget, disparada pelo estado já emitido; (2) nunca
se espera o fim de uma animação para consumir evento, emitir estado ou parar o
`TtftStopwatch`; (3) parágrafos não entram em fila nem em escalonamento: o texto está na
árvore de widgets no mesmo quadro em que o estado muda, com a animação rodando por cima;
(4) teste de widget garante o item 3.

**Pacotes:** `skeletonizer`/`shimmer` e `flutter_animate` não estão no `pubspec.yaml` nem
na pilha do `CLAUDE.md` §3. Recomendação: implementar com `FadeTransition`,
`SlideTransition` e um brilho próprio (≈ 40 linhas), sem dependência nova, e tratar
`disableAnimations` num único ponto. Se o autor preferir os pacotes, a versão é fixada na
implementação, e `flutter_animate` precisa do mesmo tratamento de `disableAnimations`.

### 26. Ilustrações

Desenho em traço de cão e gato, discreto, em `inkMuted` (nunca em `iodo`, `contra` ou
`ancorado`: cor de risco e de evidência é semântica, §2). Só em **abertura, introdução e
estados vazios** (histórico vazio). **Nunca** em resposta, alerta, `Sem evidência`,
`Sem conexão`, falha ou tempo esgotado: a ilustração não pode amenizar um estado clínico.
Sem personagens conhecidos.

Origem: **arte original do projeto**, em SVG (`app/assets/arte_fonte/`), gerada por
`app/tool/gerar_arte.py` e exportada para PNG com fundo transparente, em 1x, 2x e 3x por tema, por
`app/tool/exportar_png.py` (o Flutter não desenha SVG sem pacote extra). Estilo: formas preenchidas, dois
ou três tons e sombras suaves; paleta `metileno`, `paper`, verde `#86C7A2` e areia de apoio. Autoria e
licença de cada imagem e da fonte em `docs/CREDITOS_ARTE.md`.

### 27. Decisões do autor (05/11/2026) e pendências

**Decididas:**

1. **Chat × §4:** balão **só para a pergunta**; a resposta fica **sem balão**, com o trilho de evidência (§24).
2. **Sem pacotes novos:** animação implícita do Flutter e brilho próprio; nada de `skeletonizer`, `shimmer` ou `flutter_animate` (§25).
3. **Marca:** o nome é `VetFarmaco`. Ícone original em SVG: cápsula estilizada com marca de pata, nas cores do design system (fundo `metileno`, cápsula em `paper` e verde-evidência claro `#86C7A2`, pata em `metileno`). Depois de aprovado o desenho, os ícones do Android saem de `flutter_launcher_icons` como **dependência de desenvolvimento**, e o mesmo desenho serve de avatar (§24) e de marca na abertura (§20), sem pacote de SVG (o desenho é reproduzido em `CustomPainter`).
4. **Introdução «mostrar uma vez»:** módulo novo `onboarding`, **só com arquivos novos**, com a flag numa **caixa nova do `hive_ce`**; nenhum arquivo existente de `domain/`, `data/` ou BLoC é alterado.
5. **Campanha:** ainda não começou; as medições até agora foram exploratórias. A campanha rodará inteira com a versão nova da interface; não há mistura de versões nos dados.
6. **Demais itens:** seguem as recomendações desta Parte V (alerta fixo no topo com altura máxima de 35%; rodapé com a linha do roteiro sempre visível e recolhível só para detalhes extras).
7. **Ilustrações e ícone:** passam por pré-visualização aprovada antes de entrar no app.

**Aprovado e implementado:** o ícone (com versão só-cápsula até 32 dp) e as ilustrações de
cão e gato (olhos fechados e sorridentes, orelhas por fora do contorno; traço `#A2B0AA` no
escuro), registrados em `docs/CREDITOS_ARTE.md`.

### 28. `/inicio` — Início *(design v2, implementada)*

Tela inicial depois da abertura e da introdução. Cabeçalho com o ícone, `VetFarmaco`, a frase
`Apoio à decisão farmacológica para cães e gatos.` e a ilustração pequena (`inicio_cabecalho`); botão
`Nova consulta`; atalhos para `Histórico`, `Ajustes` e `Sobre o aplicativo`; aviso de prova de conceito.

- **Navegação:** abertura (`ParaConsulta`) e introdução (concluída, pulada ou já vista) levam a `/inicio`.
  `Nova consulta` empilha `/consulta` (voltar retorna ao Início); os atalhos empilham as outras telas.
- **Fora do caminho medido:** o caminho medido começa em `Nova consulta` (`/consulta`) e vai até o primeiro
  parágrafo validado; essa tela continua **sem imagem e sem animação**. Teste em
  `test/features/consulta/presentation/consulta_page_test.dart`.
- **Fonte:** IBM Plex Sans (interface e texto do modelo) e IBM Plex Serif (só os trechos do acervo),
  arquivos oficiais embarcados em `app/assets/fonts/`; escala 12 / 14 / 16 / 20 / 25 / 31, corpo 16/24.
- **Ilustrações:** abertura (cão e gato com o ícone da marca), introdução (cartão 1: cão e gato com um
  livro; cartão 3: celular com respostas salvas, selo de data e símbolo de «sem rede»), histórico vazio
  (gato dormindo sobre livros), faixa do `Sobre` e cabeçalho do Início. Nenhuma na resposta, no alerta, em
  `Sem evidência`, `Sem conexão` nem na nova consulta.
