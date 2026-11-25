"""Gera o conjunto de ilustrações do VetFarmaco (fonte das imagens; o app usa os PNG de `assets/img/`,
exportados por `tool/exportar_png.py`) (SVG, formas preenchidas, 2-3 tons, sombras suaves).

Cada cena sai em dois temas (claro e escuro) a partir da mesma paleta, para o estilo ser um só.
Paleta da marca: metileno #17506B, papel #F4F6F4, verde #86C7A2 + um tom de apoio (areia).
Nenhum medicamento identificável: cápsula lisa e frasco com rótulo em branco.
"""

import sys
from pathlib import Path

SAIDA = Path(__file__).resolve().parent.parent / "assets" / "arte_fonte"

BASE = dict(
    metileno="#17506B",
    verde="#86C7A2", verde_esc="#5BA67E", verde_cla="#BFE3CE",
    areia="#E3CFAE", areia_esc="#C9AE84", areia_cla="#F3E9D6", orelha_cao="#B8976A",
    gato="#7A9FB2", gato_esc="#5E8498", gato_cla="#C3D8E1", gato_orelha="#EAF2F5", nariz_gato="#46687A",
    tinta="#1F2D33", azul_claro="#A9CBDA", metal="#8FA7B3", metal_esc="#6F8896",
)
TEMAS = {
    "claro": dict(
        BASE,
        spot="#86C7A2", spot_op=".24", sombra="#17506B", sombra_op=".18",
        pagina="#FFFFFF", linha="#C9D6D0", capa="#17506B", capa_esc="#103B50",
        tapete="#BFE3CE", tapete_op=".55",
    ),
    "escuro": dict(
        BASE,
        areia="#E8D5B5", gato="#86AABD", gato_esc="#6A90A4",
        spot="#86C7A2", spot_op=".16", sombra="#000000", sombra_op=".55",
        pagina="#DCE5E1", linha="#AEBDB6", capa="#2F7396", capa_esc="#245A75",
        tapete="#86C7A2", tapete_op=".22",
    ),
}


def defs():
    return (
        '<defs><filter id="b" x="-30%" y="-80%" width="160%" height="260%">'
        '<feGaussianBlur stdDeviation="5"/></filter>'
        '<filter id="b2" x="-30%" y="-80%" width="160%" height="260%">'
        '<feGaussianBlur stdDeviation="2.4"/></filter></defs>'
    )


def sombra(P, cx, cy, rx, ry):
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{P["sombra"]}" '
            f'opacity="{P["sombra_op"]}" filter="url(#b)"/>')


def spot(P, cx, cy, r):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{P["spot"]}" opacity="{P["spot_op"]}"/>'


