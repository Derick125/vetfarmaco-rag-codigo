# CREDITOS_ARTE.md — Origem e licença da arte do app

Toda a arte do app é **autoria do projeto**: desenhos originais, criados em código e em
SVG para este TCC, sem arquivo, traçado, personagem ou pacote de terceiros e sem licença
externa a cumprir. Nenhum personagem conhecido. Os desenhos passaram por
pré-visualização aprovada pelo autor antes de entrar no app
(`docs/FRONTEND_SPEC.md` §26–27).

| Arte | Arquivos | Onde aparece | Autoria / licença |
|---|---|---|---|
| Ícone `VetFarmaco`: cápsula com marca de pata, nas cores do design system (`metileno`, `paper`, verde-evidência claro `#86C7A2`) | `app/assets/brand/icone.svg`, `icone_pequeno.svg` (32 dp ou menos, só a cápsula), `icone_primeiro_plano.svg`; PNGs `icone_1024.png` e `icone_primeiro_plano_1024.png`; réplica em código em `app/lib/shared/widgets/icone_vetfarmaco.dart` | ícone do app no Android (`flutter_launcher_icons`), avatar da resposta e marca da abertura | Autoria do projeto (desenho original); uso livre no TCC e no app |

## Regras de uso

- Sem ilustração na nova consulta, na resposta, no alerta, em `Sem evidência`, `Sem conexão`, falha ou tempo
  esgotado: nas telas clínicas a sobriedade é intencional, e a nova consulta é o início do caminho medido.
- Arte de terceiros só entra com licença livre verificada **na hora do download**, com autor, URL, licença e
  data registrados nesta tabela.

## Ilustrações (conjunto v2)

Autoria do projeto: desenho original em SVG, sem material de terceiros, com formas preenchidas, dois ou três
tons e sombras suaves, no mesmo estilo. Paleta: azul de metileno `#17506B`, fundo `#F4F6F4`, verde `#86C7A2` e
um tom de apoio (areia `#E3CFAE`), com tons derivados de cada um. Cada cena existe nos temas claro e escuro.
Sem medicamento identificável (cápsula lisa; frasco com rótulo em branco).

| Cena | Onde aparece | Conteúdo |
|---|---|---|
| `abertura` | abertura | cão e gato sentados com o ícone da marca |
| `intro_cartao1` | introdução, cartão 1 | cão e gato com um livro aberto |
| `intro_cartao3` | introdução, cartão 3 | celular com uma lista de respostas salvas, o selo de data e o símbolo de «sem rede» |
| `historico_vazio` | histórico vazio | gato dormindo sobre livros |
| `sobre_faixa` | tela Sobre (faixa no topo) | cão, gato, cápsula e frasco |
| `inicio_cabecalho` | tela inicial (cabeçalho) | cão e gato pequenos |

- **Fonte dos desenhos:** `app/assets/arte_fonte/*.svg`, gerados por `app/tool/gerar_arte.py` a partir de uma
  paleta por tema.
- **Formato no app:** o Flutter não desenha SVG sem um pacote extra, então o app usa PNG com fundo transparente em
  1x, 2x e 3x por tema (`app/assets/img/`, `2.0x/`, `3.0x/`), exportados por `app/tool/exportar_png.py`. São 36
  arquivos, cerca de 1,5 MB no total. `test/shared/widgets/ilustracao_vetfarmaco_test.dart` confere as três
  densidades, o canal alfa e a proporção de cada um.

## Fontes

| Fonte | Arquivos em `app/assets/fonts/` | Autoria e licença | Origem |
|---|---|---|---|
| IBM Plex Sans (Regular, Medium, SemiBold, Bold) | `IBMPlexSans-*.ttf`, `LICENSE-IBMPlexSans.txt` | © 2017 IBM Corp., nome reservado «Plex»; desenho de Mike Abbink (IBM) e Bold Monday. **SIL Open Font License 1.1**. | Arquivos estáticos **oficiais, sem modificação**, de `@ibm/plex-sans@1.1.0` em <https://github.com/IBM/plex/releases> |
| IBM Plex Serif (Regular, Italic) | `IBMPlexSerif-*.ttf`, `LICENSE-IBMPlexSerif.txt` | idem | idem, `@ibm/plex-serif@2.0.0` |

A OFL permite usar, incorporar e redistribuir a fonte, inclusive dentro de um aplicativo; proíbe vendê-la
isoladamente e usar o nome reservado em versões modificadas. Por isso os arquivos são os originais da IBM, e
`test/core/theme/fontes_test.dart` confere o `sha256` de cada um:

| Arquivo | sha256 |
|---|---|
| `IBMPlexSans-Regular.ttf` | `975dcda37d80f038dcd143c22e33ca2d97a0cc5a929aace1c749153b0fe1afa5` |
| `IBMPlexSans-Medium.ttf` | `331c8639d7598b2cde62a911a71db195e30cb655cd6bdf2e324a7e984955f907` |
| `IBMPlexSans-SemiBold.ttf` | `a20caf8286023a6a7a85e40b1d2a4ae9fc3e3b1f9eda8f4c542dd4986af67bb1` |
| `IBMPlexSans-Bold.ttf` | `9e6c74a889a700d707613d24548fe4ffa6bc59559a0689d2cf9e133bdcdafb2f` |
| `IBMPlexSerif-Regular.ttf` | `6c490ccd38e856c674e0d163f3f40742a75058b7b935998dbfbc1745ba54e474` |
| `IBMPlexSerif-Italic.ttf` | `d28aa63cf618439712d6b459c5649af1d6d789cb911994f2357f1ce44128f163` |

Papéis: Plex Sans em toda a interface e no texto gerado pelo modelo; Plex Serif **só** nos trechos literais
do acervo (`docs/FRONTEND_SPEC.md` §2). O pacote `google_fonts` foi removido: nenhuma fonte é baixada em
execução.
