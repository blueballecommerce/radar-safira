"""Gera docs/fornecedores.json — o que a aba "Fornecedores" da página lê.

Junta três fontes:
  data/fornecedor.json          o catálogo raspado do site do fornecedor
  data/fornecedor_busca.json    os anúncios que a JoomPulse devolveu para cada item
  data/fornecedor_veredito.json a conferência visual, anúncio por anúncio

O veredito é o que separa "a busca achou" de "é o mesmo produto": a JoomPulse
casa por nome, e nome não sabe a cor nem o formato. Só entra na página como
"igual" o que passou pela conferência da foto.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config
from .fornecedor import BUSCA, SAIDA

VEREDITO = config.DATA_DIR / "fornecedor_veredito.json"
CATS = config.DATA_DIR / "fornecedor_categorias.json"     # `fornecedor categorias`
DESTINO = config.DOCS_DIR / "fornecedores.json"

FORNECEDORES = [{
    "id": "flexx",
    "nome": "Flexx Imports",
    "site": "https://www.flexximports.com.br/",
    # cópia local (docs/img): o CDN deles recusa o arquivo fora do site
    "logo": "img/flexx-logo.webp",
    "contato": "(11) 98820-8112",
    "regra": "Vende apenas caixa fechada",
}]


def _carrega(p):
    return json.loads(p.read_text("utf-8")) if p.exists() else []


def _mensal(a: dict) -> dict:
    """Buscas anteriores à correção de período guardaram o número mensal em `vendas_sem`
    (a JoomPulse mostra vendas por mês). Quem não tem `vendas_mes` é dessa época."""
    if a.get("vendas_mes") is None and a.get("vendas_sem") is not None:
        a = {**a, "vendas_mes": a["vendas_sem"], "vendas_sem": round(a["vendas_sem"] / 4.33)}
    return a


def _nivel_mono(pct):
    if pct is None:
        return None
    return "low" if pct <= 0.3 else "medium" if pct <= 0.6 else "high"


def _categoria(c: dict | None) -> dict | None:
    """Mesmos nomes de campo que a aba Radar usa para categoria (gG, ocG, gmv, mono...)."""
    if not c or not c.get("caminho"):
        return None
    return {"id": c.get("id"), "nivel": c.get("nivel"), "caminho": c.get("caminho"),
            "l1": c.get("l1"), "l2": c.get("l2"), "l3": c.get("l3"), "folha": c.get("folha"),
            "opp": c.get("opp"), "mono": _nivel_mono(c.get("mono_pct")), "monoV": c.get("mono_pct"),
            "gG": c.get("receita_var"), "ocG": c.get("vendas_var"),
            "gmv": c.get("receita"), "vendas": c.get("vendas"), "nprod": c.get("produtos"),
            "ticket": c.get("ticket"), "sazonalidade": c.get("sazonalidade")}


def exportar() -> dict:
    catalogo = _carrega(SAIDA)
    cats = _carrega(CATS) or {}
    if not isinstance(cats, dict):
        cats = {}
    buscas = {b["fornecedor"]["url"]: b["anuncios"] for b in _carrega(BUSCA)}
    vereditos = _carrega(VEREDITO) or {}
    if isinstance(vereditos, list):                        # tolera lista de registros
        vereditos = {f'{v["item"]}|{v["id"]}': v for v in vereditos}

    produtos = []
    for it in catalogo:
        anuncios = []
        for a in buscas.get(it["url"], []):
            a = _mensal(a)
            v = (vereditos.get(f'{it["url"]}|cat:{a.get("chave")}') if a.get("chave") else None)                 or vereditos.get(f'{it["url"]}|{a["id"]}', {})
            anuncios.append({**a, "veredito": v.get("veredito"), "obs": v.get("obs")})
        # os "iguais" primeiro, depois os parecidos; dentro de cada grupo, quem mais vende
        ordem = {"igual": 0, "parecido": 1, None: 2, "diferente": 3}
        anuncios.sort(key=lambda a: (ordem.get(a["veredito"], 2), -(a.get("vendas_sem") or 0)))
        c = cats.get(it["url"]) or {}
        ja = {a["id"] for a in anuncios}
        # os que mais vendem na subcategoria, tirando os que já estão na lista do produto
        mesma = [{**a, "veredito": None, "obs": None}
                 for a in (c.get("mesma_categoria") or []) if a.get("id") not in ja]
        produtos.append({
            "url": it["url"], "nome": it["nome"], "img": it.get("img"),
            "categoria": _categoria(c.get("cat")), "mesma_categoria": mesma, "ref": c.get("ref"),
            "unit": it.get("unit"), "caixa": it.get("caixa"), "total": it.get("total"),
            "unidade": it.get("unidade"), "tags": it.get("tags") or [],
            # preço do site quando o catálogo (PDF) trouxe outro; página do catálogo
            "unit_site": it.get("unit_site"), "caixa_site": it.get("caixa_site"), "pagina": it.get("pagina"),
            "nome_catalogo": it.get("nome_catalogo"),
            "pesquisado": it["url"] in buscas,
            "anuncios": anuncios,
            "iguais": sum(1 for a in anuncios if a["veredito"] == "igual"),
            "parecidos": sum(1 for a in anuncios if a["veredito"] == "parecido"),
        })

    dados = {
        "geradoEm": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fornecedores": [{**f, "produtos": len(produtos),
                          "pesquisados": sum(1 for p in produtos if p["pesquisado"])}
                         for f in FORNECEDORES],
        "produtos": [{**p, "fornecedor": "flexx"} for p in produtos],
    }
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return dados


if __name__ == "__main__":
    d = exportar()
    print(json.dumps({"produtos": len(d["produtos"]),
                      "pesquisados": d["fornecedores"][0]["pesquisados"],
                      "arquivo": str(DESTINO)}, ensure_ascii=False))