def cao(P, x, y, s=1.0, espelhar=False):
    f = -1 if espelhar else 1
    g = [f'<g transform="translate({x} {y}) scale({s * f} {s})">']
    g.append(sombra(P, 0, 2, 58, 9))
    # rabo (atrás do corpo)
    g.append(f'<path d="M38,-40 C70,-52 80,-84 62,-96" fill="none" stroke="{P["areia_esc"]}" '
             f'stroke-width="12" stroke-linecap="round"/>')
    # corpo
    g.append(f'<path d="M-40,-4 C-52,-40 -42,-92 0,-98 C42,-92 52,-40 40,-4 Z" fill="{P["areia"]}"/>')
    g.append(f'<ellipse cx="0" cy="-48" rx="24" ry="38" fill="{P["areia_cla"]}"/>')
    g.append(f'<ellipse cx="-36" cy="-22" rx="15" ry="18" fill="{P["areia_esc"]}" opacity=".35"/>')
    g.append(f'<ellipse cx="36" cy="-22" rx="15" ry="18" fill="{P["areia_esc"]}" opacity=".35"/>')
    # patas
    for px in (-16, 16):
        g.append(f'<rect x="{px - 8}" y="-52" width="16" height="46" rx="8" fill="{P["areia"]}"/>')
        g.append(f'<ellipse cx="{px}" cy="-6" rx="12" ry="7" fill="{P["areia_cla"]}"/>')
    # coleira
    g.append(f'<path d="M-27,-92 Q0,-82 27,-92 L25,-83 Q0,-73 -25,-83 Z" fill="{P["verde"]}"/>')
    g.append(f'<circle cx="0" cy="-75" r="6" fill="{P["verde_esc"]}"/>')
    # cabeça
    g.append(f'<ellipse cx="0" cy="-112" rx="38" ry="34" fill="{P["areia"]}"/>')
    g.append(f'<path d="M-30,-134 C-62,-132 -66,-92 -48,-84 C-38,-82 -30,-100 -28,-116 Z" fill="{P["orelha_cao"]}"/>')
    g.append(f'<path d="M30,-134 C62,-132 66,-92 48,-84 C38,-82 30,-100 28,-116 Z" fill="{P["orelha_cao"]}"/>')
    g.append(f'<ellipse cx="0" cy="-102" rx="21" ry="15" fill="{P["areia_cla"]}"/>')
    g.append(f'<ellipse cx="0" cy="-108" rx="7" ry="5" fill="{P["tinta"]}"/>')
    g.append('<ellipse cx="-2" cy="-109.6" rx="2.4" ry="1.2" fill="#FFFFFF" opacity=".55"/>')
    g.append(f'<path d="M0,-103 v4 M0,-99 q-5,5 -10,1 M0,-99 q5,5 10,1" fill="none" stroke="{P["tinta"]}" '
             f'stroke-width="2" stroke-linecap="round"/>')
    for ex in (-15, 15):
        g.append(f'<circle cx="{ex}" cy="-120" r="4.6" fill="{P["tinta"]}"/>')
        g.append(f'<circle cx="{ex + 1.4}" cy="-121.4" r="1.5" fill="#FFFFFF"/>')
    g.append('</g>')
    return "".join(g)


def gato(P, x, y, s=1.0, espelhar=False):
    f = -1 if espelhar else 1
    g = [f'<g transform="translate({x} {y}) scale({s * f} {s})">']
    g.append(sombra(P, 0, 2, 54, 9))
    g.append(f'<path d="M34,-8 C74,-8 84,-52 62,-70" fill="none" stroke="{P["gato_esc"]}" '
             f'stroke-width="14" stroke-linecap="round"/>')
    g.append(f'<path d="M-38,-4 C-46,-36 -36,-84 0,-88 C36,-84 46,-36 38,-4 Z" fill="{P["gato"]}"/>')
    g.append(f'<ellipse cx="0" cy="-44" rx="20" ry="34" fill="{P["gato_cla"]}"/>')
    for px in (-13, 13):
        g.append(f'<rect x="{px - 7}" y="-42" width="14" height="36" rx="7" fill="{P["gato"]}"/>')
        g.append(f'<ellipse cx="{px}" cy="-6" rx="10" ry="6" fill="{P["gato_cla"]}"/>')
    g.append(f'<path d="M-23,-84 Q0,-76 23,-84 L21,-77 Q0,-69 -21,-77 Z" fill="{P["areia"]}"/>')
    g.append(f'<circle cx="0" cy="-70" r="5" fill="{P["areia_esc"]}"/>')
    g.append(f'<ellipse cx="0" cy="-104" rx="38" ry="31" fill="{P["gato"]}"/>')
    for sx in (-1, 1):
        g.append(f'<path d="M{sx * 34},-120 L{sx * 30},-152 L{sx * 6},-128 Z" fill="{P["gato"]}" '
                 f'stroke="{P["gato"]}" stroke-width="6" stroke-linejoin="round"/>')
        g.append(f'<path d="M{sx * 29},-124 L{sx * 27},-143 L{sx * 13},-128 Z" fill="{P["gato_orelha"]}" '
                 f'stroke="{P["gato_orelha"]}" stroke-width="3" stroke-linejoin="round"/>')
        g.append(f'<ellipse cx="{sx * 14}" cy="-94" rx="16" ry="11" fill="{P["gato_cla"]}"/>')
    for ex in (-14, 14):
        g.append(f'<ellipse cx="{ex}" cy="-108" rx="6.2" ry="7.6" fill="{P["verde"]}"/>')
        g.append(f'<ellipse cx="{ex}" cy="-108" rx="2" ry="5.4" fill="{P["tinta"]}"/>')
        g.append(f'<circle cx="{ex + 1.8}" cy="-110.6" r="1.6" fill="#FFFFFF"/>')
    g.append(f'<path d="M-3.6,-96 h7.2 l-3.6,4.6 Z" fill="{P["nariz_gato"]}"/>')
    g.append(f'<path d="M0,-91.4 v3 M0,-88.4 q-4,4 -8,1 M0,-88.4 q4,4 8,1" fill="none" stroke="{P["tinta"]}" '
             f'stroke-width="1.8" stroke-linecap="round"/>')
    for sx in (-1, 1):
        for (x1, y1, x2, y2) in ((22, -92, 52, -97), (22, -89, 53, -88), (22, -86, 50, -79)):
            g.append(f'<path d="M{sx * x1},{y1} L{sx * x2},{y2}" stroke="#FFFFFF" stroke-width="1.4" '
                     f'stroke-linecap="round" opacity=".8"/>')
    g.append('</g>')
    return "".join(g)


