# ARCHITECTURE.md — Camadas e contratos

Materializa o TCC §3.6 (Clean Architecture, Martin 2018; Orlova et al. 2024, caps. 6–8).

Este documento descreve o que o código faz hoje. O diagrama em Mermaid está em
`docs/img/arquitetura.mmd`; as evidências de cobertura e da Regra de Dependência estão em
`docs/evidencias_oe2_oe3.md`.

## 1. Visão do sistema

```
┌─────────────────────────────────┐          ┌──────────────────────────────────┐
│  App Flutter (Android)          │  HTTPS   │  FastAPI (Cloud Run)             │
│  ┌───────────────────────────┐  │  POST    │  ┌────────────────────────────┐  │
│  │ presentation (Cubit/BLoC) │  │ /consulta│  │ POST /consulta (SSE)       │  │
│  ├───────────────────────────┤  │ ───────► │  │  X-API-Key                 │  │
│  │ domain (Dart puro)        │  │          │  ├────────────────────────────┤  │
│  │  MontarCorpoConsulta ─────┼──┼ filtro   │  │ Busca híbrida (em paralelo)│  │
│  │  └ Sanitizador (interface)│  │ de PII   │  │  ├ pgvector (HNSW)         │  │
│  ├───────────────────────────┤  │ AQUI,    │  │  └ BM25 (bm25s)            │  │
│  │ data (RepositoryImpl)     │  │ antes    │  │  → RRF (k=60)              │  │
│  │  ├ RagRemoteSource (Dio)  │  │ do envio │  │ Gemini (gemini-3.8-flash)  │  │
│  │  └ caches em hive_ce      │  │          │  │ Validador de citações      │  │
│  └───────────────────────────┘  │ ◄─────── │  └────────────────────────────┘  │
└─────────────────────────────────┘   SSE    └───────────────┬──────────────────┘
                                     (eventos                │
                                      validados)  ┌──────────▼───────────┐
                                                  │ Supabase (Postgres)  │
                                                  │ pgvector + HNSW      │
                                                  └──────────────────────┘
```

Fluxo de uma consulta:

1. A tela monta um `FormularioConsulta`; o caso de uso `MontarCorpoConsulta` produz o
   `CorpoConsulta`, **sanitizando a pergunta no cliente** (§3).
2. `RealizarConsulta` entrega o corpo ao `RagRepository`; `RagRepositoryImpl` (data) chama
   `RagRemoteSource`, que faz `POST /consulta` via Dio com `ResponseType.stream` e o
   cabeçalho `X-API-Key`.
3. No back-end, as buscas vetorial (pgvector) e lexical (BM25) rodam em paralelo e são
   fundidas por RRF (k=60); o Gemini gera a resposta sobre os trechos recuperados.
4. O validador checa as citações e os parágrafos. Só o que passa é enviado ao app por SSE,
   na ordem `recuperacao`, `paragrafo`*, `citacoes`, `alerta`?, `fim` (ou `erro` em
   qualquer ponto). Nunca há evento com token bruto do modelo.
5. O app converte os eventos em `EventoResposta`; o `RespostaCubit` os consome e pode
   guardar a resposta no cache local (`hive_ce`).

A chave da API do Gemini e a `service_role` do Supabase existem **somente** no back-end.

## 2. Regra de Dependência

O código-fonte só aponta para dentro. Concretamente, em `app/lib/features/*/`:

| Camada | Pode importar | Nunca importa |
|---|---|---|
| `domain/` | outros `domain/`, `core/error`, `fpdart`, `equatable`, `crypto`, Dart SDK | Flutter, `flutter_bloc`, `dio`, `hive_ce`, `get_it`, `injectable`, `data/`, `presentation/` |
| `data/` | `domain/`, `core/`, `dio`, `hive_ce` | `presentation/` |
| `presentation/` | `domain/`, `flutter_bloc`, Flutter | `data/` |

A apresentação depende de **casos de uso**, nunca de repositórios concretos. A inversão
acontece porque a interface do repositório mora em `domain/repositories/` e a
implementação em `data/repositories/`. As implementações são ligadas às interfaces na
injeção de dependência (`core/di/`, `get_it` + `injectable`).

Na última verificação (ver `docs/evidencias_oe2_oe3.md`), os 42 arquivos de `domain/`
não tinham nenhum import proibido, e nenhum arquivo de `presentation/` importava `data/`.

Verificação automatizada (job `regra-de-dependencia` do CI):

```bash
# Falha se o domínio importar framework
! grep -rEn "import 'package:(flutter|dio|hive_ce|supabase)" app/lib/features/*/domain/
```

O CI cobre apenas esses quatro pacotes. O restante da tabela (por exemplo `flutter_bloc`
ou `data/` dentro de `domain/`) foi verificado por script, não pelo CI.

## 3. Contratos do domínio

Os arquivos ficam por feature (`consulta`, `resposta`, `historico`, `telemetria`, …).
Trechos reais, abreviados:

