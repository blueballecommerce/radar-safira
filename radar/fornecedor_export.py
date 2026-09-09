"""Gera docs/fornecedores.json — o que a aba "Fornecedores" da página lê.

Junta, por fornecedor:
  <catalogo>   o catálogo do fornecedor (raspado do site, ou digitado da prateleira)
  <busca>      os anúncios que a pesquisa devolveu para cada item
  <cats>       a subcategoria do ML de cada produto (`fornecedor categorias`)
  fornecedor_veredito.json   a conferência visual, anúncio por anúncio

O veredito é o que separa "a busca achou" de "é o mesmo produto": a busca casa
por nome, e nome não sabe a cor nem o formato. Só entra na página como "igual"
o que passou pela conferência da foto.

Os vereditos de todos os fornecedores moram no mesmo arquivo — a chave é
`<url do item>|<id do anúncio>`, e a url já carrega o fornecedor, então não há
colisão entre catálogos diferentes.
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
    "fonte": "catálogo set/26",
    "catalogo": SAIDA,
    "busca": BUSCA,
    "cats": CATS,
}, {
    "id": "logospan",
    "nome": "Logospan",
    # loja física, sem site: a página troca o link do site pelo código da etiqueta
    "site": "",
    "logo": "",                    # loja fisica, sem marca propria: a pagina desenha a inicial
    "contato": "(11) 93310-4352",
    "regra": "Loja física · aceita quantidade menor que a caixa fechada",
    "fonte": "etiqueta da loja",
    "catalogo": config.DATA_DIR / "fornecedor_logospan.json",
    "busca": config.DATA_DIR / "fornecedor_logospan_busca.json",
    # a categoria vem dentro do próprio arquivo de busca, não de um arquivo à parte
    "cats": None,
}]


def _carrega(p):
    return json.loads(p.read_text("utf-8")) if p is not None and p.exists() else []


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


def _produtos(forn: dict, vereditos: dict) -> list[dict]:
    """Os produtos de um fornecedor, já com os anúncios conferidos.

    Um fornecedor sem site (catálogo digitado da prateleira) guarda a categoria e
    a lista da subcategoria dentro do próprio arquivo de busca; o da Flexx vem do
    `fornecedor_categorias.json`. Aqui os dois caminhos convivem.
    """
    catalogo = _carrega(forn["catalogo"])
    cats = _carrega(forn.get("cats")) or {}
    if not isinstance(cats, dict):
        cats = {}
    # guarda o bloco inteiro, não só os anúncios: é dele que sai a categoria
    buscas = {b["fornecedor"]["url"]: b for b in _carrega(forn["busca"])}

    produtos = []
    for it in catalogo:
        bloco = buscas.get(it["url"]) or {}
        anuncios = []
        for a in bloco.get("anuncios", []):
            a = _mensal(a)
            v = (vereditos.get(f'{it["url"]}|cat:{a.get("chave")}') if a.get("chave") else None) \
                or vereditos.get(f'{it["url"]}|{a["id"]}', {})
            anuncios.append({**a, "veredito": v.get("veredito"), "obs": v.get("obs"),
                             "qtd": int(v.get("qtd") or 1)})
        # os "iguais" primeiro, depois os parecidos; dentro de cada grupo, quem mais vende
        ordem = {"igual": 0, "parecido": 1, None: 2, "diferente": 3}
        anuncios.sort(key=lambda a: (ordem.get(a["veredito"], 2), -(a.get("vendas_sem") or 0)))

        c = cats.get(it["url"]) or {}
        ja = {a["id"] for a in anuncios}
        # os que mais vendem na subcategoria, tirando os que já estão na lista do produto
        crus = c.get("mesma_categoria") or bloco.get("mesma_categoria") or []
        mesma = [{**_mensal(a), "veredito": None, "obs": None}
                 for a in crus if a.get("id") not in ja]
        produtos.append({
            "url": it["url"], "nome": it["nome"], "img": it.get("img"),
            "categoria": _categoria(c.get("cat")) or bloco.get("categoria"),
            "mesma_categoria": mesma, "ref": c.get("ref"),
            "unit": it.get("unit"), "caixa": it.get("caixa"), "total": it.get("total"),
            "unidade": it.get("unidade"), "tags": it.get("tags") or [],
            # preço do site quando o catálogo (PDF) trouxe outro; página do catálogo
            "unit_site": it.get("unit_site"), "caixa_site": it.get("caixa_site"), "pagina": it.get("pagina"),
            "nome_catalogo": it.get("nome_catalogo"),
            # etiqueta de prateleira: o que estava escrito no papel, para conferência
            "cod": it.get("cod"), "etiqueta": it.get("etiqueta"),
            # o que eu olhei na foto para bater o produto, e as fotos originais
            "marcas": it.get("marcas") or [], "fotos": it.get("fotos") or [],
            "pesquisado": it["url"] in buscas,
            "anuncios": anuncios,
            "iguais": sum(1 for a in anuncios if a["veredito"] == "igual"),
            "parecidos": sum(1 for a in anuncios if a["veredito"] == "parecido"),
            "fornecedor": forn["id"],
        })
    return produtos


def exportar() -> dict:
    vereditos = _carrega(VEREDITO) or {}
    if isinstance(vereditos, list):                        # tolera lista de registros
        vereditos = {f'{v["item"]}|{v["id"]}': v for v in vereditos}

    fornecedores, produtos = [], []
    for f in FORNECEDORES:
        meus = _produtos(f, vereditos)
        produtos.extend(meus)
        fornecedores.append({
            **{k: v for k, v in f.items() if k not in ("catalogo", "busca", "cats")},
            "produtos": len(meus),
            "pesquisados": sum(1 for p in meus if p["pesquisado"]),
        })

    dados = {
        "geradoEm": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fornecedores": fornecedores,
        "produtos": produtos,
    }
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return dados


if __name__ == "__main__":
    d = exportar()
    print(json.dumps({"produtos": len(d["produtos"]),
                      "fornecedores": {f["id"]: f"{f['pesquisados']}/{f['produtos']}"
                                       for f in d["fornecedores"]},
                      "arquivo": str(DESTINO)}, ensure_ascii=False))
