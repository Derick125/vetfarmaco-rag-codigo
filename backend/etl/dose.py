"""Padrão de dose por peso corporal, compartilhado entre a auditoria do ETL
(`etl/auditar_previews.py`) e a validação pós-geração da Fase 3
(`docs/RAG_SPEC.md` §7, item 3 — "dose com lastro": todo padrão numérico de
dose citado por uma resposta exige `chunk_ids` não vazio e ocorrência do
mesmo valor num chunk recuperado). As duas pontas têm que reconhecer
EXATAMENTE as mesmas variantes — se divergirem, uma dose real citada pelo
modelo pode passar despercebida pela auditoria mas ser rejeitada pela
validação (ou vice-versa) só por causa de uma diferença de regex, não de
conteúdo. Por isso o padrão vive aqui, importado nos dois lados, nunca
redefinido.

O padrão foi levantado empiricamente sobre os seis previews de bula
(`backend/data/preview/*.json`) e o corpus do Spinosa
(`backend/data/extracted/livro_completo_chunks.jsonl`) — ver
`backend/tests/test_etl_dose.py` para a lista de variantes reais encontradas
e usadas como caso de teste. Cobre:

- Unidade: mg, ml/mL (e "mℓ", com ela minúscula de script — grafia comum no
  Spinosa), mcg, µg (sinal de micro, U+00B5) e μg (mu grego, U+03BC — as
  duas grafias de "micrograma" aparecem no corpus, vindas de fontes/OCR
  diferentes), mEq, UI (sempre maiúsculo — nunca "ui" minúsculo, que não é
  grafia real de Unidade Internacional em nenhuma bula do corpus), ng, g.
- Separador entre número e unidade: qualquer quantidade de espaço em branco,
  incluindo quebra de linha — uma tabela mal extraída às vezes separa o
  número da unidade por uma linha em branco inteira (ex. "0,1\\n\\nmg/kg/min").
- Fármaco nomeado entre a unidade e o "/kg" ("mg de ivermectina / kg", "mg
  de meloxicam/kg", "mg de EPA + DHA/kg") — comum em bulas que repetem o
  nome do princípio ativo dentro da própria frase de dose. Casado de forma
  genérica (texto entre "de" e a barra), não por uma lista de fármacos —
  não pode depender do vocabulário de `etl/vocabulario/farmacos.yaml` para
  não falhar num fármaco fora dele.
- Separador entre unidade (ou fármaco nomeado) e "kg": barra (com ou sem
  espaço ao redor) ou "por" ("mg de carprofeno por kg").
- Sufixo "/dia" (dose diária, ex. "3 mg/kg/dia").
- Notação de expoente "kg-1"/"kg–1" (hífen comum ou travessão — as duas
  formas aparecem no Spinosa, sempre com travessão "–" na prática, mas o
  hífen comum é aceito também por ser tipograficamente equivalente e mais
  comum em texto digitado à mão), com ou sem ponto médio antes de "kg" —
  grafia farmacológica padrão alternativa a "/kg", usada sobretudo em
  parâmetros farmacocinéticos (ex. "mℓ/min · kg–1").
- Vírgula OU ponto como separador decimal ("0,2 mg/kg", "2.5 mg/kg").

Fora do escopo, deliberadamente: uma dose expressa como INTERVALO ("1 a 2
mg/kg") casa só o valor mais próximo da unidade ("2 mg/kg"), não o
intervalo inteiro — extrair o intervalo completo é problema de
segmentação de frase, não de reconhecimento de padrão de dose, e já era o
comportamento aceito antes deste levantamento (ver chunk de posologia do
tramadol). Uma unidade composta com outra grandeza no meio, entre a
unidade de massa/volume e o "kg" (ex. "mℓ/min · kg–1", depuração
plasmática/clearance) NÃO casa, mesmo terminando em "kg-1" — isso não é
dose por peso, é parâmetro farmacocinético (taxa de eliminação por unidade
de tempo por kg), uma grandeza física diferente; a notação "kg-1" só casa
quando vem logo depois da unidade de dose, com nada além de espaço/ponto
médio entre as duas (ex. "5 mg kg-1", "5 mg·kg-1" — hipotéticos, não
observados neste corpus, mas é a forma padrão da notação farmacológica que
este padrão precisa reconhecer se aparecer).
"""

from __future__ import annotations

import re

# Ordem importa: `mg` antes de `g` (senão a alternância pararia em "g" e
# deixaria "m" para trás não seria o caso aqui porque a busca é ancorada,
# mas mantemos a mais específica primeiro por clareza e para blindar contra
# mudança futura na âncora). `ng` antes de `g` pelo mesmo motivo.
_UNIDADE = r"(?:mg|m[lL]|mℓ|mcg|µg|μg|mEq|UI|ng|g)"

_NUMERO = r"\d+(?:[.,]\d+)?"

# Nome de fármaco opcional entre a unidade e o "/kg" ("mg de ivermectina /
# kg"). Genérico (não usa `etl/vocabulario/farmacos.yaml`): qualquer trecho
# curto sem dígito nem barra entre "de" e o separador de "kg" serve — um
# fármaco fora do vocabulário controlado não pode fazer o padrão de dose
# falhar. Preguiçoso (`{1,40}?`) para nunca ultrapassar o "/" ou "por" mais
# próximo.
_FARMACO_INTERMEDIARIO = r"(?:\s+de\s+[^\d/\n]{1,40}?)?"

# "/kg" (com espaço opcional em qualquer lado da barra) ou "por kg", com
# "/dia" opcional no fim (dose diária).
_POR_KG = rf"{_FARMACO_INTERMEDIARIO}(?:\s*/\s*|\s+por\s+)[Kk][Gg](?:\s*/\s*dia\b)?"

# Notação de expoente "kg-1"/"kg–1" (farmacocinética: "mℓ/min · kg–1") —
# alternativa a "/kg", nunca precedida por "de <fármaco>" na prática.
_KG_EXPOENTE = r"\s*·?\s*[Kk][Gg]\s*[-–]\s*1\b"

PADRAO_DOSE_POR_KG = re.compile(rf"{_NUMERO}\s*{_UNIDADE}(?:{_POR_KG}|{_KG_EXPOENTE})")


def extrair_doses(texto: str) -> list[str]:
    """Todos os trechos de `texto` que casam `PADRAO_DOSE_POR_KG`, na ordem
    em que aparecem. Usada tanto pela auditoria (`etl/auditar_previews.py`)
    quanto pela validação "dose com lastro" da Fase 3 — mantenha as duas
    chamando esta função em vez de casar o padrão localmente.
    """
    return [casamento.group(0) for casamento in PADRAO_DOSE_POR_KG.finditer(texto)]
