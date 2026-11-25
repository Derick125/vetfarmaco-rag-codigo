"""Exporta as ilustrações de `assets/arte_fonte/*.svg` para PNG com fundo transparente.

O Flutter não desenha SVG sem um pacote extra; por isso o app usa PNG em 1x, 2x e 3x por tema, no
formato de assets com variantes de densidade: `assets/img/<cena>_<tema>.png` (1x) e
`assets/img/2.0x/`, `assets/img/3.0x/`. O tamanho 1x é a largura, em dp, com que cada cena é exibida.

Precisa do Microsoft Edge (ou Chrome) para rasterizar. Uso, a partir de `app/`:

    python tool/gerar_arte.py       # (re)gera os SVG
    python tool/exportar_png.py     # exporta os PNG
"""

from __future__ import annotations

import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
FONTE = APP / "assets" / "arte_fonte"
SAIDA = APP / "assets" / "img"

# Largura em dp com que cada cena aparece no app.
LARGURAS = {
    "abertura": 300,
    "intro_cartao1": 296,
    "intro_cartao3": 296,
    "historico_vazio": 310,
    "sobre_faixa": 412,
    "inicio_cabecalho": 150,
}
TEMAS = ("claro", "escuro")
ESCALAS = {"": 1, "2.0x": 2, "3.0x": 3}

NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def navegador() -> str:
    for caminho in NAVEGADORES:
        if Path(caminho).exists():
            return caminho
    sys.exit("Edge ou Chrome não encontrado.")


def proporcao(svg: Path) -> float:
    """Altura / largura, lida do `viewBox` do SVG."""
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg.read_text(encoding="utf-8"))
    assert m, svg
    return int(m.group(2)) / int(m.group(1))


def dimensoes_png(caminho: Path) -> tuple[int, int, int]:
    """(largura, altura, tipo de cor) do cabeçalho IHDR; tipo 6 = RGBA."""
    dados = caminho.read_bytes()[:33]
    largura, altura = struct.unpack(">II", dados[16:24])
    return largura, altura, dados[25]


def exportar(svg: Path, w: int, h: int, destino: Path, exe: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "c.html"
        html.write_text(
            f'<!doctype html><body style="margin:0;background:transparent">'
            f'<img src="{svg.as_uri()}" width="{w}" height="{h}" style="display:block"></body>',
            encoding="utf-8",
        )
        subprocess.run(
            [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--default-background-color=00000000", f"--window-size={w},{h}",
             f"--screenshot={destino}", html.as_uri()],
            capture_output=True, check=True,
        )
    largura, altura, cor = dimensoes_png(destino)
    assert (largura, altura) == (w, h), f"{destino.name}: {largura}x{altura} != {w}x{h}"
    assert cor == 6, f"{destino.name}: sem canal alfa (tipo de cor {cor})"


def main() -> int:
    exe = navegador()
    total = 0
    for cena, largura in LARGURAS.items():
        for tema in TEMAS:
            svg = FONTE / f"{cena}_{tema}.svg"
            altura = round(largura * proporcao(svg))
            for pasta, k in ESCALAS.items():
                destino = SAIDA / pasta / f"{cena}_{tema}.png"
                exportar(svg, largura * k, altura * k, destino, exe)
                total += 1
    print(f"{total} PNG em {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
