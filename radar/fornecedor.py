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
import os
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


_ALIAS = {r"\bchhuveiro\b": "chuveiro", r"\bmáqiuna\b": "máquina", r"\bbilíngüe\b": "bilíngue", r"\balinhador\b": "corretor",
          r"\b(\d+(?:[.,]\d+)?)\s?cm\b": r"\1cm"}


def _consulta(nome: str) -> list[str]:
    """Variações do nome para a busca: o título inteiro e uma versão curta.

    O fornecedor escreve "Par Luva Motoqueiro Térmica E Impermeável Com Touch
    Screen"; a JoomPulse acha mais coisa com "luva motoqueiro térmica".
    """
    limpo = re.sub(r"\s+", " ", nome or "").strip()
    # erros de digitação do catálogo em PDF que a busca não perdoa
    for errado, certo in _ALIAS.items():
        limpo = re.sub(errado, certo, limpo, flags=re.I)
    palavras = [w for w in re.split(r"[^\wÀ-ÿ]+", limpo) if len(w) > 2 and w.lower() not in _STOP]
    curto = " ".join(palavras[:4])
    # último recurso: as duas palavras mais longas (as mais específicas), na ordem do título
    longas = sorted(sorted(range(len(palavras)), key=lambda i: -len(palavras[i]))[:2])
    minimo = " ".join(palavras[i] for i in longas)
    return [q for q in dict.fromkeys([limpo, curto, minimo]) if q]


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
            "l1": rep["merchantCategoryL1"],        # a comissão do ML depende da categoria
            "preco": rep["priceAmount"], "vendas_mes": rep["orderCount1m"], "vendas_sem": rep["orderCount1w"],
            "receita_mes": rep["orderGmv1m"],
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

    # incremental: o que já foi pesquisado fica; só os itens novos vão ao site
    saida = json.loads(BUSCA.read_text("utf-8")) if BUSCA.exists() else []
    # RADAR_REFAZER="colete alinhador,esterilizador": descarta e refaz os itens citados
    refazer = [t.strip().lower() for t in os.environ.get("RADAR_REFAZER", "").split(",") if t.strip()]
    if refazer:
        saida = [b for b in saida if not any(t in b["fornecedor"]["nome"].lower() for t in refazer)]
    feitos = {b["fornecedor"]["url"] for b in saida}
    itens = [it for it in itens if it["url"] not in feitos]
    log.info("itens a pesquisar: %d (já feitos: %d)", len(itens), len(feitos))
    for it in itens:
        achados: dict[str, dict] = {}
        for i, q in enumerate(_consulta(it["nome"])):
            if i >= 2 and achados:               # a busca de 2 palavras é só o último recurso
                break
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
        BUSCA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), "utf-8")   # salva a cada item
    BUSCA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), "utf-8")
    return saida


# ------------------------------------------------- categoria de cada produto
CATS = config.DATA_DIR / "fornecedor_categorias.json"

# na ficha do anúncio, o link de categoria de nível mais fundo é a folha
_JS_CAT_LINK = r"""() => {
  const a = [...document.querySelectorAll('a[href*="/dashboard/categories/"]')]
    .map(a => ({href: a.getAttribute('href') || '', nome: (a.innerText || '').trim()}))
    .filter(x => /\/categories\/(\d+)\/(MLB\d+)/.test(x.href) && x.nome);
  a.sort((x, y) => Number(y.href.match(/categories\/(\d+)\//)[1]) - Number(x.href.match(/categories\/(\d+)\//)[1]));
  return a[0] || null;
}"""

# na página da categoria: caminho completo (breadcrumb) e os cartões de números
_JS_CAT_PAGE = r"""() => {
  const NL = String.fromCharCode(10);
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  let caminho = [];
  const bc = document.querySelector('.ant-breadcrumb, nav[aria-label="breadcrumb"], [class*="breadcrumb"]');
  if (bc) caminho = bc.innerText.split(/[\/>›]/).map(clean).filter(s => s && s !== 'Categorias');
  if (!caminho.length) {
    const links = [...document.querySelectorAll('a[href*="/dashboard/categories/"]')]
      .map(a => ({lvl: Number(((a.getAttribute('href') || '').match(/categories\/(\d+)\//) || [])[1] || 0), nome: clean(a.innerText)}))
      .filter(x => x.lvl && x.nome);
    const byLvl = new Map(); links.forEach(x => { if (!byLvl.has(x.lvl)) byLvl.set(x.lvl, x.nome); });
    caminho = [...byLvl.keys()].sort((a, b) => a - b).map(k => byLvl.get(k));
  }
  const t = (document.querySelector('main') || document.body).innerText;
  const linhas = t.split(NL).map(clean).filter(Boolean);
  const bloco = (rotulo) => {
    const i = linhas.findIndex(s => s.toLowerCase().startsWith(rotulo));
    return i >= 0 ? linhas.slice(i, i + 6).join(' | ') : '';
  };
  const linhaBc = linhas.find(s => (s.match(/ \/ /g) || []).length >= 2) || '';
  return { caminho, linhaBc, oportunidade: bloco('oportunidade'), receita: bloco('receita'), vendas: bloco('vendas'),
           produtos: bloco('produtos'), ticket: bloco('ticket'), sazonalidade: bloco('sazonalidade'),
           insights: linhas.filter(s => /monopoliza|varia|medalha|por vendedor/i.test(s)).slice(0, 8),
           cabeca: linhas.slice(0, 40) };
}"""


