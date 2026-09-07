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
DESTINO = config.DOCS_DIR / "fornecedores.json"

FORNECEDORES = [{
    "id": "flexx",
    "nome": "Flexx Imports",
    "site": "https://www.flexximports.com.br/",
    "logo": "https://app.procatalogo.com.br/flexximports/wp-content/uploads/sites/4951/2026/01/"
            "Produtividade-Conforto-e-Seguran%C3%A7a-em-um-s%C3%B3-produto.webp",
    "contato": "(11) 98820-8112",
    "regra": "Vende apenas caixa fechada",
}]


def _carrega(p):
    return json.loads(p.read_text("utf-8")) if p.exists() else []


def exportar() -> dict:
    catalogo = _carrega(SAIDA)
    buscas = {b["fornecedor"]["url"]: b["anuncios"] for b in _carrega(BUSCA)}
    vereditos = _carrega(VEREDITO) or {}
    if isinstance(vereditos, list):                        # tolera lista de registros
        vereditos = {f'{v["item"]}|{v["id"]}': v for v in vereditos}

    produtos = []
    for it in catalogo:
        anuncios = []
        for a in buscas.get(it["url"], []):
            v = vereditos.get(f'{it["url"]}|{a["id"]}', {})
            anuncios.append({**a, "veredito": v.get("veredito"), "obs": v.get("obs")})
        # os "iguais" primeiro, depois os parecidos; dentro de cada grupo, quem mais vende
        ordem = {"igual": 0, "parecido": 1, None: 2, "diferente": 3}
        anuncios.sort(key=lambda a: (ordem.get(a["veredito"], 2), -(a.get("vendas_sem") or 0)))
        produtos.append({
            "url": it["url"], "nome": it["nome"], "img": it.get("img"),
            "unit": it.get("unit"), "caixa": it.get("caixa"), "total": it.get("total"),
            "unidade": it.get("unidade"), "tags": it.get("tags") or [],
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
