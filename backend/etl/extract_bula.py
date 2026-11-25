"""Extração de bulas, segmentada por seção (docs/RAG_SPEC.md §2, extensão de
`etl/extract.py` para o corpus complementar de bulas).

Bulas são curtas (1-3 páginas) e não têm capítulo — a unidade de
segmentação natural é a **seção da bula**, não a janela deslizante sobre o
documento inteiro. Este módulo:

1. Reconhece cabeçalhos de seção em quatro formatos — numerado de linha
   única, com dígito OU numeral romano (RDC 60/12, ex.: "8. POSOLOGIA E
   MODO DE USAR", "III) DIZERES LEGAIS" — o romano é o grupo de nível mais
   alto que contém os itens numerados por dígito), não numerado em caixa
   alta (bulas veterinárias/antigas, ex.: "FORMA DE APLICAÇÃO E DOSAGEM"),
   frase seguida de dois-pontos no mesmo caso do texto corrido (também
   bulas antigas, ex.: "Posologia e modo de usar:") e numerado em DUAS
   linhas, com sub-numeração decimal ou numeral romano sozinho (modelos
   RCM/SPC da UE, ex.: "4.9\nPosologia e via de administração"; RDC 60/12,
   ex.: "III)\nDIZERES LEGAIS") — e casa o texto do cabeçalho contra
   `etl/vocabulario/secoes_bula.yaml` para normalizá-lo num vocabulário
   fixo (`composicao`, `indicacoes`, `posologia`, ...). A
   varredura (`_dividir_bloco_em_segmentos`) roda linha a linha sobre o
   bloco inteiro, não só na primeira linha — necessário porque em alguns
   PDFs (modelos RCM/SPC, entre outros) uma página inteira é um bloco só
   do PyMuPDF, com vários cabeçalhos "enterrados" no meio do texto. A
   ordem dos blocos usada aqui é a ordem NATURAL do PyMuPDF, não uma
   reordenação por posição vertical — necessário para bulas em múltiplas
   colunas, onde a coordenada vertical de uma coluna não é comparável com
   a de outra.
2. Limita a extração ao primeiro ANEXO, quando o PDF segue o modelo
   regulatório da UE (RCM/SPC, formato INFARMED/EMA) de organizar o
   documento em ANEXOS numerados em romano — ANEXO I é o conteúdo clínico
   de verdade; ANEXO II em diante é material regulatório/administrativo
   (fabricante, condições de fornecimento, rotulagem, folheto informativo
   repetido por apresentação comercial) sem informação clínica nova
   (`_ultima_pagina_do_primeiro_anexo`, log
   `paginas_fora_do_primeiro_anexo_ignoradas`). Bulas sem esse formato
   (a maioria) não são afetadas.
3. Descarta seções sem valor clínico (dizeres legais, responsável técnico,
   fabricante, apresentações comerciais, prazo de validade, histórico de
   alteração de bula, SAC, abertura de ampola, resumo de ensaio clínico) —
   cada descarte é registrado em log (`secao_descartada`) para auditoria.
   Bulas bilíngues (a bula inteira repetida em outro idioma, comum no
   Mercosul) são detectadas de forma genérica — reincidência da seção
   "composicao", confirmada por marcadores léxicos do idioma no cabeçalho
   ou no corpo das seções a partir da reincidência — e o bloco repetido é
   descartado por inteiro (`_descartar_bloco_em_espanhol`), registrado em
   log (`bloco_em_espanhol_descartado`). Bulas humanas bipartidas em
   "INFORMAÇÕES AO PACIENTE" (linguagem leiga) e "INFORMAÇÕES TÉCNICAS"
   (profissional de saúde) têm o bloco leigo inteiro descartado pelo mesmo
   princípio — um intervalo de seções entre dois marcadores estruturais é
   redundante com o resto do documento (`_descartar_bloco_paciente`, log
   `bloco_informacoes_ao_paciente_descartado`). Dentro de uma seção
   mantida, uma varredura de linha (`_remover_linhas_administrativas`)
   remove linhas isoladas de conteúdo legal/administrativo ou instruções
   ilustradas de dispositivo de dosagem que sobram sem cabeçalho próprio
   (licenciamento MAPA/Ministério, registro MS, CNPJ, CRF/CRMV, endereço,
   SAC, telefone, "Indústria Brasileira", "Marca Registrada", "Responsável
   Técnico", "VENDA SOB PRESCRIÇÃO", "conta-gotas") — só a linha inteira,
   nunca um trecho dentro de uma frase clínica, contado por bula em log
   (`linhas_administrativas_removidas`). A mesma varredura
   (`_remover_numeros_de_pagina`) também remove um número de página
   isolado numa linha própria — cabeçalho/rodapé de página inteiro, ou o
   fragmento que sobra quando esse bloco cai no meio do texto corrido de
   uma seção — contado em log (`numeros_de_pagina_removidos`). Uma terceira
   varredura (`_remover_paragrafos_administrativos`) remove um PARÁGRAFO
   inteiro (da linha-gatilho até a próxima linha em branco) sem cabeçalho
   próprio dentro de uma seção que, no resto, é aplicável — hoje cobre o
   desenho de estudo de comparabilidade ("estudo de grampo euglicêmico")
   de medicamento biossimilar embutido em "Propriedades farmacodinâmicas"/
   "farmacocinéticas", preservando o perfil de ação e a farmacocinética de
   absorção em si (início, pico, duração, Cmax, meia-vida), contado em log
   (`paragrafos_administrativos_removidos`). Uma quarta
   (`_remover_blocos_administrativos`) remove um BLOCO inteiro — da linha-
   gatilho até a próxima linha que parece um cabeçalho de verdade,
   atravessando linhas em branco internas — para conteúdo com vários
   parágrafos e lacunas (ex. espaço de figura) antes do próximo cabeçalho,
   como instruções ilustradas de abertura de ampola com mais de um sistema
   (cada um com sua lista de passos numerados). Roda ANTES da segmentação
   em cabeçalhos (diferente das outras três) — cada passo numerado isolado
   já seria, por si só, um cabeçalho de sinal forte que abriria sua própria
   seção antes de qualquer varredura pós-segmentação ter a chance de agir
   — contado em log (`blocos_administrativos_removidos`). Uma remoção que
   chega ao fim de um `_Bloco` do PyMuPDF sem achar cabeçalho de parada
   continua no próximo bloco (`em_andamento`, repassado entre chamadas na
   mesma passagem por `extrair()`) — necessário porque o PyMuPDF separa um
   bloco de texto em vários quando há uma lacuna grande o bastante (ex. o
   espaço de um diagrama entre "Sistema 1" e "Sistema 2" de instrução
   ilustrada); sem isso, o segundo sistema ficaria à mostra por inteiro. O
   próprio padrão do gatilho precisa ser a frase-título que abre a
   instrução, nunca uma combinação de palavras solta que também apareça em
   frases avulsas — a remoção atravessa página se for preciso, e um
   gatilho solto pego pouco antes do fim de um bloco pode varrer conteúdo
   clínico páginas à frente até achar o próximo cabeçalho de verdade.
   Tabelas também
   podem ser descartadas por conteúdo (`tabelas_descartadas`, casado
   contra a legenda) — nunca truncadas, só omitidas por inteiro quando sem
   valor clínico à parte (ex. estudo farmacocinético populacional por
   faixa etária/sexo), contado em log (`tabela_descartada`,
   `tabelas_descartadas_total`).
4. Funde, em `secoes` já montada, toda seção com menos de ~10 palavras na
   seção anterior, em vez de deixá-la virar um chunk próprio
   (`_mesclar_secoes_curtas`, log `secao_curta_fundida_na_anterior`) —
   cobre o caso, genérico, de um cabeçalho de referência cruzada dentro de
   uma frase ("...ver item INTERAÇÕES MEDICAMENTOSAS") ficar isolado numa
   linha própria do PDF e ser lido como cabeçalho de seção de verdade.
   Roda por último, depois de tudo que depende de encontrar cabeçalhos
   específicos em `secoes` (ANEXO, "Nome do medicamento veterinário",
   "INFORMAÇÕES AO PACIENTE"/"TÉCNICAS") — fundir antes apagaria
   exatamente os cabeçalhos que esses mecanismos procuram.
5. Extrai tabelas com `pdfplumber` e as serializa em Markdown — uma tabela
   é uma unidade indivisível, nunca dividida entre chunks (isso é
   responsabilidade de `etl/chunk_bula.py`, mas a tabela já sai daqui como
   uma unidade própria, associada à seção onde aparece visualmente).
   Células vazias são preservadas na serialização (`_serializar_markdown`,
   reaproveitada de `etl/extract.py`) — não colapsa colunas.

Reaproveita de `etl/extract.py` a limpeza de texto corrido (junção de
hifenização, normalização de espaços/unidades) e a extração/serialização de
tabelas — a lógica de tabela é idêntica à do corpus de livro.

Uso:
    python -m etl.extract_bula --source data/bulas/ivermectina.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pymupdf
import structlog
import yaml

from etl.chunk import _casar, carregar_vocabulario
from etl.extract import (
    _Bloco,
    _blocos_da_pagina,
    _extrair_tabelas,
    _limpar_bloco,
    _normalizar_espacos,
    _sobrepoe,
)

logger = structlog.get_logger()

CAMINHO_VOCABULARIO_SECOES_PADRAO = Path(__file__).parent / "vocabulario" / "secoes_bula.yaml"
CAMINHO_VOCABULARIO_FARMACOS_PADRAO = Path(__file__).parent / "vocabulario" / "farmacos.yaml"

# Espécies-alvo do escopo do TCC (TCC §1, CLAUDE.md §1: clínica de pequenos
# animais). Usada só para filtrar CICLOS DE PRODUTO num PDF multiespécie
# (ver `_atribuir_ciclo_de_produto`) — nunca para decidir espécie de uma
# bula comum de um produto só, isso vem sempre do manifesto.
ESPECIES_ESCOPO_TCC = frozenset({"canino", "felino"})

# Cabeçalhos de seção de bula são curtos e não terminam em pontuação de fim
# de frase — isso distingue "FORMA DE APLICAÇÃO E DOSAGEM" de uma frase
# legal em caixa alta como "VENDA SOB PRESCRIÇÃO ... VETERINÁRIO.", que não
# é cabeçalho de seção. Um cabeçalho numerado pode ser mais longo (a
# numeração em si já é o sinal forte, não depende do texto estar em caixa
# alta nem ser curto) — ex.: o título longo da seção de sobredosagem,
# com complementos entre parênteses, em modelos RCM/SPC da UE.
_MAX_CARACTERES_CABECALHO = 60
_MAX_CARACTERES_TITULO_NUMERADO = 100

# Prefixo numérico, com sub-numeração decimal opcional — "1.", "4.9",
# "6.4." — cobre tanto o numerado simples da RDC 60/12 quanto o
# hierárquico dos modelos RCM/SPC da UE. Sempre exige um "." em algum
# ponto (isolado após um inteiro, ou como separador decimal) — nunca um
# número nu ("1", "2") sem nenhuma pontuação, que apareceria à toa numa
# linha de fragmento de tabela de dose mal extraída (ex. uma coluna de
# frações "1/4  1/2  ...  1 e 1/4  1 e 1/2" quebrada por PDF).
_PADRAO_NUMERO_PREFIXO = r"(?:\d{1,2}(?:\.\d{1,2}\.?|\.)|[IVX]{1,4}\))"
# Uma linha que é SÓ o número, nada mais — sinal de que o título vem na
# linha seguinte (ver `_parece_titulo_numerado` e `_dividir_bloco_em_segmentos`).
_PADRAO_NUMERO_SOZINHO = re.compile(rf"^\s*{_PADRAO_NUMERO_PREFIXO}\s*$")
# Numerado com título na MESMA linha. Exige um separador inequívoco entre
# o número e o título — um "." logo após um número inteiro ("1. TÍTULO"),
# a própria sub-numeração decimal ("4.10 Título", já que o "." interno já
# separa número de texto), ou um numeral romano seguido de ")" — grupo de
# nível mais alto de bulas RDC 60/12 ("I) IDENTIFICAÇÃO DO MEDICAMENTO",
# "III) DIZERES LEGAIS"), que por sua vez contêm os itens numerados por
# dígito. Sem a exigência de separador, uma linha de tabela de dose mal
# extraída como "3 mg Até 3 Kg" seria lida como cabeçalho numerado "3" com
# título "mg Até 3 Kg".
#
# Dígito + ")" (sem o ".") é DELIBERADAMENTE excluído — é a marcação comum
# de passo de lista dentro de um procedimento ("1) Calcular a dose total
# ...", "2) Calcular o volume ..."), não de cabeçalho de seção; incluí-lo
# aqui fazia esses passos virarem seção própria (ex. bula do tramadol,
# instruções de diluição dentro de POSOLOGIA), fragmentando a seção e
# perdendo a ressalva que vem logo depois no mesmo bloco.
_PADRAO_NUMERACAO = re.compile(r"^\s*(?:\d{1,2}\.\d{1,2}\.?|\d{1,2}\.|[IVX]{1,4}\))\s*(.+)$")

# Sub-item por letra ("a) Medicamentos que provocam...", "b) ...", "c)
# ..."), comum em hierarquias de interação medicamentosa de bulas antigas
# — nível numerado por dígito, sub-nível por letra minúscula. Sinal forte
# por construção (uma letra minúscula sozinha seguida de ")" no início da
# linha é rara fora de uma lista deliberada) — por isso pode ser checado
# em qualquer linha do bloco, como o numerado por dígito. Ao contrário do
# numerado por dígito, o "título" aqui costuma ser a frase inteira que
# resume o subgrupo (acaba em "." ou ":", não só numa frase curta) — por
# isso o comprimento permitido é maior e pontuação final não desqualifica.
_MAX_CARACTERES_TITULO_LETRA = 220
_PADRAO_LETRA_MESMA_LINHA = re.compile(r"^\s*[a-z]\)\s*(.+)$")

# Terceiro formato de cabeçalho, comum em bulas antigas: uma frase curta
# seguida de dois-pontos, no mesmo caso do texto corrido — "Fórmula:",
# "Posologia e modo de usar:" — às vezes com o corpo da seção já na mesma
# linha ("Apresentação: blister contendo..."). É um sinal estrutural mais
# fraco que caixa alta: um item de lista como "- Diuréticos: elevação da
# toxicidade..." tem a mesma forma. Por isso o comprimento é mais curto que
# `_MAX_CARACTERES_CABECALHO` (títulos reais aqui não passam de ~30
# caracteres) e, em `_classificar_cabecalho`, esse modo só vira cabeçalho se
# casar contra o vocabulário — não há fallback para "outros" nesse modo.
_MAX_CARACTERES_CABECALHO_FRACA = 40
_PADRAO_CABECALHO_COLON = re.compile(rf"^([^\n:]{{2,{_MAX_CARACTERES_CABECALHO_FRACA}}}):\s?(.*)$")

# Um trecho de texto "parece frase" (candidato a legenda de tabela) se tiver
# tamanho mínimo e ao menos uma letra minúscula — distingue prosa de
# fragmentos de tabela mal extraídos (números, siglas soltas).
_TAMANHO_MINIMO_FRASE = 15
_MAX_CARACTERES_LEGENDA = 200


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------


@dataclass
class TabelaExtraida:
    """Uma tabela de bula, já serializada em Markdown."""

    markdown: str
    legenda: str  # frase introdutória mais próxima, ou o cabeçalho da seção


@dataclass
class SecaoExtraida:
    """Uma seção de bula mantida (não descartada), pronta para o chunking."""

    secao: str  # nome canônico (etl/vocabulario/secoes_bula.yaml)
    cabecalho_original: str | None  # texto do cabeçalho como está no PDF
    pagina_inicial: int
    texto: str
    tabelas: list[TabelaExtraida] = field(default_factory=list)
    # Um único PDF pode descrever mais de um produto/apresentação (ver
    # `_atribuir_ciclo_de_produto`) — quando isso acontece, `produto_ciclo`
    # e `especies_ciclo` identificam a QUAL apresentação esta seção
    # pertence, mais específico que o `produto`/`especies` do manifesto
    # (que descrevem o arquivo inteiro). `None`/lista vazia quando o PDF
    # não declara produtos por ciclo (a maioria das bulas).
    produto_ciclo: str | None = None
    especies_ciclo: list[str] = field(default_factory=list)


@dataclass
class _RegraSecao:
    secao: str
    padrao: re.Pattern[str]


@dataclass
class VocabularioSecoes:
    secoes: list[_RegraSecao]
    descartar: re.Pattern[str] | None
    linhas_administrativas: re.Pattern[str] | None
    paragrafos_administrativos: re.Pattern[str] | None
    blocos_administrativos: re.Pattern[str] | None
    tabelas_descartadas: re.Pattern[str] | None


# --------------------------------------------------------------------------
# Vocabulário de cabeçalhos
# --------------------------------------------------------------------------


def carregar_vocabulario_secoes(caminho: Path) -> VocabularioSecoes:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    regras = [
        _RegraSecao(
            secao=entrada["secao"], padrao=re.compile("|".join(entrada["padroes"]), re.IGNORECASE)
        )
        for entrada in dados.get("secoes", [])
    ]
    padroes_descarte = dados.get("descartar", [])
    descartar = re.compile("|".join(padroes_descarte), re.IGNORECASE) if padroes_descarte else None
    padroes_linha = dados.get("linhas_administrativas", [])
    linhas_administrativas = (
        re.compile("|".join(padroes_linha), re.IGNORECASE) if padroes_linha else None
    )
    padroes_paragrafo = dados.get("paragrafos_administrativos", [])
    paragrafos_administrativos = (
        re.compile("|".join(padroes_paragrafo), re.IGNORECASE) if padroes_paragrafo else None
    )
    padroes_bloco = dados.get("blocos_administrativos", [])
    blocos_administrativos = (
        re.compile("|".join(padroes_bloco), re.IGNORECASE) if padroes_bloco else None
    )
    padroes_tabela = dados.get("tabelas_descartadas", [])
    tabelas_descartadas = (
        re.compile("|".join(padroes_tabela), re.IGNORECASE) if padroes_tabela else None
    )
    return VocabularioSecoes(
        secoes=regras,
        descartar=descartar,
        linhas_administrativas=linhas_administrativas,
        paragrafos_administrativos=paragrafos_administrativos,
        blocos_administrativos=blocos_administrativos,
        tabelas_descartadas=tabelas_descartadas,
    )


def _titulo_numerado_mesma_linha(linha: str) -> str | None:
    """Numerado com número e título na MESMA linha ("1. NOME...", "4.10
    Sobredosagem..."). Sinal forte por construção — `_PADRAO_NUMERACAO"
    exige um separador inequívoco entre número e título — por isso pode
    ser checado em QUALQUER linha de um bloco, não só na primeira (ver
    `_dividir_bloco_em_segmentos`).
    """
    linha = linha.strip()
    if not linha or linha.endswith((".", ":", ";", ",")):
        return None
    casamento = _PADRAO_NUMERACAO.match(linha)
    if not casamento:
        return None
    texto = casamento.group(1).strip()
    if not texto or len(texto) > _MAX_CARACTERES_TITULO_NUMERADO:
        return None
    return unicodedata.normalize("NFC", texto)


def _titulo_letra_mesma_linha(linha: str) -> str | None:
    """Sub-item por letra ("a) Medicamentos que provocam..."). Ver
    `_PADRAO_LETRA_MESMA_LINHA`. Ao contrário do numerado por dígito, não
    rejeita título terminado em pontuação — o "título" aqui é a frase
    inteira que resume o subgrupo, que legitimamente termina em "." ou ":".
    """
    casamento = _PADRAO_LETRA_MESMA_LINHA.match(linha.strip())
    if not casamento:
        return None
    texto = casamento.group(1).strip()
    if not texto or len(texto) > _MAX_CARACTERES_TITULO_LETRA:
        return None
    return unicodedata.normalize("NFC", texto)


def _parece_titulo_numerado(linha: str) -> bool:
    """Se `linha` (a linha seguinte a um número sozinho) parece um título de
    seção, e não uma frase comum que por acaso vem depois de uma linha só
    com número. Ver `_dividir_bloco_em_segmentos`.
    """
    linha = linha.strip()
    if not linha or len(linha) > _MAX_CARACTERES_TITULO_NUMERADO:
        return False
    return not linha.endswith((".", ":", ";", ","))


def _eh_candidato_a_cabecalho_caps(linha: str) -> str | None:
    """Caixa alta isolada, sem numeração ("FORMA DE APLICAÇÃO E DOSAGEM").
    Sinal mais fraco que o numerado — uma linha de tabela mal extraída ou
    um trecho de frase partido por quebra visual de PDF também pode ficar
    curto; só é seguro checar na PRIMEIRA linha de um bloco (ver
    `_dividir_bloco_em_segmentos`), que é onde esse formato sempre apareceu
    nas bulas observadas até agora.
    """
    linha = linha.strip()
    if not linha or len(linha) > _MAX_CARACTERES_CABECALHO:
        return None
    if linha.endswith((".", ":", ";", ",")):
        return None
    texto_normalizado = unicodedata.normalize("NFC", linha)
    if not texto_normalizado.isupper():
        return None
    return texto_normalizado


def _dividir_bloco_em_segmentos(
    texto_bloco: str, vocabulario: VocabularioSecoes
) -> list[tuple[str | None, bool | None, str | None, str]]:
    """Divide um bloco de texto cru em segmentos delimitados por cabeçalho,
    já classificados contra o vocabulário. Devolve uma lista de
    `(secao_canonica, descartar, cabecalho_original, texto)`.

    Necessário porque em alguns PDFs (modelos RCM/SPC da UE, entre outros)
    o PyMuPDF não separa um bloco por parágrafo/seção — a página inteira
    pode ser um bloco só, com vários cabeçalhos "enterrados" no meio do
    texto. Por isso a varredura de cabeçalho NUMERADO (linha única ou em
    duas linhas — `_titulo_numerado_mesma_linha`,
    `_PADRAO_NUMERO_SOZINHO`+`_parece_titulo_numerado`) roda sobre o bloco
    inteiro, linha a linha, não só na primeira. O mesmo vale para o
    sub-item por LETRA (`_titulo_letra_mesma_linha`, "a) Título...") comum
    em hierarquias de interação medicamentosa de bulas antigas — mas esse
    é sinal fraco, como o de dois-pontos: só vira cabeçalho se casar no
    vocabulário, para não arriscar fragmentar uma lista lettered comum de
    outra bula sem essa hierarquia.

    Caixa alta sem número (`_eh_candidato_a_cabecalho_caps`) também roda
    em qualquer linha, mas fora da PRIMEIRA linha do bloco exige casamento
    no vocabulário (modo "fraca", sem fallback para "outros") — um
    fragmento de quebra de linha do PDF dentro de uma seção já descartada
    (ex. um pedaço de número de registro "EU/2/11/134/023", que passa em
    `isupper()` por não ter letra minúscula, ou uma frase legal em caixa
    alta, como o aviso padrão de guarda fora do alcance de
    crianças) não pode abrir seção nova sem casamento — se abrisse (modo
    "forte"), esse fragmento ESCAPARIA do descarte da seção em que estava
    embutido, e isso já foi visto acontecer de verdade. Na primeira linha
    do bloco, mantém o fallback "forte" de sempre — é onde esse formato
    historicamente apareceu, em blocos bem segmentados por cabeçalho.
    Frase com dois-pontos (`_PADRAO_CABECALHO_COLON`, modo "fraca") tem o
    mesmo risco e por isso também só é checada na primeira linha: uma
    quebra de linha visual do PDF no meio de uma frase pode por acaso
    terminar numa palavra do vocabulário seguida de ":" (ex. "...nas
    seguintes posologias:" quebrando bem antes do dois-pontos).

    O primeiro item pode ter `secao_canonica=None` — texto antes do
    primeiro cabeçalho reconhecido DENTRO deste bloco, que o chamador deve
    tratar como continuação da seção que já estava aberta antes dele.
    """
    linhas = texto_bloco.split("\n")
    segmentos: list[tuple[str | None, bool | None, str | None, str]] = []
    secao_atual: str | None = None
    descartar_atual: bool | None = None
    cabecalho_atual: str | None = None
    buffer: list[str] = []

    def _fechar_segmento() -> None:
        segmentos.append((secao_atual, descartar_atual, cabecalho_atual, "\n".join(buffer)))

    def _abrir_segmento(cabecalho: str, modo: str, texto_inicial: list[str]) -> bool:
        nonlocal secao_atual, descartar_atual, cabecalho_atual, buffer
        classificacao = _classificar_cabecalho(cabecalho, modo, vocabulario)
        if classificacao is None:
            return False
        _fechar_segmento()
        secao_atual, descartar_atual = classificacao
        cabecalho_atual = cabecalho
        buffer = texto_inicial
        return True

    i, n = 0, len(linhas)
    while i < n:
        linha_normalizada = _normalizar_espacos(linhas[i]).strip()

        if _PADRAO_NUMERO_SOZINHO.match(linha_normalizada) and i + 1 < n:
            proxima = _normalizar_espacos(linhas[i + 1]).strip()
            if _parece_titulo_numerado(proxima):
                if _abrir_segmento(unicodedata.normalize("NFC", proxima), "forte", []):
                    i += 2
                    continue

        titulo_mesma_linha = _titulo_numerado_mesma_linha(linha_normalizada)
        if titulo_mesma_linha is not None and _abrir_segmento(titulo_mesma_linha, "forte", []):
            i += 1
            continue

        # Sub-item por letra: sinal fraco (como o de dois-pontos) — só
        # vira cabeçalho se casar no vocabulário, para não arriscar
        # fragmentar uma lista lettered qualquer de outra bula que não
        # tenha essa hierarquia.
        titulo_letra = _titulo_letra_mesma_linha(linha_normalizada)
        if titulo_letra is not None and _abrir_segmento(titulo_letra, "fraca", []):
            i += 1
            continue

        # Caixa alta sem número: útil em qualquer posição, não só na
        # primeira linha do bloco — necessário porque em algumas bulas
        # (esta, entre outras) um bloco do PyMuPDF cobre a página quase
        # inteira, com vários cabeçalhos "enterrados" no meio dele. Fora
        # da primeira linha, porém, exige casamento no vocabulário (modo
        # "fraca", sem fallback para "outros") — sem essa restrição,
        # fragmentos que sobram de quebra de linha do PDF dentro de uma
        # seção já descartada (ex. um pedaço de número de registro "EU/2/
        # 11/134/023", que passa em isupper() por não ter letra minúscula)
        # abririam uma seção nova e ESCAPARIAM do descarte — visto
        # acontecer de verdade. Na primeira linha, mantém o fallback
        # "forte" de sempre: é onde esse formato historicamente apareceu.
        candidato_caps = _eh_candidato_a_cabecalho_caps(linha_normalizada)
        if candidato_caps is not None:
            modo_caps = "forte" if i == 0 else "fraca"
            if _abrir_segmento(candidato_caps, modo_caps, []):
                i += 1
                continue

        if i == 0:
            casamento = _PADRAO_CABECALHO_COLON.match(linha_normalizada)
            if casamento:
                cabecalho_bruto, resto_da_linha = casamento.groups()
                cabecalho_bruto = unicodedata.normalize("NFC", cabecalho_bruto.strip())
                texto_inicial = [resto_da_linha] if resto_da_linha.strip() else []
                if cabecalho_bruto and _abrir_segmento(cabecalho_bruto, "fraca", texto_inicial):
                    i += 1
                    continue

        buffer.append(linhas[i])
        i += 1

    _fechar_segmento()
    return segmentos


def _classificar_cabecalho(
    texto_cabecalho: str, modo: str, vocabulario: VocabularioSecoes
) -> tuple[str, bool] | None:
    """Devolve `(secao_canonica, descartar)` para um cabeçalho já reconhecido
    por `_detectar_cabecalho`, ou `None` se ele deve ser tratado como corpo
    de texto normal (só acontece no modo "fraca" sem casamento — ver
    `_detectar_cabecalho`).

    Seções não mapeadas em nenhum padrão, no modo "forte", caem em
    "outros" — mantidas, e registradas em log para revisão manual do
    vocabulário.
    """
    if vocabulario.descartar and vocabulario.descartar.search(texto_cabecalho):
        return "descarte", True
    for regra in vocabulario.secoes:
        if regra.padrao.search(texto_cabecalho):
            return regra.secao, False
    if modo == "forte":
        logger.info("secao_nao_mapeada", cabecalho=texto_cabecalho, modo=modo)
        return "outros", False
    return None


# Um número de página isolado (nada mais na linha) — o bloco de
# cabeçalho/rodapé de página inteiro (ex. um bloco do PyMuPDF cujo texto
# cru é só " \n8\n"), ou o fragmento que sobra quando esse bloco cai no
# meio do fluxo natural, entre dois blocos de texto corrido da mesma
# seção (não tem cabeçalho próprio, então não fecha seção — só polui o
# meio do texto, ex. "...pela manhã\n\n9\n\n(geralmente entre..."). Limite
# de 4 dígitos cobre qualquer paginação realista sem arriscar remover um
# valor numérico clínico isolado (nenhum valor de dose, mg ou intervalo
# aparece sozinho numa linha sem unidade ao lado).
_PADRAO_NUMERO_DE_PAGINA = re.compile(r"^\d{1,4}$")


def _remover_numeros_de_pagina(texto_bloco: str) -> tuple[str, int]:
    """Remove, de um bloco de texto CRU (ainda não limpo), as linhas que são
    só um número de página isolado. Roda linha a linha, antes de
    `_limpar_bloco` fundir as linhas em parágrafo — mesma lógica e mesma
    garantia de `_remover_linhas_administrativas`: só remove a LINHA
    INTEIRA que é puramente dígitos, nunca um número dentro de uma frase
    clínica já fundida.

    Devolve `(texto_sem_essas_linhas, linhas_removidas)`.
    """
    linhas = texto_bloco.split("\n")
    mantidas = []
    removidas = 0
    for linha in linhas:
        if _PADRAO_NUMERO_DE_PAGINA.match(linha.strip()):
            removidas += 1
            continue
        mantidas.append(linha)
    return "\n".join(mantidas), removidas


def _remover_paragrafos_administrativos(
    texto_bloco: str, vocabulario: VocabularioSecoes
) -> tuple[str, int]:
    """Remove, de um bloco de texto CRU (ainda não limpo), um PARÁGRAFO
    inteiro — da linha que bate num padrão de `paragrafos_administrativos`
    até a próxima linha em branco (ou o fim do bloco) — para conteúdo
    espalhado por várias linhas sem cabeçalho próprio dentro de uma seção
    que, no resto, é clinicamente aplicável (ex.: desenho de estudo de
    comparabilidade — "estudo de grampo euglicêmico", curvas de infusão de
    glicose — embutido dentro de "Propriedades farmacodinâmicas" de um
    medicamento biossimilar, que também traz o perfil de ação de verdade).

    Diferente de `_remover_linhas_administrativas` (que só remove a linha
    que bate no padrão): aqui a remoção continua pelas linhas seguintes
    até uma linha em branco, porque o padrão só aparece na PRIMEIRA frase
    do parágrafo — as frases seguintes descrevem o mesmo estudo sem repetir
    o gatilho, e nestas bulas um parágrafo sempre termina numa linha em
    branco antes do próximo.

    Devolve `(texto_sem_esses_paragrafos, paragrafos_removidos)`.
    """
    if vocabulario.paragrafos_administrativos is None:
        return texto_bloco, 0
    linhas = texto_bloco.split("\n")
    mantidas: list[str] = []
    removidos = 0
    i, n = 0, len(linhas)
    while i < n:
        linha = linhas[i]
        if linha.strip() and vocabulario.paragrafos_administrativos.search(linha):
            removidos += 1
            i += 1
            while i < n and linhas[i].strip():
                i += 1
            continue
        mantidas.append(linha)
        i += 1
    return "\n".join(mantidas), removidos


def _parece_inicio_de_cabecalho(linha: str) -> bool:
    """Sinal LEVE de que `linha` é o início de um cabeçalho de seção de
    verdade — usado só para saber ONDE PARAR em
    `_remover_blocos_administrativos`, não para classificar nada. Reusa os
    checks de sinal forte (numerado de linha única, caixa alta) — não o
    numerado em duas linhas (exigiria olhar a linha seguinte, que esta
    função não tem) nem os formatos fracos (dois-pontos, letra), que dão
    falso positivo demais para servir de ponto de parada.
    """
    linha_normalizada = _normalizar_espacos(linha).strip()
    if not linha_normalizada:
        return False
    if _titulo_numerado_mesma_linha(linha_normalizada) is not None:
        return True
    return _eh_candidato_a_cabecalho_caps(linha_normalizada) is not None


def _remover_blocos_administrativos(
    texto_bloco: str, vocabulario: VocabularioSecoes, em_andamento: bool = False
) -> tuple[str, int, bool]:
    """Remove, de um bloco de texto CRU, um BLOCO inteiro — da linha que
    bate num padrão de `blocos_administrativos` até a próxima linha que
    parece o início de um cabeçalho de seção de verdade
    (`_parece_inicio_de_cabecalho`), ou o fim do bloco.

    Diferente de `_remover_paragrafos_administrativos` (que para na
    primeira linha em branco): aqui a remoção ATRAVESSA linhas em branco
    internas — necessário para conteúdo com vários parágrafos e lacunas em
    branco (ex. espaço de diagrama/figura) antes do próximo cabeçalho de
    verdade, como instruções ilustradas de abertura de ampola com dois
    sistemas, cada um com sua própria lista de passos numerados "1.\nTexto
    do passo" (numerado em duas linhas — ver `_dividir_bloco_em_segmentos`).

    Por isso PRECISA rodar sobre o bloco inteiro ANTES de
    `_dividir_bloco_em_segmentos`, não depois como as outras varreduras:
    cada "N.\nTexto do passo" isolado é, por si só, um cabeçalho numerado
    de sinal FORTE (sempre abre seção, mesmo sem casar no vocabulário) —
    se a segmentação rodasse primeiro, cada passo já teria virado sua
    própria seção "outros" antes desta função ter a chance de agir.

    `em_andamento` carrega uma remoção que começou num bloco ANTERIOR e
    ainda não achou seu cabeçalho de parada — necessário porque o PyMuPDF
    quebra um bloco de texto em vários `_Bloco` quando há uma lacuna grande
    o bastante (ex. o espaço reservado a um diagrama entre "Sistema 1" e
    "Sistema 2" de instrução ilustrada). Sem isso, o gatilho de descarte só
    aparece DENTRO da frase final de um sistema (ex. "...para realizar a
    abertura da ampola."), e tudo que vem ANTES dele no bloco seguinte —
    os passos do segundo sistema — sobrevive por engano, porque nunca foi
    visto por uma remoção em andamento.

    Devolve `(texto_sem_esses_blocos, blocos_removidos, ainda_em_andamento)`
    — o terceiro valor deve ser repassado como `em_andamento` na chamada
    para o PRÓXIMO bloco da mesma página/documento.
    """
    if vocabulario.blocos_administrativos is None:
        return texto_bloco, 0, False
    linhas = texto_bloco.split("\n")
    mantidas: list[str] = []
    removidos = 0
    removendo = em_andamento
    i, n = 0, len(linhas)
    while i < n:
        linha = linhas[i]
        if removendo:
            if _parece_inicio_de_cabecalho(linha):
                removendo = False
                continue
            i += 1
            continue
        if linha.strip() and vocabulario.blocos_administrativos.search(linha):
            removidos += 1
            removendo = True
            i += 1
            continue
        mantidas.append(linha)
        i += 1
    return "\n".join(mantidas), removidos, removendo


def _remover_linhas_administrativas(
    texto_bloco: str, vocabulario: VocabularioSecoes
) -> tuple[str, int]:
    """Remove, de um bloco de texto CRU (ainda não limpo), as linhas
    inteiras de conteúdo legal/administrativo que sobram sem cabeçalho
    próprio — ex.: a linha de registro do produto no Ministério da
    Agricultura (número e data do licenciamento), solta dentro da seção de
    Armazenagem, sem ela mesma ser um cabeçalho reconhecido.

    Roda linha a linha (`\\n`), antes de `_limpar_bloco` fundir as linhas
    em parágrafo — por isso só descarta a LINHA INTEIRA que bate no
    padrão, nunca um trecho dentro de uma frase clínica já fundida: os
    padrões de `linhas_administrativas` (CNPJ, CEP, telefone, sigla de
    conselho profissional, ...) não ocorrem por acaso dentro de uma frase
    sobre indicação/posologia/contraindicação.

    Devolve `(texto_sem_essas_linhas, linhas_removidas)`.
    """
    if vocabulario.linhas_administrativas is None:
        return texto_bloco, 0
    linhas = texto_bloco.split("\n")
    mantidas = []
    removidas = 0
    for linha in linhas:
        if linha.strip() and vocabulario.linhas_administrativas.search(linha):
            removidas += 1
            continue
        mantidas.append(linha)
    return "\n".join(mantidas), removidas


def _parece_frase(texto: str) -> bool:
    return len(texto) >= _TAMANHO_MINIMO_FRASE and any(c.islower() for c in texto)


def _ultima_frase(texto: str) -> str:
    """A última sentença de um parágrafo — para não usar o parágrafo inteiro
    como legenda de tabela.
    """
    partes = re.split(r"(?<=[.:])\s+", texto.strip())
    partes = [p for p in partes if p]
    candidata = partes[-1] if partes else texto.strip()
    if len(candidata) > _MAX_CARACTERES_LEGENDA:
        candidata = candidata[:_MAX_CARACTERES_LEGENDA].rstrip() + "…"
    return candidata


def _procurar_legenda(
    partes_texto: list[str], cabecalho_atual: str | None, secao_atual: str
) -> str:
    for texto in reversed(partes_texto):
        if _parece_frase(texto):
            return _ultima_frase(texto)
    return cabecalho_atual or secao_atual


# --------------------------------------------------------------------------
# Limite de ANEXO (modelos RCM/SPC da UE)
# --------------------------------------------------------------------------

# Modelos regulatórios da UE (RCM/SPC, formato INFARMED/EMA) organizam o
# PDF em ANEXOS numerados em romano: ANEXO I é o Resumo das
# Características do Medicamento — o conteúdo clínico de verdade
# (composição, indicações, posologia, contraindicações, interações,
# reações adversas...). ANEXO II (fabricante, condições de fornecimento,
# limites máximos de resíduos) e ANEXO III em diante (rotulagem e folheto
# informativo, tipicamente repetidos por apresentação comercial) são
# material regulatório/administrativo — reafirmam em formato de rótulo o
# que o ANEXO I já disse, sem informação clínica nova.
_PADRAO_ANEXO = re.compile(r"^\s*ANEXO\s+[IVXLCDM]+\s*$", re.MULTILINE | re.IGNORECASE)


def _ultima_pagina_do_primeiro_anexo(documento: pymupdf.Document) -> int:
    """Devolve o número da última página antes do SEGUNDO marcador "ANEXO
    <romano>" no documento, ou o total de páginas se houver 0 ou 1 marcador
    (a grande maioria das bulas não usa esse formato — devolve o
    documento inteiro sem alterar nada).
    """
    paginas_com_anexo: list[int] = []
    for numero_pagina in range(1, documento.page_count + 1):
        if _PADRAO_ANEXO.search(documento[numero_pagina - 1].get_text()):
            paginas_com_anexo.append(numero_pagina)
            if len(paginas_com_anexo) >= 2:
                break
    if len(paginas_com_anexo) < 2:
        return documento.page_count
    return paginas_com_anexo[1] - 1


# --------------------------------------------------------------------------
# Segmentação por seção
# --------------------------------------------------------------------------


@dataclass
class _EstadoSecao:
    secao: str
    cabecalho_original: str | None
    descartar: bool
    pagina_inicial: int
    partes_texto: list[str] = field(default_factory=list)
    tabelas: list[TabelaExtraida] = field(default_factory=list)


def _fechar_secao(
    estado: _EstadoSecao, secoes: list[SecaoExtraida], descartadas: list[dict]
) -> None:
    texto = "\n\n".join(p for p in estado.partes_texto if p)
    if not texto and not estado.tabelas:
        return
    if estado.descartar:
        descartadas.append(
            {
                "cabecalho": estado.cabecalho_original,
                "pagina": estado.pagina_inicial,
                "caracteres": len(texto),
                "tabelas_descartadas": len(estado.tabelas),
                "amostra": texto[:160],
            }
        )
        return
    secoes.append(
        SecaoExtraida(
            secao=estado.secao,
            cabecalho_original=estado.cabecalho_original,
            pagina_inicial=estado.pagina_inicial,
            texto=texto,
            tabelas=estado.tabelas,
        )
    )


# --------------------------------------------------------------------------
# Bloco duplicado em outro idioma (bula bilíngue)
# --------------------------------------------------------------------------

# Bulas bilíngues comuns no Mercosul repetem a bula inteira em espanhol
# depois da versão em português — indexar as duas duplicaria o corpus e
# degradaria BM25 e busca vetorial (o mesmo trecho competindo consigo
# mesmo). Os marcadores abaixo cobrem os cabeçalhos citados na tarefa — e
# só existem em espanhol, nunca em português (a ortografia diverge o
# bastante: "posologia" vs "posología", "contraindicações" vs
# "contraindicaciones", "reações adversas" vs "efectos secundarios" — não
# há colisão possível). CUIDADO: "posología" exige o Í ACENTUADO
# especificamente — "POSOLOG[IÍ]A" (aceitando I OU Í) já foi um bug real
# aqui, porque bate também na palavra portuguesa "posologia" (sem acento),
# presente em toda bula — o que confirmaria corte de espanhol em uma bula
# 100% portuguesa. `re.IGNORECASE` dobra maiúscula/minúscula mas não
# acento, então "Í" no padrão não casa com "I" nem "i" do português.
_MARCADORES_ESPANHOL = re.compile(
    r"INDICACIONES|CONTRAINDICACIONES|POSOLOGÍA|EFECTOS SECUNDARIOS|INTERACCIONES",
    re.IGNORECASE,
)


def _descartar_bloco_em_espanhol(secoes: list[SecaoExtraida], descartadas: list[dict]) -> None:
    """Detecta e descarta, em `secoes` (mutada in-place), uma repetição
    integral da bula em espanhol — genérico, não específico de nenhum
    arquivo:

    1. Sinal primário: a seção "composicao" (Fórmula/Composição) aparece
       uma segunda vez. Uma bula bem formada só declara a fórmula uma
       vez, perto do início — reincidência é o indício mais forte de que
       o documento inteiro está se repetindo.
    2. Confirmação: o cabeçalho OU o corpo de texto das seções a partir
       dessa reincidência contêm algum marcador léxico exclusivo de
       espanhol. Verifica o corpo também, não só o cabeçalho, porque um
       cabeçalho em espanhol sem casamento no vocabulário (ortografia
       diferente da portuguesa, ex. "Posología y modo de uso:") não abre
       seção própria (`_classificar_cabecalho`, modo "fraca") — o texto
       dele sobrevive como corpo da seção anterior, não como
       `cabecalho_original`. Sem essa confirmação, não corta — pode ser só
       uma bula com duas apresentações que repete "Composição" por
       engano, e cortar sem confirmar arriscaria descartar conteúdo
       válido.

    Qualquer seção "outros" sem cabeçalho reconhecido logo antes do corte
    (título/marca no topo da página que se repete junto com o bloco
    duplicado) entra no descarte também.
    """
    indices_composicao = [i for i, s in enumerate(secoes) if s.secao == "composicao"]
    if len(indices_composicao) < 2:
        return
    indice_corte = indices_composicao[1]

    texto_a_partir_do_corte = " ".join(
        f"{s.cabecalho_original or ''} {s.texto}" for s in secoes[indice_corte:]
    )
    texto_normalizado = unicodedata.normalize("NFC", texto_a_partir_do_corte)
    if not _MARCADORES_ESPANHOL.search(texto_normalizado):
        return

    while indice_corte > 0 and secoes[indice_corte - 1].secao == "outros":
        indice_corte -= 1

    bloco_espanhol = secoes[indice_corte:]
    del secoes[indice_corte:]

    for secao in bloco_espanhol:
        descartadas.append(
            {
                "cabecalho": secao.cabecalho_original,
                "pagina": secao.pagina_inicial,
                "caracteres": len(secao.texto),
                "tabelas_descartadas": len(secao.tabelas),
                "amostra": secao.texto[:160],
                "motivo": "bloco_em_espanhol",
            }
        )

    logger.warning(
        "bloco_em_espanhol_descartado",
        a_partir_da_secao=bloco_espanhol[0].cabecalho_original,
        pagina_inicial=bloco_espanhol[0].pagina_inicial,
        secoes_descartadas=len(bloco_espanhol),
        caracteres_descartados=sum(len(s.texto) for s in bloco_espanhol),
        tabelas_descartadas=sum(len(s.tabelas) for s in bloco_espanhol),
    )


# --------------------------------------------------------------------------
# Bloco "informações ao paciente" (bulas humanas bipartidas)
# --------------------------------------------------------------------------

# Bulas humanas brasileiras antigas costumam se dividir em dois blocos que
# dizem essencialmente a mesma coisa em registros diferentes: um em
# linguagem leiga ("INFORMAÇÕES AO PACIENTE") e outro técnico, para o
# profissional de saúde ("INFORMAÇÕES TÉCNICAS"). Generaliza o mesmo
# princípio do corte por idioma/por ANEXO — um intervalo de seções entre
# dois marcadores estruturais é redundante com o resto do documento e sai
# inteiro, para não competir consigo mesmo no BM25/busca vetorial.
_PADRAO_INFORMACOES_PACIENTE = re.compile(r"^INFORMA[CÇ][OÕ]ES AO PACIENTE", re.IGNORECASE)
_PADRAO_INFORMACOES_TECNICAS = re.compile(r"^INFORMA[CÇ][OÕ]ES T[EÉ]CNICAS", re.IGNORECASE)


def _descartar_bloco_paciente(secoes: list[SecaoExtraida], descartadas: list[dict]) -> None:
    """Descarta, em `secoes` (mutada in-place), o intervalo de seções entre
    "INFORMAÇÕES AO PACIENTE" (inclusive) e "INFORMAÇÕES TÉCNICAS"
    (exclusive) — todas as seções leigas ficam redundantes com as seções
    técnicas equivalentes que vêm depois.

    Só corta quando os DOIS marcadores aparecem, nessa ordem — sem o
    marcador técnico para confirmar onde o bloco leigo termina, não
    arrisca descartar conteúdo além do previsto (pode ser uma bula sem
    essa divisão bipartida, onde "informações ao paciente" é só uma seção
    comum entre outras).
    """
    indice_inicio = next(
        (
            i
            for i, s in enumerate(secoes)
            if s.cabecalho_original and _PADRAO_INFORMACOES_PACIENTE.search(s.cabecalho_original)
        ),
        None,
    )
    if indice_inicio is None:
        return
    indice_fim = next(
        (
            i
            for i, s in enumerate(secoes)
            if i > indice_inicio
            and s.cabecalho_original
            and _PADRAO_INFORMACOES_TECNICAS.search(s.cabecalho_original)
        ),
        None,
    )
    if indice_fim is None:
        return

    bloco_paciente = secoes[indice_inicio:indice_fim]
    del secoes[indice_inicio:indice_fim]

    for secao in bloco_paciente:
        descartadas.append(
            {
                "cabecalho": secao.cabecalho_original,
                "pagina": secao.pagina_inicial,
                "caracteres": len(secao.texto),
                "tabelas_descartadas": len(secao.tabelas),
                "amostra": secao.texto[:160],
                "motivo": "bloco_informacoes_ao_paciente",
            }
        )

    logger.warning(
        "bloco_informacoes_ao_paciente_descartado",
        secoes_descartadas=len(bloco_paciente),
        caracteres_descartados=sum(len(s.texto) for s in bloco_paciente),
        tabelas_descartadas=sum(len(s.tabelas) for s in bloco_paciente),
    )


# --------------------------------------------------------------------------
# Ciclo de produto (PDF que descreve mais de uma apresentação/espécie-alvo)
# --------------------------------------------------------------------------

# Cabeçalho que abre um novo ciclo de produto — modelos RCM/SPC da UE
# repetem o RCM inteiro uma vez por apresentação comercial, cada repetição
# começando por "1. Nome do medicamento veterinário". Não é o mesmo
# padrão do vocabulário de seção: aqui procuramos especificamente esse
# cabeçalho para saber ONDE um ciclo novo começa, não para classificar a
# seção (que já cai em "composicao" via `secoes_bula.yaml`).
_PADRAO_INICIO_CICLO = re.compile(r"^NOME DO MEDICAMENTO", re.IGNORECASE)


def _formatar_nome_ciclo(texto: str) -> str:
    """Corrige a concatenação de mais de uma apresentação sob o mesmo
    cabeçalho "Nome do medicamento veterinário".

    Um ciclo RCM/SPC pode listar mais de uma força do mesmo produto em
    linhas separadas no PDF de origem (ex. duas linhas "Produto X, 1 mg, comprimidos
    para cães" e "Produto X, 2,5 mg, comprimidos para cães", duas
    apresentações do mesmo ciclo canino). A limpeza de texto
    corrido reaproveitada de `etl/extract.py` (`_juntar_hifenizacao`) junta
    toda quebra de linha de um bloco com um espaço, sem distinguir "duas
    linhas do mesmo parágrafo" de "duas linhas de uma lista de produtos" —
    o resultado sai como uma frase corrida sem separador entre as duas
    apresentações.

    Detecta isso de forma genérica (não específica deste fármaco): o nome
    comercial é sempre a primeira palavra da frase, e não se repete dentro
    de uma única apresentação por acaso — se a primeira palavra aparece de
    novo mais adiante, é o início de uma segunda apresentação concatenada.
    Insere "; " em cada repetição. Uma apresentação única (o caso comum)
    não tem a palavra repetida e sai inalterada.
    """
    palavras = texto.split()
    if not palavras:
        return texto
    marca = palavras[0]
    reincidencias = [indice for indice, palavra in enumerate(palavras) if palavra == marca]
    if len(reincidencias) < 2:
        return texto
    partes: list[str] = []
    inicio = 0
    for indice in reincidencias[1:]:
        partes.append(" ".join(palavras[inicio:indice]))
        inicio = indice
    partes.append(" ".join(palavras[inicio:]))
    return "; ".join(partes)


def _atribuir_ciclo_de_produto(
    secoes: list[SecaoExtraida], descartadas: list[dict], caminho_farmacos: Path
) -> None:
    """Identifica, em `secoes` (mutada in-place), a qual ciclo de produto
    cada seção pertence, e descarta os ciclos cuja espécie-alvo não tem
    nenhuma sobreposição com o escopo do TCC (`ESPECIES_ESCOPO_TCC`).

    Um PDF pode descrever mais de um produto/apresentação do mesmo
    fármaco — comum em modelos RCM/SPC da UE, onde a mesma substância
    aparece em apresentações para espécies bem diferentes (cães, gatos,
    bovinos, equinos...) dentro do mesmo documento. Cada vez que uma seção
    cujo cabeçalho é "Nome do medicamento veterinário" (`_PADRAO_INICIO_CICLO`)
    é encontrada, o texto dela (o nome comercial + espécie-alvo, ex.
    "Produto Y, injetável, para bovinos, suínos e equinos") é casado contra o
    vocabulário de espécies de
    `etl/vocabulario/farmacos.yaml` (mesma função de casamento do corpus
    de livro, `etl.chunk._casar`) para saber a que espécie aquele ciclo se
    destina — nunca por inferência do restante do texto da seção, só do
    nome do produto, para não confundir com uma espécie citada de
    passagem (ex. "não deve ser administrado a gatos" dentro da seção de
    contraindicações de um produto para cães).

    Um documento sem nenhum cabeçalho desse tipo (a grande maioria das
    bulas, de produto único) não é afetado — todas as seções ficam com
    `especies_ciclo=[]`, e nada é descartado por espécie.
    """
    vocabulario_farmacos = carregar_vocabulario(caminho_farmacos)
    produto_atual: str | None = None
    especies_atual: list[str] = []
    mantidas: list[SecaoExtraida] = []
    ciclos_descartados: dict[str, list[str]] = {}

    for secao in secoes:
        if secao.cabecalho_original and _PADRAO_INICIO_CICLO.search(secao.cabecalho_original):
            produto_atual = _formatar_nome_ciclo(secao.texto.strip())
            especies_atual = _casar(produto_atual, vocabulario_farmacos.especies)

        secao.produto_ciclo = produto_atual
        secao.especies_ciclo = list(especies_atual)

        if especies_atual and not (set(especies_atual) & ESPECIES_ESCOPO_TCC):
            ciclos_descartados.setdefault(produto_atual or "?", []).append(secao.secao)
            descartadas.append(
                {
                    "cabecalho": secao.cabecalho_original,
                    "pagina": secao.pagina_inicial,
                    "caracteres": len(secao.texto),
                    "tabelas_descartadas": len(secao.tabelas),
                    "amostra": secao.texto[:160],
                    "motivo": "especie_fora_do_escopo",
                    "produto_ciclo": produto_atual,
                    "especies_ciclo": especies_atual,
                }
            )
            continue

        mantidas.append(secao)

    for produto, nomes_secao in ciclos_descartados.items():
        logger.warning(
            "ciclo_de_produto_fora_do_escopo_descartado",
            produto=produto,
            secoes_descartadas=len(nomes_secao),
        )

    secoes[:] = mantidas


# --------------------------------------------------------------------------
# Seção curta demais para virar chunk próprio
# --------------------------------------------------------------------------

# Aproximado por contagem de palavras, não pela contagem exata de tokens
# (essa só acontece no chunking, em `etl/chunk_bula.py`) — suficiente para
# um limiar aproximado, e evita acoplar este módulo ao tokenizador.
_LIMITE_PALAVRAS_SECAO_CURTA = 10


def _mesclar_secoes_curtas(secoes: list[SecaoExtraida]) -> None:
    """Funde, em `secoes` (mutada in-place), toda seção com menos de
    `_LIMITE_PALAVRAS_SECAO_CURTA` palavras na seção ANTERIOR, em vez de
    deixá-la virar um chunk próprio.

    Cobre o caso, genérico, de um cabeçalho de referência cruzada dentro
    de uma frase ("...ver item INTERAÇÕES MEDICAMENTOSAS") ficar isolado
    numa linha própria do PDF e ser lido como cabeçalho de seção de
    verdade (`_eh_candidato_a_cabecalho_caps`) — a seção resultante tem só
    o resto da frase (1-2 palavras) e não justifica um chunk à parte.

    Roda por ÚLTIMO no pipeline de pós-processamento de `extrair` — depois
    de `_descartar_bloco_em_espanhol`, `_descartar_bloco_paciente` e
    `_atribuir_ciclo_de_produto`, que dependem de encontrar cabeçalhos
    específicos (ex. "Nome do medicamento veterinário", tipicamente CURTO,
    só o nome comercial) em `secoes` para funcionar — se a fusão rodasse
    antes, poderia apagar exatamente os cabeçalhos que esses mecanismos
    procuram, antes que eles tivessem a chance de agir.

    Nunca funde uma seção com tabela, mesmo curta — uma tabela é uma
    unidade própria (`etl/chunk_bula.py`), independente do texto ao redor.
    A primeira seção do documento, sem antecessora, nunca é fundida (fica
    como está, mesmo curta).
    """
    i = 1
    fundidas = 0
    while i < len(secoes):
        secao = secoes[i]
        if not secao.tabelas and len(secao.texto.split()) < _LIMITE_PALAVRAS_SECAO_CURTA:
            anterior = secoes[i - 1]
            logger.info(
                "secao_curta_fundida_na_anterior",
                cabecalho=secao.cabecalho_original,
                cabecalho_anterior=anterior.cabecalho_original,
                palavras=len(secao.texto.split()),
            )
            anterior.texto = f"{anterior.texto}\n\n{secao.texto}".strip()
            del secoes[i]
            fundidas += 1
            continue
        i += 1
    if fundidas:
        logger.info("secoes_curtas_fundidas", total=fundidas)


def extrair(
    caminho_pdf: Path,
    vocabulario: VocabularioSecoes,
    caminho_farmacos: Path = CAMINHO_VOCABULARIO_FARMACOS_PADRAO,
) -> tuple[list[SecaoExtraida], list[dict]]:
    """Extrai e segmenta uma bula por seção.

    Devolve `(secoes_mantidas, secoes_descartadas)` — a segunda lista é só
    para auditoria/log, nunca vira chunk.
    """
    documento = pymupdf.open(caminho_pdf)

    ultima_pagina = _ultima_pagina_do_primeiro_anexo(documento)
    if ultima_pagina < documento.page_count:
        logger.warning(
            "paginas_fora_do_primeiro_anexo_ignoradas",
            origem=str(caminho_pdf),
            paginas_totais=documento.page_count,
            ultima_pagina_processada=ultima_pagina,
            paginas_ignoradas=documento.page_count - ultima_pagina,
        )

    secoes: list[SecaoExtraida] = []
    descartadas: list[dict] = []

    # Texto antes do primeiro cabeçalho reconhecido (título comercial,
    # forma farmacêutica) não é descartável por padrão — não há cabeçalho
    # a casar contra o vocabulário de descarte, então é mantido em
    # "outros" e fica sujeito à mesma conferência de log.
    estado = _EstadoSecao(
        secao="outros", cabecalho_original=None, descartar=False, pagina_inicial=1
    )
    linhas_administrativas_removidas = 0
    numeros_de_pagina_removidos = 0
    paragrafos_administrativos_removidos = 0
    blocos_administrativos_removidos = 0
    tabelas_descartadas_contagem = 0
    # Carrega uma remoção de `_remover_blocos_administrativos` que ainda não
    # achou cabeçalho de parada do bloco anterior para o próximo (ver
    # docstring da função) — reiniciado por documento, não por página, já
    # que a lacuna que separa os blocos pode ficar entre duas páginas.
    bloco_administrativo_em_andamento = False

    with pdfplumber.open(caminho_pdf) as documento_plumber:
        for numero_pagina in range(1, ultima_pagina + 1):
            pagina_fitz = documento[numero_pagina - 1]
            pagina_plumber = documento_plumber.pages[numero_pagina - 1]

            tabelas_md, bboxes = _extrair_tabelas(pagina_plumber)
            blocos = _blocos_da_pagina(pagina_fitz)

            # A ordem NATURAL do PyMuPDF (não reordenada por y0) já é
            # ordem de leitura correta mesmo em bulas de múltiplas colunas
            # — ordenar tudo por y0 misturaria coluna 1 com coluna 2/3,
            # porque a coordenada vertical de um bloco não é comparável
            # entre colunas diferentes. Cada tabela é inserida na posição
            # do primeiro bloco que ela sobrepõe (é aí que ela apareceria
            # no fluxo natural); os demais blocos sobrepostos por essa
            # tabela são só pulados, nunca duplicados no texto corrido.
            tabela_emitida = [False] * len(bboxes)
            itens: list[tuple[str, object]] = []
            for bloco in blocos:
                sobrepostos = [i for i, bbox in enumerate(bboxes) if _sobrepoe(bloco, bbox)]
                if sobrepostos:
                    for indice in sobrepostos:
                        if not tabela_emitida[indice]:
                            itens.append(("tabela", (tabelas_md[indice], bboxes[indice])))
                            tabela_emitida[indice] = True
                    continue
                itens.append(("bloco", bloco))

            for tipo, payload in itens:
                if tipo == "tabela":
                    markdown, _bbox = payload
                    legenda = _procurar_legenda(
                        estado.partes_texto, estado.cabecalho_original, estado.secao
                    )
                    # Uma tabela é indivisível por padrão (nunca cortada,
                    # nunca misturada com texto) — mas algumas bulas têm
                    # tabelas sem valor clínico à parte (ex. estudo
                    # farmacocinético populacional por faixa etária e
                    # sexo): `tabelas_descartadas` casa contra a legenda
                    # (a frase introdutória mais próxima, tipicamente a
                    # própria legenda "Tabela N: ...") e, se bater, a
                    # tabela não entra em `estado.tabelas` — vira uma
                    # tabela a menos no chunk, nunca um chunk truncado.
                    if vocabulario.tabelas_descartadas and vocabulario.tabelas_descartadas.search(
                        legenda
                    ):
                        tabelas_descartadas_contagem += 1
                        logger.info(
                            "tabela_descartada",
                            pagina=numero_pagina,
                            secao=estado.secao,
                            legenda=legenda,
                            amostra=markdown[:120],
                        )
                        continue
                    estado.tabelas.append(TabelaExtraida(markdown=markdown, legenda=legenda))
                    # Uma tabela com 0 linhas de dados (só cabeçalho +
                    # separador) costuma ser o `find_tables()` do
                    # pdfplumber capturando só um fragmento de uma grade
                    # maior (bordas não fecham células limpamente) — não
                    # corrigimos automaticamente (a regra "tabela é
                    # unidade indivisível" impede completar por conta
                    # própria), só sinalizamos para conferência manual do
                    # PDF de origem. Conta linhas pelo separador real de
                    # linha da tabela ("|\n|"), não por `\n` cru — uma
                    # célula pode ter quebra de linha embutida.
                    total_linhas = markdown.count("|\n|") + 1
                    linhas_dados = total_linhas - 2  # desconta cabeçalho e separador
                    if linhas_dados <= 0:
                        logger.warning(
                            "tabela_possivelmente_fragmentada",
                            pagina=numero_pagina,
                            secao=estado.secao,
                            linhas_dados=linhas_dados,
                            amostra=markdown[:120],
                        )
                    continue

                bloco: _Bloco = payload
                # Roda ANTES da segmentação, sobre o bloco inteiro — não
                # depois, como as outras varreduras (ver docstring de
                # `_remover_blocos_administrativos`): o conteúdo que remove
                # (ex. passos numerados de instrução ilustrada) é, por si
                # só, cabeçalho numerado de sinal forte, que a segmentação
                # trataria como início de seção antes de qualquer varredura
                # rodar sobre o resultado.
                texto_bloco_bruto, blocos_removidos, bloco_administrativo_em_andamento = (
                    _remover_blocos_administrativos(
                        bloco.texto, vocabulario, bloco_administrativo_em_andamento
                    )
                )
                blocos_administrativos_removidos += blocos_removidos
                # Um bloco pode conter vários cabeçalhos "enterrados" nele
                # (ver `_dividir_bloco_em_segmentos`) — não só na primeira
                # linha. O primeiro segmento (secao=None) é continuação da
                # seção já aberta antes deste bloco; os demais abrem seção
                # nova, um de cada vez, na ordem em que aparecem.
                for (
                    secao_segmento,
                    descartar_segmento,
                    cabecalho_segmento,
                    texto_bloco,
                ) in _dividir_bloco_em_segmentos(texto_bloco_bruto, vocabulario):
                    if secao_segmento is not None:
                        _fechar_secao(estado, secoes, descartadas)
                        estado = _EstadoSecao(
                            secao=secao_segmento,
                            cabecalho_original=cabecalho_segmento,
                            descartar=bool(descartar_segmento),
                            pagina_inicial=numero_pagina,
                        )

                    # A varredura de linha só se aplica dentro de uma seção
                    # já aceita — uma seção descartada (ex.: FABRICANTE) já
                    # vai inteira para `descartadas`, não precisa de poda
                    # linha a linha.
                    if not estado.descartar:
                        texto_bloco, removidos_paragrafo = _remover_paragrafos_administrativos(
                            texto_bloco, vocabulario
                        )
                        paragrafos_administrativos_removidos += removidos_paragrafo
                        texto_bloco, removidas_pagina = _remover_numeros_de_pagina(texto_bloco)
                        numeros_de_pagina_removidos += removidas_pagina
                        texto_bloco, removidas = _remover_linhas_administrativas(
                            texto_bloco, vocabulario
                        )
                        linhas_administrativas_removidas += removidas

                    texto_limpo = _limpar_bloco(texto_bloco)
                    if texto_limpo:
                        estado.partes_texto.append(texto_limpo)

    _fechar_secao(estado, secoes, descartadas)

    _descartar_bloco_em_espanhol(secoes, descartadas)
    _descartar_bloco_paciente(secoes, descartadas)
    _atribuir_ciclo_de_produto(secoes, descartadas, caminho_farmacos)
    _mesclar_secoes_curtas(secoes)

    for descarte in descartadas:
        logger.info("secao_descartada", **descarte)

    logger.info(
        "linhas_administrativas_removidas",
        origem=str(caminho_pdf),
        linhas=linhas_administrativas_removidas,
    )
    logger.info(
        "numeros_de_pagina_removidos",
        origem=str(caminho_pdf),
        linhas=numeros_de_pagina_removidos,
    )
    logger.info(
        "paragrafos_administrativos_removidos",
        origem=str(caminho_pdf),
        paragrafos=paragrafos_administrativos_removidos,
    )
    logger.info(
        "blocos_administrativos_removidos",
        origem=str(caminho_pdf),
        blocos=blocos_administrativos_removidos,
    )
    if bloco_administrativo_em_andamento:
        # Uma remoção que chega ao fim do documento sem achar cabeçalho de
        # parada é sinal de vocabulário `blocos_administrativos` amplo
        # demais para este PDF (casou perto do fim, sem seção real depois
        # para servir de limite) — provavelmente engoliu conteúdo demais.
        logger.warning(
            "bloco_administrativo_sem_cabecalho_de_parada",
            origem=str(caminho_pdf),
        )
    logger.info(
        "tabelas_descartadas_total",
        origem=str(caminho_pdf),
        tabelas=tabelas_descartadas_contagem,
    )
    logger.info(
        "extracao_bula_concluida",
        origem=str(caminho_pdf),
        paginas_totais=documento.page_count,
        paginas_processadas=ultima_pagina,
        secoes_mantidas=len(secoes),
        secoes_descartadas=len(descartadas),
        tabelas_mantidas=sum(len(s.tabelas) for s in secoes),
        tabelas_descartadas=tabelas_descartadas_contagem,
        linhas_administrativas_removidas=linhas_administrativas_removidas,
        numeros_de_pagina_removidos=numeros_de_pagina_removidos,
        paragrafos_administrativos_removidos=paragrafos_administrativos_removidos,
        blocos_administrativos_removidos=blocos_administrativos_removidos,
    )
    return secoes, descartadas


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _serializar_secao(secao: SecaoExtraida) -> dict:
    return {
        "secao": secao.secao,
        "cabecalho_original": secao.cabecalho_original,
        "pagina_inicial": secao.pagina_inicial,
        "texto": secao.texto,
        "tabelas": [{"markdown": t.markdown, "legenda": t.legenda} for t in secao.tabelas],
        "produto_ciclo": secao.produto_ciclo,
        "especies_ciclo": secao.especies_ciclo,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Caminho do PDF da bula")
    parser.add_argument(
        "--vocabulario-secoes",
        type=Path,
        default=CAMINHO_VOCABULARIO_SECOES_PADRAO,
        help="Dicionário controlado de cabeçalhos (default: etl/vocabulario/secoes_bula.yaml)",
    )
    parser.add_argument(
        "--vocabulario-farmacos",
        type=Path,
        default=CAMINHO_VOCABULARIO_FARMACOS_PADRAO,
        help="Dicionário controlado de espécies, para ciclos de produto "
        "multiespécie (default: etl/vocabulario/farmacos.yaml)",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Arquivo JSONL de saída (uma seção por linha); default: stdout",
    )
    args = parser.parse_args(argv)

    vocabulario = carregar_vocabulario_secoes(args.vocabulario_secoes)
    secoes, _descartadas = extrair(args.source, vocabulario, args.vocabulario_farmacos)

    linhas = [json.dumps(_serializar_secao(s), ensure_ascii=False) for s in secoes]

    if args.saida:
        args.saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        logger.info("saida_gravada", caminho=str(args.saida), linhas=len(linhas))
    else:
        for linha in linhas:
            print(linha)  # noqa: T201 — saída de dados do CLI, não log de depuração

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