def selo(P, x, y, tam):
    """Ícone da marca (cápsula com pata) em quadrado arredondado."""
    k = tam / 1024
    cid = f"sel{int(x)}{int(y)}"
    return (
        f'<g transform="translate({x} {y})">'
        f'<ellipse cx="{tam / 2}" cy="{tam + 6}" rx="{tam * 0.42}" ry="5" fill="{P["sombra"]}" '
        f'opacity="{P["sombra_op"]}" filter="url(#b2)"/>'
        f'<clipPath id="{cid}"><rect width="{tam}" height="{tam}" rx="{tam * 0.22}"/></clipPath>'
        f'<g clip-path="url(#{cid})"><g transform="scale({k})">'
        '<rect width="1024" height="1024" fill="#17506B"/>'
        '<g transform="rotate(-45 512 512)">'
        '<clipPath id="e' + cid + '"><rect x="212" y="377" width="300" height="270"/></clipPath>'
        '<clipPath id="d' + cid + '"><rect x="512" y="377" width="300" height="270"/></clipPath>'
        f'<rect x="212" y="377" width="600" height="270" rx="135" fill="#F4F6F4" clip-path="url(#e{cid})"/>'
        f'<rect x="212" y="377" width="600" height="270" rx="135" fill="#86C7A2" clip-path="url(#d{cid})"/>'
        '<rect x="508" y="377" width="8" height="270" fill="#17506B"/></g>'
        '<g fill="#17506B"><ellipse cx="406" cy="650" rx="54" ry="42"/>'
        '<ellipse cx="344" cy="598" rx="20" ry="27" transform="rotate(-25 344 598)"/>'
        '<ellipse cx="385" cy="566" rx="20" ry="28" transform="rotate(-8 385 566)"/>'
        '<ellipse cx="437" cy="566" rx="20" ry="28" transform="rotate(8 437 566)"/>'
        '<ellipse cx="478" cy="598" rx="20" ry="27" transform="rotate(25 478 598)"/></g>'
        '</g></g></g>'
    )


