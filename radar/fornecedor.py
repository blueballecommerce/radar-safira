"""Catálogo do fornecedor (Flexx Imports) — coleta e casamento com o radar do ML.

O site é WooCommerce e entrega o HTML pronto, então aqui não é preciso navegador:
uma requisição por página de listagem dá conta das ~700 fichas. Como no radar, os
dados vão da página direto para o disco, sem passar por um modelo.

    python -m radar fornecedor coletar    # baixa o catálogo -> data/fornecedor.json
    python -m radar fornecedor cruzar     # cruza com o radar -> data/pares.json

O título do anúncio carrega quase tudo o que o site informa, porque a ficha não tem
descrição — só nome, preço e quantidade da caixa. O detalhe fino (cor, formato,
material) vive na foto, e é por isso que `cruzar` só levanta candidatos: quem decide
se é o mesmo produto é o olho humano (ou um modelo), olhando a imagem.
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from pathlib import Path

from . import config

log = logging.getLogger("radar.fornecedor")

BASE = "https://www.flexximports.com.br"
LISTA = BASE + "/?s=&post_type=product&paged={n}"
SAIDA = config.DATA_DIR / "fornecedor.json"
PARES = config.DATA_DIR / "pares.json"
PAUSA_S = 1.5                    # o site é de um parceiro; não convém atropelar


def _num(txt: str | None) -> float | None:
    """'R$ 2.000,00' -> 2000.0"""
    if not txt:
        return None
    m = re.search(r"[\d.]+(?:,\d+)?", txt.replace("\xa0", " "))
    if not m:
        return None
    try:
        return float(m.group(0).replace(".", "").replace(",", "."))
    except ValueError:
        return None


# "R$ 10,00 a UNI | 200un | Aparador de Pelos" — o preço unitário e o tamanho da
# caixa vêm no próprio título. O padrão varia bastante na mão de quem cadastra:
# "a UNI", "o PAR", "o KIT", "a UNI." e até "R$ R$" repetido, com ou sem espaço
# antes da barra. O regex aceita todas essas formas.
_TITULO = re.compile(
    r"^\s*(?:R\$\s*)*(?P<unit>[\d.,]+)\s*(?:[ao]\s*[a-zA-Zç]+\.?)?\s*\|\s*"
    r"(?P<qtd>[\d.]+)\s*(?P<un>[a-zA-Zç]*)\.?\s*\|?\s*(?P<nome>.*)$",
    re.IGNORECASE)


def _limpa_titulo(t: str) -> str:
    """Conserta os deslizes de digitação do cadastro antes de tentar ler o título.

    Aparecem coisas como 'R$ 7,5O' (letra O no lugar do zero) e 'R$ 41, 00'
    (espaço depois da vírgula) — o preço está lá, só malformado.
    """
    t = " ".join((t or "").split())
    t = re.sub(r"(?<=\d),\s+(?=\d)", ",", t)                     # "41, 00" -> "41,00"
    t = re.sub(r"(?<=\d)[Oo](?=\d|\s|$)", "0", t)                # "7,5O"   -> "7,50"
    return t


def parse_titulo(t: str) -> dict:
    """Separa preço unitário, tamanho da caixa e nome limpo do título do anúncio."""
    t = _limpa_titulo(t)
    m = _TITULO.match(t)
    if not m:
        # alguns títulos fogem do padrão; o que der para aproveitar, aproveitamos
        partes = [p.strip() for p in t.split("|")]
        return {"nome": partes[-1] if partes else t, "unit": _num(t) if "R$" in t else None,
                "caixa": None, "unidade": None, "titulo": t}
    d = m.groupdict()
    return {
        "nome": d["nome"].strip(" |") or t,
        "unit": _num(d["unit"]),
        "caixa": int(float(d["qtd"].replace(".", ""))) if d["qtd"] else None,
        "unidade": d["un"].lower().rstrip("."),
        "titulo": t,
    }


def _cards(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    sopa = BeautifulSoup(html, "html.parser")
    out = []
    for li in sopa.select("li.product"):
        a = li.select_one("a.woocommerce-loop-product__link") or li.select_one("a")
        titulo = li.select_one(".woocommerce-loop-product__title")
        img = li.select_one("img")
        if not titulo:
            continue
        d = parse_titulo(titulo.get_text(" ", strip=True))
        d["url"] = a.get("href") if a else None
        d["img"] = (img.get("data-src") or img.get("src") or "").split("?")[0] if img else None
        d["total"] = _num(li.select_one(".price").get_text(" ", strip=True) if li.select_one(".price") else None)
        # confere a conta do fornecedor: unitário × caixa deveria dar o total
        if d.get("unit") and d.get("caixa") and d.get("total"):
            esperado = d["unit"] * d["caixa"]
            d["confere"] = abs(esperado - d["total"]) < max(1.0, esperado * 0.02)
        out.append(d)
    return out


def coletar(paginas: int = 40) -> list[dict]:
    """Percorre a listagem até acabar e devolve o catálogo inteiro."""
    import httpx

    vistos: dict[str, dict] = {}
    with httpx.Client(timeout=30, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; RadarSafira/1.0)"}) as cli:
        for n in range(1, paginas + 1):
            r = cli.get(LISTA.format(n=n))
            if r.status_code != 200:
                break
            itens = _cards(r.text)
            novos = [i for i in itens if i.get("url") and i["url"] not in vistos]
            for i in novos:
                vistos[i["url"]] = i
            log.info("página %d: %d itens (%d no total)", n, len(itens), len(vistos))
            if not itens or not novos:
                break
            time.sleep(PAUSA_S)

    catalogo = list(vistos.values())
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), "utf-8")
    log.info("catálogo salvo: %d produtos em %s", len(catalogo), SAIDA)
    return catalogo


# ------------------------------------------------------------------ casamento
_STOP = {"para", "com", "sem", "dos", "das", "uma", "uns", "por", "kit", "pcs", "und",
         "unidades", "cor", "tamanho", "original", "novo", "nova", "caixa", "pecas",
         "unidade", "modelo", "tipo", "cores", "produto", "conjunto"}


def _tokens(s: str) -> set[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {w for w in re.split(r"[^a-z0-9]+", s) if len(w) > 3 and w not in _STOP and not w.isdigit()}


# Faixa de preço plausível para o mesmo produto, em múltiplos do custo unitário.
# Abaixo de 1,8× não há negócio; acima de 12× quase nunca é o mesmo item — é o
# caso da "seladora de R$ 25" casando com uma seladora industrial de R$ 5.799.
MULT_MIN, MULT_MAX = 1.8, 12.0


def cruzar(catalogo: list[dict], produtos: list[dict], corte: float = 0.62,
           min_comum: int = 2) -> list[dict]:
    """Levanta pares (item do fornecedor × anúncio do ML) por semelhança de título.

    Contar palavras em comum não basta: "Lanterna de Bicicleta" e "Bicicleta
    Ergométrica" dividem duas palavras e não têm nada a ver. Aqui cada palavra vale
    conforme sua raridade (idf) e o par só passa se as palavras em comum cobrirem
    a maior parte do *peso* do nome do fornecedor — ou seja, se o anúncio do ML
    fala do mesmo objeto, não só do mesmo assunto.

    Ainda assim é um filtro grosso, de propósito: reduz 700 itens a algumas dezenas
    que merecem olhar a foto. Cor, formato e material só a imagem resolve.
    """
    import math

    df: dict[str, int] = {}
    idx = []
    for p in produtos:
        t = _tokens(p.get("n", ""))
        idx.append((p, t))
        for w in t:
            df[w] = df.get(w, 0) + 1
    n = max(1, len(produtos))
    idf = lambda w: math.log(1 + n / (1 + df.get(w, 0)))

    pares = []
    for item in catalogo:
        alvo = _tokens(item.get("nome", ""))
        if len(alvo) < 2:
            continue
        peso_alvo = sum(idf(w) for w in alvo)
        if peso_alvo <= 0:
            continue
        achados = []
        for p, t in idx:
            comum = alvo & t
            if len(comum) < min_comum:
                continue
            # quanto do nome do fornecedor o anúncio cobre, em peso de informação
            cobertura = sum(idf(w) for w in comum) / peso_alvo
            if cobertura < corte:
                continue
            # sanidade de preço: o mesmo produto não custa 200× o que o fornecedor cobra
            custo, preco = item.get("unit"), p.get("pr")
            if custo and preco and not (MULT_MIN * custo <= preco <= MULT_MAX * custo):
                continue
            achados.append((round(cobertura, 3), sorted(comum), p))
        if not achados:
            continue
        achados.sort(key=lambda a: (-a[0], -(a[2].get("w") or 0)))
        pares.append({
            "fornecedor": {k: item.get(k) for k in ("nome", "unit", "caixa", "total", "url", "img")},
            "candidatos": [{
                "id": p.get("i"), "nome": p.get("n"), "preco": p.get("pr"), "vendas_sem": p.get("w"),
                "l1": p.get("l1"), "l2": p.get("l2"), "score": p.get("score"), "img": p.get("img"),
                "palavras": pal, "semelhanca": cob,
                # margem bruta antes de comissão, frete e imposto — o simulador dá o número final
                "margem": (round((p["pr"] - item["unit"]) / p["pr"], 3)
                           if p.get("pr") and item.get("unit") and p["pr"] > 0 else None),
            } for cob, pal, p in achados[:5]],
        })
    pares.sort(key=lambda x: -max((c["margem"] or 0) for c in x["candidatos"]))
    PARES.write_text(json.dumps(pares, ensure_ascii=False, indent=1), "utf-8")
    log.info("pares levantados: %d de %d itens do fornecedor", len(pares), len(catalogo))
    return pares


# ------------------------------------------------------- pesquisa na JoomPulse
BUSCA = config.DATA_DIR / "fornecedor_busca.json"
CAND_POR_ITEM = 12               # catálogos distintos por produto do fornecedor
LINHAS_POR_BUSCA = 60            # anúncios lidos por busca — muitos dividem o mesmo catálogo


def _consulta(nome: str) -> list[str]:
    """Variações do nome para a busca: o título inteiro e uma versão curta.

    O fornecedor escreve "Par Luva Motoqueiro Térmica E Impermeável Com Touch
    Screen"; a JoomPulse acha mais coisa com "luva motoqueiro térmica".
    """
    limpo = re.sub(r"\s+", " ", nome or "").strip()
    palavras = [w for w in re.split(r"[^\wÀ-ÿ]+", limpo) if len(w) > 2 and w.lower() not in _STOP]
    curto = " ".join(palavras[:4])
    return [q for q in dict.fromkeys([limpo, curto]) if q]


def _agrupa_por_catalogo(rows: list[dict], custo: float | None) -> list[dict]:
    """Uma linha por catálogo, não por vendedor.

    Desagrupado, o site repete o mesmo produto uma vez por vendedor — mesma foto,
    mesmo tempo no ar, mesmas avaliações. Para comparar produtos DIFERENTES, o que
    importa é o catálogo: quem mais vende vira o representante, os demais viram
    a contagem de vendedores e a faixa de preço.
    """
    from . import browser as B

    grupos: dict[str, list[dict]] = {}
    for r in rows:
        grupos.setdefault(B.catalog_key(r), []).append(r)
    saida = []
    for chave, irmaos in grupos.items():
        prods = [B.to_product(r) for r in irmaos]
        prods.sort(key=lambda p: (-(p["orderCount1w"] or 0), p["priceAmount"] or 9e9))
        rep = prods[0]
        precos = [p["priceAmount"] for p in prods if p["priceAmount"]]
        saida.append({
            "id": rep["id"], "nome": rep["productName"], "img": rep["productImage"], "chave": chave,
            "preco": rep["priceAmount"], "vendas_sem": rep["orderCount1w"], "receita_mes": rep["orderGmv1m"],
            "dias": rep["daysInAd"], "vendedor": rep["merchantName"], "catalogo": rep["catalogProduct"],
            "bb": len(prods) if rep["catalogProduct"] else None,
            "avaliacoes": rep["reviewsCount"], "nota": rep["reviewsRating"],
            "tipo": rep["listingType"], "frete_gratis": rep["isFreeShipping"],
            "preco_min": min(precos) if precos else None, "preco_max": max(precos) if precos else None,
            "outros": [{"id": p["id"], "vendedor": p["merchantName"], "preco": p["priceAmount"]}
                       for p in prods[1:8]],
            "margem": (round((rep["priceAmount"] - custo) / rep["priceAmount"], 3)
                       if rep.get("priceAmount") and custo else None),
        })
    saida.sort(key=lambda c: -(c["vendas_sem"] or 0))
    return saida


async def pesquisar(itens: list[dict], page) -> list[dict]:
    """Para cada item do fornecedor, os catálogos que a JoomPulse devolve pelo nome.

    Usa a sessão do navegador (a mesma da coleta), no modo desagrupado — assim
    cada anúncio vem com vendedor, preço, tempo no ar e a foto — e depois agrupa
    de volta por catálogo, para que cada linha seja um produto diferente.
    """
    from . import browser as B

    saida = []
    for it in itens:
        achados: dict[str, dict] = {}
        for q in _consulta(it["nome"]):
            try:
                rows = await B.scrape_search(page, {"query": q}, LINHAS_POR_BUSCA)
            except Exception as e:
                log.warning("busca falhou para %r: %s", q, type(e).__name__)
                continue
            for r in rows:
                achados.setdefault(r["id"], r)
            if len({B.catalog_key(r) for r in achados.values()}) >= CAND_POR_ITEM:
                break
        cands = _agrupa_por_catalogo(list(achados.values()), it.get("unit"))[:CAND_POR_ITEM]
        log.info("%s: %d anúncios, %d catálogos", it["nome"][:40], len(achados), len(cands))
        saida.append({"fornecedor": it, "anuncios": cands})
    BUSCA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), "utf-8")
    return saida