```dart
// consulta/domain/sanitizador.dart
abstract interface class Sanitizador {
  String sanitizar(String entrada);
}

// consulta/domain/corpo_consulta.dart
/// Monta o CorpoConsulta a partir do formulário, sanitizando a pergunta.
class MontarCorpoConsulta {
  const MontarCorpoConsulta(this._sanitizador);
  final Sanitizador _sanitizador;

  CorpoConsulta call(FormularioConsulta f) => CorpoConsulta(
    pergunta: _sanitizador.sanitizar(f.pergunta.trim()),   // PII removida AQUI
    complexidadeDica: f.complexidade,
    especie: f.especie,
    pesoKg: f.erroPeso == null ? f.peso : null,
    farmacos: f.farmacos,
    comorbidades: f.comorbidades.toList()..sort(),
  );
}

// resposta/domain/repositories/rag_repository.dart
abstract interface class RagRepository {
  /// Envia a consulta (já sanitizada) e emite os eventos validados.
  Stream<Either<Failure, EventoResposta>> consultar(CorpoConsulta corpo);
}

// resposta/domain/usecases/realizar_consulta.dart
class RealizarConsulta {
  const RealizarConsulta(this._repositorio);
  final RagRepository _repositorio;

  Stream<Either<Failure, EventoResposta>> call(CorpoConsulta corpo) =>
      _repositorio.consultar(corpo);
}

// historico/domain/repositories/resposta_cache_repository.dart
abstract interface class RespostaCacheRepository {
  Future<Either<Failure, Unit>> salvar(RespostaSalva resposta);
  Future<Either<Failure, RespostaSalva?>> buscar(String chave);
  Future<Either<Failure, List<RespostaSalva>>> historico();
  Future<Either<Failure, Unit>> remover(String chave);
}
```

### Onde fica o filtro de dados pessoais

A sanitização acontece **no app, em `MontarCorpoConsulta` (domain), antes de qualquer
envio**. `RealizarConsulta` não sanitiza: recebe um `CorpoConsulta` que já é exatamente o
que o usuário viu em "Ver o que será enviado". O back-end recebe a pergunta já
sanitizada e não faz nova sanitização.

`Sanitizador` é uma interface do domínio; a implementação com regex, `SanitizadorRegex`,
fica em `core/privacy/` e é ligada na injeção de dependência. Assim, a política de
privacidade é regra de negócio (testável, sem Flutter) e não detalhe de infraestrutura.
O `Sanitizador` é uma varredura best-effort sobre texto livre (mascara CPF, telefone,
tutor, paciente e prontuário); a proteção principal é que tutor e nome do animal nem
existem como campos do corpo enviado, que é estruturado.

O contrato de consulta e a política de cache estão separados em dois repositórios:
`RagRepository` (rede) e `RespostaCacheRepository` (`hive_ce`). Outros repositórios de
`domain/` cuidam de configuração, vocabulário, onboarding, termo, ajustes e telemetria,
cada um com sua implementação em `data/`.

## 4. Falhas

```dart
sealed class Failure extends Equatable { final String mensagem; }

final class FalhaRede      extends Failure {}  // sem conectividade
final class FalhaTempo     extends Failure {}  // timeout
final class FalhaServidor  extends Failure {}  // 5xx
final class FalhaCota      extends Failure {}  // 429
final class FalhaCache     extends Failure {}  // hive_ce
final class FalhaContrato  extends Failure {}  // resposta fora do schema
final class FalhaValidacao extends Failure {}  // entrada inválida (ex.: endereço do back-end)
final class FalhaCitacao   extends Failure {}  // chunk_id inexistente ⇒ invalida tudo
```

Definidas em `core/error/failures.dart` (Dart puro, só `equatable`). A camada de dados
converte exceções em `Failure` (`core/network/dio_failure_mapper.dart` para erros de rede).

`FalhaCitacao` é específica desta pesquisa: se o modelo citar um `chunk_id` que não foi
recuperado, a resposta inteira é descartada. Isso é o oposto de degradar graciosamente —
e é intencional (TCC §1.3).

## 5. Camadas do back-end

```
backend/
├── app/
│   ├── main.py                  # FastAPI, middlewares, rotas
│   ├── config.py                # pydantic-settings; modelo_id vive aqui (TCC §4.7)
│   ├── api/
│   │   ├── consulta.py          # POST /consulta, resposta por SSE
│   │   ├── vocabulario.py
│   │   └── deps.py              # autenticação por X-API-Key
│   ├── rag/
│   │   ├── recuperacao.py       # orquestra vetorial + lexical em paralelo, pool Postgres
│   │   ├── retriever_vetorial.py  # pgvector
│   │   ├── retriever_lexical.py   # bm25s
│   │   ├── fusao.py             # RRF k=60
│   │   ├── roteador.py          # complexidade → thinking_level; detecção de fármacos
│   │   ├── composicao.py        # monta o prompt a partir da consulta estruturada
│   │   ├── gerador.py           # google-genai, streaming
│   │   ├── validador.py         # citações fantasma, doses, trechos literais
│   │   └── streaming.py         # eventos SSE, extração de parágrafos, telemetria
│   └── telemetry/logging.py     # structlog
├── etl/                         # extração, chunking, embeddings, carga
├── eval/                        # ragas_run, recall_at_k, scenarios.yaml, qrels
├── migrations/
└── tests/
```

Fluxo em `POST /consulta`: autentica (`X-API-Key`; 401 sem chave válida, 503 se a chave
não estiver configurada) → roteia → recupera (vetorial e lexical em paralelo, fusão RRF)
→ compõe o prompt → gera com o Gemini em streaming → valida → emite os eventos SSE.
Citações fantasma invalidam a resposta inteira; parágrafos reprovados no validador não
são emitidos.

O back-end **não** tem hoje uma camada `domain/` com *ports* (`Protocol`) separada: o
código fica em `app/rag/` e a orquestração depende diretamente dos módulos concretos. A
inversão de dependência por interfaces existe apenas no cliente.

## 6. Substituição do modelo (TCC §4.7)

`modelo_id` é lido de configuração (variável de ambiente, via `pydantic-settings`) e
usado pelo `gerador.py`. Trocar de `gemini-3.8-flash` para um sucessor exige alterar **um**
valor de configuração e nada mais. O registro `consulta_concluida` do back-end grava o
modelo usado (`modelo=modelo_id`), para que a migração possa ser tratada como variável
de confusão na análise.