def livro_aberto(P, x, y, s=1.0):
    def pt(q, v, u):
        a, b, c, d = q
        top = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        bot = (d[0] + (c[0] - d[0]) * u, d[1] + (c[1] - d[1]) * u)
        return (top[0] + (bot[0] - top[0]) * v, top[1] + (bot[1] - top[1]) * v)

    esq = [(-108, -56), (-4, -48), (-4, 2), (-108, -8)]
    dir_ = [(108, -56), (4, -48), (4, 2), (108, -8)]
    g = [f'<g transform="translate({x} {y}) scale({s})">']
    g.append(sombra(P, 0, 14, 124, 10))
    g.append(f'<polygon points="-116,-60 0,-52 116,-60 116,0 0,10 -116,0" fill="{P["capa"]}"/>')
    g.append(f'<polygon points="-116,-8 0,2 116,-8 116,0 0,10 -116,0" fill="{P["capa_esc"]}"/>')
    for q in (esq, dir_):
        g.append('<polygon points="' + " ".join(f"{a},{b}" for a, b in q) + f'" fill="{P["pagina"]}"/>')
    g.append(f'<polygon points="-108,-8 -4,2 -4,6 -108,-3" fill="{P["linha"]}"/>')
    g.append(f'<polygon points="108,-8 4,2 4,6 108,-3" fill="{P["linha"]}"/>')
    for q in (esq, dir_):
        for i, v in enumerate((0.2, 0.36, 0.52, 0.68)):
            u0, u1 = (0.12, 0.88) if i != 3 else (0.12, 0.6)
            a = pt(q, v, u0)
            b = pt(q, v, u1)
            g.append(f'<path d="M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f}" stroke="{P["linha"]}" '
                     f'stroke-width="3.2" stroke-linecap="round"/>')
    g.append(f'<path d="M-3,-51 L-3,16 L1,12 L5,16 L5,-50 Z" fill="{P["verde"]}"/>')
    g.append('</g>')
    return "".join(g)


def livro_fechado(P, x, y, cor_capa, largura=240, esp=46):
    h = largura / 2
    g = [f'<g transform="translate({x} {y})">']
    g.append(sombra(P, 0, 4, h + 8, 9))
    g.append(f'<rect x="{-h}" y="{-esp}" width="{largura}" height="{esp}" rx="9" fill="{cor_capa}"/>')
    g.append(f'<rect x="{-h + 7}" y="{-esp + 9}" width="{largura - 14}" height="{esp - 18}" rx="4" '
             f'fill="{P["pagina"]}"/>')
    for i in range(3):
        yy = -esp + 17 + i * 6.6
        g.append(f'<path d="M{-h + 14},{yy:.1f} H{h - 14}" stroke="{P["linha"]}" stroke-width="1.8"/>')
    g.append(f'<rect x="{-h}" y="{-esp}" width="14" height="{esp}" rx="7" fill="{P["verde_esc"] if cor_capa == P["capa"] else P["capa"]}" opacity=".55"/>')
    g.append('</g>')
    return "".join(g)


def gato_dormindo(P, x, y, s=1.0):
    g = [f'<g transform="translate({x} {y}) scale({s})">']
    g.append(f'<path d="M58,-26 C92,-24 96,6 66,6 C56,6 50,0 52,-6" fill="none" stroke="{P["gato_esc"]}" '
             f'stroke-width="13" stroke-linecap="round"/>')
    g.append(f'<ellipse cx="6" cy="-24" rx="66" ry="27" fill="{P["gato"]}"/>')
    g.append(f'<ellipse cx="14" cy="-12" rx="46" ry="12" fill="{P["gato_cla"]}"/>')
    g.append(f'<ellipse cx="-34" cy="-8" rx="15" ry="7" fill="{P["gato_cla"]}"/>')
    g.append(f'<ellipse cx="-50" cy="-24" rx="29" ry="24" fill="{P["gato"]}"/>')
    for sx0, sx1, sx2 in ((-72, -66, -52), (-40, -32, -22)):
        g.append(f'<path d="M{sx0},-40 L{sx1},-62 L{sx2},-44 Z" fill="{P["gato"]}" stroke="{P["gato"]}" '
                 f'stroke-width="5" stroke-linejoin="round"/>')
    g.append(f'<ellipse cx="-50" cy="-14" rx="16" ry="9" fill="{P["gato_cla"]}"/>')
    for ex in (-60, -40):
        g.append(f'<path d="M{ex - 6},-26 q6,6 12,0" fill="none" stroke="{P["tinta"]}" stroke-width="2.4" '
                 f'stroke-linecap="round"/>')
    g.append(f'<path d="M-53.5,-17 h7 l-3.5,4.4 Z" fill="{P["nariz_gato"]}"/>')
    g.append(f'<path d="M-30,-70 h14 l-14,15 h14 M-6,-96 h10 l-10,11 h10" fill="none" stroke="{P["verde_esc"]}" '
             f'stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>')
    g.append('</g>')
    return "".join(g)