def _pct_de(txt: str | None) -> float | None:
    m = re.search(r"([+\-−]?)\s?(\d+(?:[.,]\d+)?)\s?%", txt or "")
    if not m:
        return None
    v = float(m.group(2).replace(",", "."))
    return (-v if m.group(1) in ("-", "−") else v) / 100


def _valor_de(txt: str | None) -> float | None:
    """Primeiro valor 'grande' do bloco (R$ 640 mil, 26 mil, 1,2 mi...), ignorando o trecho em %."""
    from . import browser as B
    semp = re.sub(r"[+\-−]?\s?\d+(?:[.,]\d+)?\s?%", " ", txt or "")
    corpo = semp.split("|", 1)[1] if "|" in semp else semp
    m = re.search(r"(R\$\s?)?(\d[\d.,]*)\s?(mil|mi|bi|k|M)?\b", corpo)
    if not m:
        return None
    return B._big((m.group(1) or "") + m.group(2) + (" " + m.group(3) if m.group(3) else ""))


def _dica_de(opp_txt: str) -> str | None:
    """O conselho da JoomPulse para a categoria: 'Oportunidade | Explicar | Média | <dica> | Insights'."""
    m = re.search(r"\|\s?(?:Alta|Média|Baixa)\s?\|\s?(.+?)(?:\s?\|\s?Insights|$)", opp_txt or "")
    return m.group(1).strip() if m else None


def _ref_de(b: dict, ver: dict, url: str) -> dict:
    """Anúncio que representa o produto: igual > parecido > sem veredito; dentro do grupo, quem mais vende."""
    ordem = {"igual": 0, "parecido": 1, None: 2, "diferente": 3}

    def v(a):
        return ver.get(f'{url}|cat:{a.get("chave")}', ver.get(f'{url}|{a["id"]}', {})).get("veredito")
    # um anúncio "diferente" levaria à categoria de outro produto; melhor ficar sem
    uteis = [a for a in b["anuncios"] if v(a) != "diferente"]
    return sorted(uteis, key=lambda a: (ordem.get(v(a), 2), -(a.get("vendas_mes") or a.get("vendas_sem") or 0)))


