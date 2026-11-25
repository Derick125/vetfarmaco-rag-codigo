# VetFarmaco RAG — código

Código-fonte do TCC *"Inteligência Artificial Generativa na Farmacologia Veterinária:
Arquitetura de RAG Híbrido com LLM em nuvem e Clean Architecture em Flutter"*
(Derick de Oliveira Paiva, UniCatólica de Quixadá, 2026).

Este repositório existe para ser citado no TCC e reúne **só o código e a documentação técnica**.

É uma **prova de conceito acadêmica** de apoio à decisão farmacológica em clínica de
pequenos animais (cães e gatos). **Não emite prescrição e não substitui o julgamento do
médico veterinário.** O médico veterinário faz uma consulta; o back-end recupera trechos
do acervo por busca híbrida (semântica + lexical, fundidas por RRF com k = 60) e o modelo
de linguagem redige a resposta **somente** sobre os trechos recuperados, com citação
obrigatória de cada afirmação. Um validador confere as citações antes de qualquer texto
chegar ao usuário.

## Dados não incluídos (direitos autorais)

**Os dados processados não estão neste repositório por direitos autorais.** O acervo do
sistema é o livro de Spinosa et al. (2017) e seis bulas de medicamentos veterinários, todos
protegidos. Por isso, não há aqui:

- os PDFs do livro e das bulas;
- o texto extraído e os *chunks* (nem os embeddings derivados deles);
- o índice BM25;
- os arquivos de auditoria e as rodadas de geração, que reproduzem trechos do acervo;
- a rotulação do *gold set* de recuperação, que depende dos *chunks*.

Também ficam de fora, por serem dados da pesquisa, o CSV da telemetria e as respostas do painel
clínico. O que sobra é o código que os produz e os analisa. Quem tiver acesso legítimo às
fontes pode refazer o acervo com o ETL (`backend/etl/`), mas o resultado não é redistribuído.

Por isso, partes da documentação em `docs/` citam caminhos de `backend/data/` e de
`backend/scripts/`, que não existem aqui. Os testes usam só textos inventados (os trechos
dos fixtures imitam a estrutura dos trechos reais, sem copiá-los), e o
`docs/relatorio_metodologia.md` desta versão traz `[trecho omitido: direitos autorais]` no
lugar de cada citação literal do livro ou de bula; números, decisões e datas foram mantidos.
Os identificadores da implantação (projeto, URL e imagem) aparecem como `<...>`.

## Mapa do repositório

- **`backend/`** — back-end em Python 3.12 (FastAPI).
  - `app/rag/` — recuperação (vetorial, lexical, fusão), geração, validador e streaming.
  - `etl/` — extração e *chunking* do acervo; `migrations/` — esquema do Postgres/pgvector.
  - `eval/` — avaliações: `recall_at_k.py`, `ragas_run.py`, cenários, consultas e análises
    da telemetria e do painel (`analise_telemetria.py`, `analise_painel.py`).
  - `tests/` — testes do back-end (usam dados sintéticos).
- **`app/`** — cliente em Flutter (Clean Architecture); `app/test/` tem os testes.
- **`docs/`** — arquitetura, especificações do RAG, do banco e da interface, critérios de
  aceite, protocolo da telemetria e divergências entre o TCC e a documentação das ferramentas.

## Rodando

Configuração: copie `backend/.env.example` para `backend/.env` e preencha com as suas
próprias chaves. O `.env` não é versionado e nenhuma chave está no repositório.

```bash
cd backend && uv sync && pytest -q          # testes do back-end
cd app && flutter test && flutter analyze   # testes e análise do cliente
```

Sem o acervo, o back-end não responde consultas reais: é preciso ter as fontes e rodar o
ETL. Os testes não precisam dele.