def capsula(P, x, y, rot=-30, c=1.0, c1=None, c2=None):
    c1 = c1 or P["gato"]
    c2 = c2 or P["verde"]
    return (
        f'<g transform="translate({x} {y}) rotate({rot}) scale({c})">'
        f'<ellipse cx="0" cy="32" rx="44" ry="6" fill="{P["sombra"]}" opacity="{P["sombra_op"]}" filter="url(#b2)" transform="rotate({-rot})"/>'
        f'<clipPath id="ce{int(x)}{int(y)}"><rect x="-46" y="-18" width="46" height="36"/></clipPath>'
        f'<clipPath id="cd{int(x)}{int(y)}"><rect x="0" y="-18" width="46" height="36"/></clipPath>'
        f'<rect x="-46" y="-18" width="92" height="36" rx="18" fill="{c1}" clip-path="url(#ce{int(x)}{int(y)})"/>'
        f'<rect x="-46" y="-18" width="92" height="36" rx="18" fill="{c2}" clip-path="url(#cd{int(x)}{int(y)})"/>'
        f'<rect x="-40" y="-13" width="76" height="6" rx="3" fill="#FFFFFF" opacity=".35"/></g>'
    )


def frasco(P, x, y, s=1.0):
    return (
        f'<g transform="translate({x} {y}) scale({s})">'
        f'{sombra(P, 0, 4, 34, 7)}'
        f'<rect x="-24" y="-92" width="48" height="92" rx="12" fill="{P["azul_claro"]}"/>'
        f'<rect x="-24" y="-92" width="14" height="92" rx="7" fill="#FFFFFF" opacity=".28"/>'
        f'<rect x="-20" y="-112" width="40" height="26" rx="7" fill="{P["capa"] if P["capa"] != "#17506B" else P["metileno"]}"/>'
        f'<rect x="-20" y="-112" width="40" height="8" rx="4" fill="#FFFFFF" opacity=".2"/>'
        f'<rect x="-24" y="-66" width="48" height="38" fill="{P["pagina"]}"/>'
        f'<rect x="-15" y="-56" width="30" height="5" rx="2.5" fill="{P["linha"]}"/>'
        f'<rect x="-15" y="-46" width="22" height="5" rx="2.5" fill="{P["linha"]}" opacity=".7"/>'
        f'</g>'
    )


def folha(P, x, y, rot, s=1.0):
    return (f'<g transform="translate({x} {y}) rotate({rot}) scale({s})">'
            f'<path d="M0,0 C-14,-16 -12,-40 0,-54 C12,-40 14,-16 0,0 Z" fill="{P["verde"]}"/>'
            f'<path d="M0,0 L0,-46" stroke="{P["verde_esc"]}" stroke-width="2" opacity=".6"/></g>')


def svg(w, h, corpo):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'{defs()}{corpo}</svg>\n')


def cena_abertura(P):
    c = [spot(P, 240, 190, 150),
         f'<ellipse cx="240" cy="304" rx="196" ry="15" fill="{P["tapete"]}" opacity="{P["tapete_op"]}"/>',
         cao(P, 150, 300, 1.0), gato(P, 332, 300, 0.97, espelhar=True),
         selo(P, 198, 56, 84)]
    for (cx, cy, r) in ((150, 78, 5), (316, 62, 4), (352, 104, 6), (118, 120, 3.5)):
        c.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{P["verde"]}" opacity=".55"/>')
    return svg(480, 360, "".join(c))


