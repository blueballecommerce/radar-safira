#!/usr/bin/env python3
"""Cartão de produto a partir da foto de prateleira de um fornecedor sem site.

Recorta o produto e a sua etiqueta verde da foto original e monta um cartão
limpo: produto em cima, etiqueta e dados em texto embaixo, fundo branco. É o que
a lista de fornecedores mostra como miniatura.

    python scripts/etiqueta.py prova     # folha de prova, para conferir os recortes
    python scripts/etiqueta.py cartoes   # grava docs/img/logospan/<cod>.jpg

As caixas de recorte são medidas uma vez, na mão, olhando a folha de prova. A da
etiqueta só precisa ser aproximada: o verde fluorescente é o único da cena, então
`_bbox_verde` fecha o enquadramento sozinho — inclusive quando a etiqueta está
torta e precisa de um giro antes.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
ORIG = RAIZ / "docs" / "img" / "logospan" / "originais"
DEST = RAIZ / "docs" / "img" / "logospan"
PROVA = RAIZ / "data" / "pranchas" / "logospan"

# cod: (foto, caixa do produto, caixa da etiqueta, giro da etiqueta, nome, preco, caixa_un)
ITENS = {
    "24672": ("foto5-air-blaster.jpg",   (20, 540, 790, 1195), (250, 1272, 565, 1358), 0,
              "Arma Lança Dardos Air Blaster", "6,98", 216),
    "24805": ("foto4-soft-shot.jpg",     (68, 245, 715, 625),  (222, 632, 412, 698), 0,
              "Arminha Lança Dardos Soft-Shot Gun · rifle", "49,98", 48),
    "24807": ("foto4-soft-shot.jpg",     (683, 320, 1550, 625), (952, 642, 1152, 702), 0,
              "Arminha Lança Dardos Soft-Shot Gun · pistola", "19,98", 120),
    "13288": ("foto1-assault-team.jpg",  (98, 50, 900, 1405),  (258, 1478, 565, 1562), 0,
              "Arma Lança Dardos Kit Policial Assault Team", "21,98", 30),
    "24689": ("foto2-crab-bear.jpg",     (0, 355, 402, 1240),  (18, 1248, 248, 1340), 0,
              "Caranguejo Robô Cartoon Crab", "29,98", 108),
    "24690": ("foto2-crab-bear.jpg",     (386, 395, 900, 1240), (608, 1248, 838, 1340), 0,
              "Urso com Luz e Som Dancing Bear", "24,98", 120),
    "24688": ("foto3-rocket-bubble.jpg", (0, 262, 900, 1420),  (103, 928, 258, 1092), 28,
              "Arma Lança Foguetes Bazuca", "59,98", None),
    # ---------------------------------------------------------------- lote 2
    "24263": ("foto06-skates.jpg", (0, 396, 572, 694), (100, 648, 228, 704), 0,
              "Skate 43cm Monstro Amarelo", "27,98", 12),
    "24825": ("foto06-skates.jpg", (552, 396, 1062, 694), (696, 650, 834, 708), 0,
              "Skate 43cm All Star Rock", "27,98", 12),
    "24265": ("foto06-skates.jpg", (1038, 396, 1600, 694), (1302, 652, 1476, 714), 0,
              "Skate 43cm Monstro Verde", "27,98", 12),
    "23947": ("foto07-bonecas-sereia.jpg", (0, 150, 272, 742), (28, 738, 180, 794), 0,
              "Boneca com Acessórios Bruxa", "10,98", 48),
    "05794": ("foto07-bonecas-sereia.jpg", (272, 150, 616, 742), (358, 744, 512, 800), 0,
              "Boneca com Acessórios Sereia", "10,98", 48),
    "24002": ("foto07-bonecas-sereia.jpg", (712, 150, 878, 742), (864, 744, 1016, 802), 0,
              "Boneca Sereia TOYS24129", "9,98", 144),
    "24003": ("foto07-bonecas-sereia.jpg", (952, 150, 1140, 742), (1300, 740, 1492, 804), 0,
              "Boneca Sereia TOYS24111", "9,98", 120),
    "00502": ("foto08-super-machine.jpg", (0, 455, 900, 1100), (176, 1082, 404, 1228), 0,
              "Arma de Plástico 43,5cm Super Machine", "41,98", 48),
    "00280": ("foto08-super-machine.jpg", (140, 105, 900, 585), (716, 1412, 900, 1596), 0,
              "Arma de Plástico 47,5cm Super Machine", "39,98", None),
    "03798": ("foto12-future-war.jpg", (0, 165, 900, 1185), (96, 1190, 430, 1325), -8,
              "Arma Kit Future War", "23,98", 84),
    "23826": ("foto11-soft-gun-m4.jpg", (0, 375, 900, 1240), (224, 1244, 444, 1326), 0,
              "Lança Dardos Soft Gun M4", "19,98", 48),
    "01928": ("foto10-comando-2em1.jpg", (0, 515, 880, 1245), (272, 1240, 610, 1345), 0,
              "Lança Dardos Comando 2 em 1", "29,98", None),
    "05884": ("foto09-super-comando.jpg", (0, 128, 792, 1152), (460, 1140, 820, 1280), 0,
              "Lança Dardos Super Comando", "24,98", 24),
}


def fonte(t, bold=False):
    for n in (("arialbd.ttf",) if bold else ("arial.ttf",)) + ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(n, t)
        except Exception:
            pass
    return ImageFont.load_default()


def _bbox_verde(im, margem=6):
    """Caixa da etiqueta verde fluorescente dentro do recorte.

    A etiqueta e o unico verde saturado da cena, entao um limiar simples
    (verde bem acima do vermelho e do azul) acha a borda melhor do que eu
    acertaria na mao — e resolve tambem as etiquetas tortas, depois do giro.
    """
    px = im.convert("RGB").load()
    w, h = im.size
    xs, ys = [], []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if g > 110 and g > r * 1.25 and g > b * 1.30:
                xs.append(x); ys.append(y)
    if len(xs) < 40:
        return None
    return (max(0, min(xs) - margem), max(0, min(ys) - margem),
            min(w, max(xs) + margem), min(h, max(ys) + margem))


def recorta(cod):
    foto, cxp, cxe, giro, *_ = ITENS[cod]
    im = Image.open(ORIG / foto)
    prod = im.crop(cxp)
    etq = im.crop(cxe)
    if giro:
        etq = etq.resize((etq.width * 5, etq.height * 5), Image.LANCZOS)
        etq = etq.rotate(giro, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    bb = _bbox_verde(etq)
    if bb:
        etq = etq.crop(bb)
    return prod, etq


def prova():
    """Uma folha com produto e etiqueta lado a lado, para conferir os recortes."""
    L, alt = 420, 300
    linhas = len(ITENS)
    tela = Image.new("RGB", (L * 2 + 30, linhas * (alt + 30)), (255, 255, 255))
    d = ImageDraw.Draw(tela)
    for i, cod in enumerate(ITENS):
        prod, etq = recorta(cod)
        y = i * (alt + 30)
        for j, im in enumerate((prod, etq)):
            c = im.copy()
            c.thumbnail((L, alt))
            tela.paste(c, (j * (L + 20) + 10, y + 22))
        d.text((10, y + 3), f"{cod} — {ITENS[cod][4]}", font=fonte(16, True), fill=(0, 0, 0))
        d.line([(0, y + alt + 26), (tela.width, y + alt + 26)], fill=(200, 200, 200))
    p = PROVA / "prova-recortes.jpg"
    tela.save(p, quality=88)
    print(p, tela.size)


LADO = 900
BARRA = 190


def miniatura(cod):
    """Só o produto, quadrado, para a lista do site.

    A miniatura da lista tem 63 px: o cartão inteiro espremido ali não deixa ler
    nada, e o nome e o preço já estão na própria linha. Então aqui vai o produto
    sozinho — o cartão com a etiqueta é outro arquivo, em `cartoes/`.
    """
    prod, _ = recorta(cod)
    tela = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    p = prod.copy()
    p.thumbnail((LADO, LADO), Image.LANCZOS)
    tela.paste(p, ((LADO - p.width) // 2, (LADO - p.height) // 2))
    saida = DEST / f"{cod}.jpg"
    tela.save(saida, quality=92)
    print("  ", saida.name, tela.size)


def cartao(cod):
    prod, etq = recorta(cod)
    _, _, _, _, nome, preco, caixa = ITENS[cod]
    tela = Image.new("RGB", (LADO, LADO + BARRA), (255, 255, 255))

    # produto: cabe inteiro, centralizado, sem esticar
    p = prod.copy()
    p.thumbnail((LADO - 40, LADO - 40), Image.LANCZOS)
    tela.paste(p, ((LADO - p.width) // 2, (LADO - p.height) // 2))

    d = ImageDraw.Draw(tela)
    d.rectangle([0, LADO, LADO, LADO + BARRA], fill=(246, 247, 249))
    d.line([(0, LADO), (LADO, LADO)], fill=(214, 218, 224), width=2)

    # etiqueta verde recortada da propria foto, do lado direito da barra
    e = etq.copy()
    e.thumbnail((330, BARRA - 34), Image.LANCZOS)
    ex, ey = LADO - e.width - 22, LADO + (BARRA - e.height) // 2
    d.rectangle([ex - 3, ey - 3, ex + e.width + 3, ey + e.height + 3], fill=(255, 255, 255),
                outline=(206, 210, 216))
    tela.paste(e, (ex, ey))

    # dados lidos da etiqueta, em texto limpo
    d.text((26, LADO + 26), f"COD. {cod}", font=fonte(27, True), fill=(35, 145, 90))
    f = fonte(25, True)
    linhas, atual = [], ""
    for w in nome.split():
        t = (atual + " " + w).strip()
        if d.textlength(t, font=f) <= LADO - e.width - 70:
            atual = t
        else:
            linhas.append(atual)
            atual = w
    if atual:
        linhas.append(atual)
    for j, ln in enumerate(linhas[:2]):
        d.text((26, LADO + 62 + j * 31), ln, font=f, fill=(24, 28, 34))
    rod = f"R$ {preco}" + (f"   ·   caixa {caixa} un" if caixa else "")
    d.text((26, LADO + BARRA - 44), rod, font=fonte(30, True), fill=(24, 28, 34))

    (DEST / "cartoes").mkdir(parents=True, exist_ok=True)
    p = DEST / "cartoes" / f"{cod}.jpg"
    tela.save(p, quality=92)
    print("  ", "cartoes/" + p.name, tela.size)


if __name__ == "__main__":
    acao = sys.argv[1] if sys.argv[1:] else "prova"
    if acao == "cartoes":
        for cod in ITENS:
            miniatura(cod)
            cartao(cod)
    elif acao == "prova":
        prova()
    else:
        raise SystemExit("uso: python scripts/etiqueta.py [prova|cartoes]")
