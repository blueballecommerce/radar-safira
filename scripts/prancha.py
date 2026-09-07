#!/usr/bin/env python3
"""Monta pranchas de conferência: o produto do fornecedor à esquerda, os anúncios
que a JoomPulse devolveu à direita, numerados. Uma imagem por produto.

É o material da conferência visual: olhar uma prancha custa uma fração de olhar
dez fotos soltas, e o lado a lado é o que revela cor, formato e material.

Uso: python scripts/prancha.py [pasta_saida]
Lê data/fornecedor_busca.json e grava <pasta>/<n>.jpg + <pasta>/indice.json
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BUSCA = ROOT / "data" / "fornecedor_busca.json"
VEREDITO = ROOT / "data" / "fornecedor_veredito.json"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "pranchas"
LADO = 260            # tamanho de cada foto na prancha
COLS = 4              # candidatos por linha
MAX_CAND = 8          # candidatos distintos por produto (por catálogo, não por anúncio)
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.flexximports.com.br/"}


def baixa(cli: httpx.Client, url: str | None) -> Image.Image:
    branco = Image.new("RGB", (LADO, LADO), (240, 240, 240))
    if not url:
        return branco
    try:
        r = cli.get(url, timeout=30, follow_redirects=True)
        if r.status_code != 200 or len(r.content) < 500:
            return branco
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return branco
    im.thumbnail((LADO, LADO))
    tela = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    tela.paste(im, ((LADO - im.width) // 2, (LADO - im.height) // 2))
    return tela


def fonte(tam: int):
    for nome in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nome, tam)
        except Exception:
            pass
    return ImageFont.load_default()


def rotulo(im: Image.Image, texto: str, cor=(20, 20, 20)) -> Image.Image:
    quadro = Image.new("RGB", (LADO, LADO + 46), (255, 255, 255))
    quadro.paste(im, (0, 0))
    d = ImageDraw.Draw(quadro)
    f = fonte(13)
    linhas, atual = [], ""
    for w in texto.split():
        if d.textlength(atual + " " + w, font=f) > LADO - 8 and atual:
            linhas.append(atual); atual = w
        else:
            atual = (atual + " " + w).strip()
    linhas.append(atual)
    for i, l in enumerate(linhas[:2]):
        d.text((4, LADO + 4 + i * 17), l, fill=cor, font=f)
    return quadro


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dados = json.loads(BUSCA.read_text("utf-8"))
    ja = json.loads(VEREDITO.read_text("utf-8")) if VEREDITO.exists() else {}
    indice = []
    with httpx.Client(headers=UA) as cli:
        for n, bloco in enumerate(dados, 1):
            f = bloco["fornecedor"]
            # um candidato por catálogo: anúncios do mesmo produto têm a mesma foto
            vistos, cands = set(), []
            for a in bloco["anuncios"]:
                k = (a.get("img") or "").split("?")[0]
                if k in vistos:
                    continue
                if a.get("chave") and f'{f["url"]}|cat:{a["chave"]}' in ja:
                    continue                          # já conferido numa rodada anterior
                vistos.add(k); cands.append(a)
                if len(cands) >= MAX_CAND:
                    break
            if not cands:
                print(f"{n:02d} {f['nome'][:44]:<44} nada novo para conferir"); continue
            esq = rotulo(baixa(cli, f.get("img")), f"FORNECEDOR: {f['nome']}", (160, 30, 30))
            quadros = [rotulo(baixa(cli, a.get("img")),
                              f"#{i+1} R$ {a.get('preco') or '?'} · {a.get('vendas_sem') or 0}/sem · {a.get('dias') or '?'}d · {a.get('nome','')[:40]}")
                       for i, a in enumerate(cands)]
            linhas = max(1, -(-len(quadros) // COLS))
            W = LADO + 24 + COLS * (LADO + 8)
            H = 30 + linhas * (LADO + 46 + 8)
            prancha = Image.new("RGB", (W, H), (255, 255, 255))
            d = ImageDraw.Draw(prancha)
            d.text((6, 6), f"[{n}] {f['nome']} — custo R$ {f.get('unit')} · caixa {f.get('caixa')} · {len(bloco['anuncios'])} anúncios, {len(cands)} distintos",
                   fill=(0, 0, 0), font=fonte(15))
            prancha.paste(esq, (6, 30))
            for i, q in enumerate(quadros):
                x = LADO + 24 + (i % COLS) * (LADO + 8)
                y = 30 + (i // COLS) * (LADO + 46 + 8)
                prancha.paste(q, (x, y))
            caminho = OUT / f"{n:02d}.jpg"
            prancha.save(caminho, quality=82)
            indice.append({"n": n, "url": f["url"], "nome": f["nome"], "arquivo": str(caminho),
                           "candidatos": [{"pos": i + 1, "id": a["id"], "chave": a.get("chave"), "nome": a.get("nome"), "preco": a.get("preco"),
                                           "ids_mesma_foto": [b["id"] for b in bloco["anuncios"]
                                                              if (b.get("img") or "").split("?")[0] == (a.get("img") or "").split("?")[0]]}
                                          for i, a in enumerate(cands)]})
            print(f"{n:02d} {f['nome'][:44]:<44} {len(cands)} candidatos -> {caminho.name}")
    (OUT / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    main()