def cena_cartao1(P):
    c = [spot(P, 240, 190, 150),
         f'<ellipse cx="240" cy="300" rx="196" ry="15" fill="{P["tapete"]}" opacity="{P["tapete_op"]}"/>',
         cao(P, 92, 290, 0.98), gato(P, 388, 290, 0.95, espelhar=True),
         livro_aberto(P, 240, 292, 1.04)]
    return svg(480, 360, "".join(c))


def celular(P, x, y, rot=-3):
    """Celular com a lista de respostas salvas e o selo de data (leitura sem rede)."""
    g = [f'<g transform="translate({x} {y}) rotate({rot})">']
    g.append(f'<rect x="-78" y="-135" width="156" height="270" rx="26" fill="{P["sombra"]}" '
             f'opacity="{P["sombra_op"]}" filter="url(#b)" transform="translate(6 12)"/>')
    g.append(f'<rect x="-80" y="-137" width="160" height="274" rx="27" fill="{P["capa"]}"/>')
    g.append(f'<rect x="-80" y="-137" width="160" height="274" rx="27" fill="none" stroke="{P["capa_esc"]}" stroke-width="2"/>')
    g.append(f'<rect x="-71" y="-128" width="142" height="256" rx="20" fill="{P["pagina"]}"/>')
    g.append(f'<rect x="-22" y="-125" width="44" height="9" rx="4.5" fill="{P["capa"]}"/>')
    # barra de título
    g.append(f'<rect x="-58" y="-104" width="64" height="9" rx="4.5" fill="{P["linha"]}"/>')
    g.append(f'<circle cx="44" cy="-100" r="6" fill="{P["linha"]}"/><circle cx="26" cy="-100" r="6" fill="{P["linha"]}"/>')
    # selo de data: faixa com calendário e uma linha
    g.append(f'<rect x="-58" y="-80" width="116" height="26" rx="7" fill="{P["areia_cla"]}" opacity=".7"/>')
    g.append(f'<rect x="-58" y="-80" width="116" height="26" rx="7" fill="none" stroke="{P["areia_esc"]}" stroke-width="2"/>')
    g.append(f'<rect x="-50" y="-73" width="15" height="13" rx="3" fill="{P["pagina"]}" stroke="{P["areia_esc"]}" stroke-width="2"/>')
    g.append(f'<rect x="-50" y="-73" width="15" height="4.5" rx="2" fill="{P["areia_esc"]}"/>')
    g.append(f'<rect x="-28" y="-70" width="72" height="6" rx="3" fill="{P["areia_esc"]}" opacity=".8"/>')
    # lista de respostas salvas
    for i, (w1, w2) in enumerate(((58, 38), (52, 42), (62, 30))):
        yy = -42 + i * 48
        g.append(f'<rect x="-58" y="{yy}" width="116" height="40" rx="9" fill="{P["pagina"]}" stroke="{P["linha"]}" stroke-width="2"/>')
        g.append(f'<circle cx="-46" cy="{yy + 20}" r="4.5" fill="{P["verde_esc"] if i != 0 else P["areia_esc"]}"/>')
        g.append(f'<rect x="-34" y="{yy + 11}" width="{w1}" height="7" rx="3.5" fill="{P["linha"]}"/>')
        g.append(f'<rect x="-34" y="{yy + 23}" width="{w2}" height="6" rx="3" fill="{P["linha"]}" opacity=".6"/>')
        g.append(f'<rect x="34" y="{yy + 14}" width="18" height="12" rx="6" fill="{P["verde_cla"]}"/>')
    g.append(f'<rect x="-22" y="118" width="44" height="5" rx="2.5" fill="{P["linha"]}"/>')
    g.append('</g>')
    return "".join(g)