async def _le_categoria(page, nivel: int, cid: str, nome: str, custo) -> tuple[dict, list]:
    from . import browser as B
    await page.goto(f"{B.BASE}/dashboard/categories/{nivel}/{cid}/products",
                    timeout=B.NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    await page.wait_for_timeout(8000)
    try:                                   # comparação com o mês anterior, não com a semana
        btn = page.get_by_text("Mês anterior", exact=True).first
        if await btn.count():
            await btn.click(timeout=4000)
            await page.wait_for_timeout(2500)
    except Exception:
        pass
    info = await page.evaluate(_JS_CAT_PAGE)
    cam = info.get("caminho") or []
    if not cam and info.get("linhaBc"):
        cam = [s.strip() for s in info["linhaBc"].split("/") if s.strip() and s.strip() != "Categorias"]
    # o breadcrumb da página lista só os ancestrais; a folha é o nome do link da ficha
    if nivel == 1:                          # categoria de topo: o caminho é só ela
        cam = [nome]
    elif nome and len(cam) < nivel and (not cam or cam[-1] != nome):
        cam = cam + [nome]
    opp_txt = info.get("oportunidade") or ""
    opp = next((k for k, t in (("high", "Alta"), ("medium", "Média"), ("low", "Baixa")) if t in opp_txt), None)
    mono = next((s for s in info.get("insights", []) if re.search(r"\d\s?%\s?monopoliza", s.lower())), "")
    saz = info.get("sazonalidade") or ""
    cat = {"id": cid, "nivel": nivel, "nome": nome, "caminho": cam,
           "l1": cam[0] if cam else None, "l2": cam[1] if len(cam) > 1 else None,
           "l3": cam[2] if len(cam) > 2 else None, "folha": cam[-1] if cam else nome, "opp": opp,
           "receita": _valor_de(info.get("receita")), "receita_var": _pct_de(info.get("receita")),
           "vendas": _valor_de(info.get("vendas")), "vendas_var": _pct_de(info.get("vendas")),
           "produtos": _valor_de(info.get("produtos")), "ticket": _valor_de(info.get("ticket")),
           "mono_pct": _pct_de(mono), "dica": _dica_de(opp_txt),
           "sazonalidade": saz.split("|")[1].strip() if "|" in saz else None,
           "bruto": {k: info.get(k) for k in ("oportunidade", "receita", "vendas", "insights", "linhaBc")}}
    rows = []
    try:
        if await B._rows_ready(page, tries=4):
            await B._periodo_mes(page)
            await B._ungroup(page)
            await B._set_page_size(page)
            rows = await page.evaluate(B._SCRAPE)
    except Exception as e:
        log.warning("tabela da categoria %s: %s", cid, type(e).__name__)
    cands = _agrupa_por_catalogo(rows, custo)[:10]
    for c in cands:
        c["l1"], c["l2"] = cat["l1"], cat["l2"]
    return cat, cands


async def categorias(itens: list[dict], page, busca: list[dict]) -> dict:
    """Descobre a categoria do ML de cada produto pesquisado e lê a página dela.

    O anúncio de referência (igual > parecido > o que mais vende) leva à ficha
    da JoomPulse, que linka a categoria folha; a página da categoria traz o
    caminho completo, receita e vendas com variação, oportunidade, monopolização
    e os produtos que mais vendem nela — o que alimenta "categoria em alta" e a
    lista "anúncios da mesma categoria" para quem não tem concorrente igual.
    Incremental: grava depois de cada produto e reaproveita categorias já lidas.
    """
    from . import browser as B

    saida = json.loads(CATS.read_text("utf-8")) if CATS.exists() else {}
    por_url = {b["fornecedor"]["url"]: b for b in busca}
    vfile = config.DATA_DIR / "fornecedor_veredito.json"
    ver = json.loads(vfile.read_text("utf-8")) if vfile.exists() else {}
    cache_cat = {v["cat"]["id"]: v["cat"] for v in saida.values() if v.get("cat") and v["cat"].get("caminho")}
    cache_prod = {v["cat"]["id"]: v.get("mesma_categoria", []) for v in saida.values() if v.get("cat")}

    for it in itens:
        feito = saida.get(it["url"])
        if feito and (feito.get("ref") is None or (feito.get("cat") and feito["cat"].get("caminho"))):
            continue
        b = por_url.get(it["url"])
        if not b or not b.get("anuncios"):
            continue
        fila = _ref_de(b, ver, it["url"])
        if not fila:
            log.info("%s: só anúncios diferentes, fica sem categoria", it["nome"][:36])
            saida[it["url"]] = {"ref": None, "cat": None, "mesma_categoria": []}
            CATS.write_text(json.dumps(saida, ensure_ascii=False, indent=1), "utf-8")
            continue
        # a ficha de alguns anúncios só mostra a categoria de topo; tenta até 3 anúncios
        # e fica com a categoria mais funda que aparecer
        link, ref = None, fila[0]
        for cand in fila[:3]:
            achado = None
            try:
                await page.goto(f"{B.BASE}/dashboard/beginner-products/{cand['id']}",
                                timeout=B.NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                for _ in range(10):
                    await page.wait_for_timeout(1500)
                    achado = await page.evaluate(_JS_CAT_LINK)
                    if achado:
                        break
            except Exception as e:
                log.warning("ficha %s: %s", cand["id"], type(e).__name__)
            if achado:
                nv = int(re.search(r"/categories/(\d+)/", achado["href"]).group(1))
                if not link or nv > int(re.search(r"/categories/(\d+)/", link["href"]).group(1)):
                    link, ref = achado, cand
                if nv >= 3:
                    break
        if not link:
            log.warning("%s: sem categoria na ficha de %s", it["nome"][:36], ref["id"])
            saida[it["url"]] = {"ref": ref["id"], "cat": None, "mesma_categoria": []}
            CATS.write_text(json.dumps(saida, ensure_ascii=False, indent=1), "utf-8")
            continue
        m = re.search(r"/categories/(\d+)/(MLB\d+)", link["href"])
        nivel, cid = int(m.group(1)), m.group(2)
        if cid not in cache_cat:
            try:
                cat, cands = await _le_categoria(page, nivel, cid, link["nome"], it.get("unit"))
            except Exception as e:
                log.warning("categoria %s: %s", cid, type(e).__name__)
                cat, cands = {"id": cid, "nivel": nivel, "nome": link["nome"], "caminho": [], "folha": link["nome"]}, []
            cache_cat[cid], cache_prod[cid] = cat, cands
            log.info("%s -> %s | opp %s | receita %s | vendas %s | %d produtos",
                     it["nome"][:30], " › ".join(cat["caminho"]) or link["nome"], cat.get("opp"),
                     cat.get("receita_var"), cat.get("vendas_var"), len(cands))
        saida[it["url"]] = {"ref": ref["id"], "cat": cache_cat[cid], "mesma_categoria": cache_prod.get(cid, [])}
        CATS.write_text(json.dumps(saida, ensure_ascii=False, indent=1), "utf-8")
    return saida