def sem_rede(P, x, y):
    """Símbolo discreto de «sem rede»: wifi cortado por uma diagonal."""
    cx, cy = 0, 8
    arcos = []
    for r in (9, 16, 23):
        d = 0.7071 * r
        arcos.append(f'<path d="M{cx - d:.1f},{cy - d:.1f} A{r},{r} 0 0 1 {cx + d:.1f},{cy - d:.1f}" fill="none" '
                     f'stroke="{P["metileno"] if P["capa"] == "#17506B" else P["verde"]}" stroke-width="4" stroke-linecap="round"/>')
    return (f'<g transform="translate({x} {y})">'
            f'<circle cx="0" cy="4" r="31" fill="{P["sombra"]}" opacity="{P["sombra_op"]}" filter="url(#b2)" transform="translate(2 5)"/>'
            f'<circle cx="0" cy="0" r="30" fill="{P["pagina"]}"/>'
            f'<circle cx="0" cy="0" r="30" fill="none" stroke="{P["linha"]}" stroke-width="2"/>'
            f'<g transform="translate(0 2)">{"".join(arcos)}<circle cx="{cx}" cy="{cy + 2}" r="3.6" '
            f'fill="{P["metileno"] if P["capa"] == "#17506B" else P["verde"]}"/></g>'
            f'<path d="M-16,-17 L17,17" stroke="{P["tinta"]}" stroke-width="4.5" stroke-linecap="round"/></g>')


def cena_cartao3(P):
    c = [spot(P, 240, 184, 150),
         sombra(P, 238, 332, 92, 11),
         celular(P, 236, 188, -3),
         sem_rede(P, 330, 84)]
    return svg(480, 360, "".join(c))


def cena_historico(P):
    c = [spot(P, 240, 140, 118),
         f'<ellipse cx="240" cy="268" rx="170" ry="12" fill="{P["tapete"]}" opacity="{P["tapete_op"]}"/>',
         livro_fechado(P, 240, 262, P["verde_esc"], largura=268, esp=26),
         livro_fechado(P, 240, 236, P["capa"], largura=236, esp=44),
         gato_dormindo(P, 240, 192, 1.0)]
    return svg(480, 300, "".join(c))


def cena_sobre(P):
    c = [f'<path d="M0,186 C100,168 200,200 300,186 C400,172 500,200 600,184 L600,210 L0,210 Z" '
         f'fill="{P["tapete"]}" opacity="{P["tapete_op"]}"/>',
         spot(P, 300, 118, 84),
         cao(P, 100, 196, 0.86), gato(P, 500, 196, 0.82, espelhar=True),
         folha(P, 232, 194, -24, 0.8), folha(P, 248, 196, 8, 0.62),
         capsula(P, 270, 146, -30, 1.05), frasco(P, 336, 194, 0.92),
         capsula(P, 392, 178, 24, 0.74, c1=P["areia"], c2=P["verde"]),
         folha(P, 420, 196, 22, 0.72), folha(P, 406, 197, -8, 0.55)]
    return svg(600, 210, "".join(c))


def cena_inicio(P):
    c = [spot(P, 110, 66, 62),
         cao(P, 70, 112, 0.58), gato(P, 152, 112, 0.56, espelhar=True)]
    return svg(220, 120, "".join(c))


CENAS = {
    "abertura": cena_abertura,
    "intro_cartao1": cena_cartao1,
    "intro_cartao3": cena_cartao3,
    "historico_vazio": cena_historico,
    "sobre_faixa": cena_sobre,
    "inicio_cabecalho": cena_inicio,
}

if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    for nome, fn in CENAS.items():
        for tema, P in TEMAS.items():
            (SAIDA / f"{nome}_{tema}.svg").write_text(fn(P), encoding="utf-8")
    print(len(CENAS) * 2, "SVGs em", SAIDA)
    sys.exit(0)
