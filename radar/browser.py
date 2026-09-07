"""Coletor via navegador: usa a sessão do próprio usuário na JoomPulse.

A JoomPulse não aceita cliente OAuth próprio (`invalid_client`) e o endpoint MCP
recusa cookie de sessão (401), então a coleta acontece pelo site: um Chromium com
perfil persistente guarda o login (feito uma vez, com o código por SMS/WhatsApp) e
depois abre as páginas sozinho e lê as tabelas.

    python -m radar login-browser     # uma vez: abre o navegador para você entrar
    python -m radar run --browser     # rodada usando a sessão guardada

O perfil fica em .secrets/browser-profile (fora do git, como o token).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from datetime import date as _date
from pathlib import Path

from . import config

log = logging.getLogger("radar.browser")

PROFILE_DIR = config.SECRETS_DIR / "browser-profile"
BASE = "https://joompulse.com"
DASHBOARD = f"{BASE}/dashboard"
SEARCH = f"{BASE}/dashboard/advanced-search"
CATEGORIES = f"{BASE}/dashboard/categories"

# Espera entre páginas: a JoomPulse tem proteção anti-bot (429 bot.limit_reached),
# então a coleta anda em ritmo humano em vez de disparar tudo de uma vez.
PAGE_PAUSE_S = float(os.environ.get("RADAR_BROWSER_PAUSE", "2.5"))
# Teto para abrir a árvore de categorias — ela é grande e só interessa até o 3º nível.
EXPAND_BUDGET_S = float(os.environ.get("RADAR_EXPAND_BUDGET", "150"))
# Varredura por subcategoria: são centenas, então cada uma rende poucos produtos.
# 0 em RADAR_L2_LIMIT = todas as subcategorias.
L2_LIMIT = int(os.environ.get("RADAR_L2_LIMIT", "0"))
L2_MAIN_LIMIT = int(os.environ.get("RADAR_L2_MAIN", "25"))
# Segunda varredura só para anúncios novos: dobra o tempo da rodada e rende pouco,
# porque num recorte de subcategoria os novos que vendem já sobem no top. 0 = desligada.
L2_NEW_LIMIT = int(os.environ.get("RADAR_L2_NEW", "0"))
NAV_TIMEOUT_MS = 60_000


def _ctx(pw, headless: bool):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=headless,
        viewport={"width": 1600, "height": 1000},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        args=["--disable-blink-features=AutomationControlled"],
    )


async def logged_in(page) -> bool:
    """Sessão viva? O site manda para /auth quando não está."""
    await page.goto(DASHBOARD, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    return "/auth" not in page.url


async def login() -> bool:
    """Abre o navegador para o login manual (telefone + código) e guarda a sessão."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await _ctx(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        if await logged_in(page):
            print("Sessão já está ativa — nada a fazer.")
            await ctx.close()
            return True

        print("\n" + "=" * 68)
        print("  Entre na JoomPulse na janela que abriu:")
        print("    1. digite o telefone do seu sócio (+55 11 97292 8835)")
        print("    2. peça o código que chega por SMS/WhatsApp e cole no site")
        print("    3. quando o painel abrir, volte aqui — o resto é automático")
        print("=" * 68 + "\n")
        await page.goto(f"{BASE}/auth", timeout=NAV_TIMEOUT_MS)

        for _ in range(120):                      # até 10 minutos
            await page.wait_for_timeout(5000)
            if "/auth" not in page.url and "/dashboard" in page.url:
                await page.wait_for_timeout(2000)
                print("Login guardado. Pode fechar a janela.")
                await ctx.close()
                return True
        print("Tempo esgotado sem login.")
        await ctx.close()
        return False


async def check() -> bool:
    """Diz se a sessão guardada ainda serve."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        ctx = await _ctx(pw, headless=True)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        ok = await logged_in(page)
        await ctx.close()
        return ok


# ---------------------------------------------------------------- extração
# Colunas da tabela de "Busca de produtos", na ordem em que aparecem.
# As duas primeiras são a caixa de seleção e o menu de contexto.
COLS = ["_sel", "_menu", "img", "nome", "receita", "vendas_media", "vendas_total", "categoria",
        "preco", "listagem", "marca", "dias", "vendedor", "vend_detalhe", "imagens",
        "avaliacoes", "classificacao"]

_NUM = re.compile(r"-?[\d.]+(?:,\d+)?")


def _num(txt: str | None) -> float | None:
    """'R$ 40.598.013,00' -> 40598013.0 ; '~R$ 599,00' -> 599.0 ; '–' -> None"""
    if not txt:
        return None
    m = _NUM.search(txt.replace(" ", " "))
    if not m:
        return None
    try:
        return float(m.group(0).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _int(txt: str | None) -> int | None:
    v = _num(txt)
    return None if v is None else int(v)


# JS que lê a tabela inteira de uma vez — devolve uma lista de objetos por linha.
# Roda dentro da página, então nada disso passa pelo modelo: o Python recebe o
# resultado pronto e grava em disco.
_SCRAPE = """
() => {
  const out = [];
  for (const tr of document.querySelectorAll('tr')) {
    const tds = tr.querySelectorAll('td');
    if (tds.length < 15) continue;
    const txt = i => (tds[i]?.innerText || '').replace(/\\u00a0/g, ' ').trim();
    const nome = txt(3);
    const mlb = (nome.match(/MLB\\d{6,}/) || [])[0];
    if (!mlb) continue;
    const img = tds[2]?.querySelector('img');
    const link = [...tr.querySelectorAll('a')].map(a => a.href).find(h => /mercadolivre|mercadolibre/.test(h)) || null;
    out.push({
      id: mlb,
      nome: nome.split('\\n')[0].trim(),
      img: img ? (img.currentSrc || img.src) : null,
      link,
      catalogo: /Abrir catálogo|Catálogo total/.test(nome + txt(4)),
      receita: txt(4), vendas_media: txt(5), vendas_total: txt(6),
      categoria: txt(7), preco: txt(8), listagem: txt(9), marca: txt(10),
      dias: txt(11), vendedor: txt(12), vend_detalhe: txt(13),
      imagens: txt(14), avaliacoes: txt(15), classificacao: txt(16),
    });
  }
  return out;
}
"""


async def _set_page_size(page, size: int = 100) -> None:
    """Troca o '10 / página' do rodapé pelo maior valor disponível."""
    try:
        sel = page.locator(".ant-pagination-options .ant-select").first
        if not await sel.count():
            return
        await sel.click(timeout=8000)
        await page.wait_for_timeout(600)
        opt = page.locator(f".ant-select-item-option:has-text('{size} / página')").first
        if await opt.count():
            await opt.click(timeout=8000)
            await page.wait_for_timeout(2500)
            log.info("página ajustada para %d itens", size)
    except Exception as e:  # o seletor é cosmético: se falhar, seguimos com 10/página
        log.debug("não deu para mudar o tamanho da página: %s", e)


async def _goto_page(page, n: int) -> bool:
    """Vai para a página n da paginação. False quando ela não existe."""
    item = page.locator(f".ant-pagination-item-{n}").first
    if not await item.count():
        return False
    try:
        await item.click(timeout=10_000)
    except Exception as e:
        log.warning("paginação parou na página %d: %s", n, type(e).__name__)
        return False
    await page.wait_for_timeout(int(PAGE_PAUSE_S * 1000))
    return True


async def _rows_ready(page, tries: int = 12) -> bool:
    """A tabela é preenchida depois do HTML; espera aparecer linha com id MLB."""
    for _ in range(tries):
        n = await page.evaluate(
            "() => [...document.querySelectorAll('tr')].filter(t => /MLB\\d{6,}/.test(t.innerText)).length")
        if n:
            return True
        await page.wait_for_timeout(2500)
    return False


async def _ungroup(page) -> None:
    """'Desagrupar catálogos': sem isso o vendedor, o tipo de anúncio e as
    avaliações vêm vazios, porque a linha representa o catálogo e não o anúncio."""
    try:
        btn = page.locator("text=Desagrupar catálogos").first
        if await btn.count():
            await btn.click(timeout=10_000)
            await page.wait_for_timeout(int(PAGE_PAUSE_S * 1000) + 3000)
    except Exception as e:
        log.debug("não deu para desagrupar: %s", e)


async def scrape_search(page, params: dict, max_rows: int) -> list[dict]:
    """Abre a busca com os filtros dados e lê a tabela, paginando até max_rows."""
    from urllib.parse import urlencode

    url = f"{SEARCH}?{urlencode(params)}"
    await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    if not await _rows_ready(page):
        log.warning("sem resultados para %s", params)
        return []
    await _ungroup(page)
    await _set_page_size(page)

    rows: list[dict] = []
    seen: set[str] = set()
    for n in range(1, 60):
        got = await page.evaluate(_SCRAPE)
        novos = [r for r in got if r["id"] not in seen]
        for r in novos:
            seen.add(r["id"])
        rows.extend(novos)
        if len(rows) >= max_rows or not novos:
            break
        if not await _goto_page(page, n + 1):
            break
    return rows[:max_rows]


# ------------------------------------------------- tradução para o formato do motor
# O engine espera as mesmas chaves que o CubeJS devolve (radar/queries.py). O site
# entrega menos campos, então o que não existe vira None e o Scorer trata como neutro.
_LISTING = {"premium": "gold_pro", "clássico": "gold_special", "classico": "gold_special", "grátis": "free"}


def catalog_key(r: dict) -> str:
    """Identidade do produto de catálogo.

    Desagrupado, o mesmo produto aparece uma vez por vendedor — mesma foto, mesmo
    título, preços diferentes. O site não mostra o id do catálogo, então usamos
    foto+título como identidade; é o que o `dedupe` do engine espera em productId,
    e é também o que permite contar quantos concorrentes disputam o anúncio.
    """
    img = (r.get("img") or "").split("?")[0]
    return "cat:" + hashlib.sha1((img + "|" + (r.get("nome") or "")[:70]).encode("utf-8")).hexdigest()[:16]


def to_product(r: dict, l1: str | None = None, l2: str | None = None, l3: str | None = None,
               bb: int | None = None, l2id: str | None = None) -> dict:
    """Uma linha da tabela vira o mesmo dicionário que o CubeJS devolveria.

    O site não expõe subcategoria nem nível de concorrência: quando a busca foi
    feita por uma categoria de nível 2/3, o chamador informa em l2/l3 (ele sabe,
    porque foi ele quem filtrou). O que continua sem fonte fica None e o Scorer
    trata como neutro.
    """
    cat = (r.get("categoria") or "").strip()
    listing = (r.get("listagem") or "").lower()
    tipo = next((v for k, v in _LISTING.items() if k in listing), None)
    return {
        "id": r["id"],
        # catálogo: todos os anúncios do mesmo produto compartilham a chave, e o
        # dedupe do engine fica com o que mais vende
        "productId": catalog_key(r) if ("no catálogo" in listing or r.get("catalogo")) else None,
        "userProductId": None,
        "catalogProduct": "no catálogo" in listing or bool(r.get("catalogo")),
        "productName": r.get("nome"),
        "productImage": r.get("img"),
        "merchantName": (r.get("vendedor") or "").split("\n")[0].strip() or None,
        "brand": (r.get("marca") or "").strip() or None,
        "categoryId": l2id,
        # o Scorer casa a subcategoria por este id — é ele que liga o produto aos
        # dados de oportunidade, monopolização e crescimento da categoria
        "merchantCategoryIdL2": l2id,
        "merchantCategoryL1": l1 or cat or None,
        "merchantCategoryL2": l2,
        "merchantCategoryL3": l3,
        "sellerMedal": None,
        "sellerReputation": None,
        "isFull": "full" in listing or None,
        "isFreeShipping": "frete grátis" in listing or None,
        "listingType": tipo,
        "l2CompetitivenessLevel": None,
        "priceAmount": _num(r.get("preco")),
        "orderCount1w": _int(r.get("vendas_media")),
        "orderCount1m": None,
        "orderGmv1m": _num(r.get("receita")),
        "reviewsCount": _int(r.get("avaliacoes")),
        "reviewsRating": _num(r.get("classificacao")),
        "daysInAd": _int(r.get("dias")),
        "numBuyBoxSellers": bb,
    }


def count_buybox(rows: list[dict]) -> dict[str, int]:
    """Quantos anúncios disputam o mesmo produto.

    No modo desagrupado o mesmo catálogo aparece uma vez por vendedor, então
    contar as linhas que repetem título+imagem dá o número de concorrentes —
    que é justamente o `numBuyBoxSellers` que o site não mostra em coluna.
    """
    tally: dict[str, int] = {}
    for r in rows:
        k = catalog_key(r)
        tally[k] = tally.get(k, 0) + 1
    return {r["id"]: tally[catalog_key(r)] for r in rows}


# ------------------------------------------------------------- categorias
# "R$ 2,7 bi" -> 2700000000 ; "17 mi" -> 17000000 ; "186 mil" -> 186000
_MULT = {"bi": 1e9, "mi": 1e6, "mil": 1e3, "k": 1e3}


def _big(txt: str | None) -> float | None:
    if not txt:
        return None
    v = _num(txt)
    if v is None:
        return None
    low = txt.lower()
    for suf, mult in _MULT.items():
        if re.search(rf"\d\s*{suf}\b", low):
            return v * mult
    return v


def _pct(txt: str | None) -> float | None:
    """'+22,1%' -> 0.221 ; '-5,75%' -> -0.0575"""
    if not txt or "%" not in txt:
        return None
    v = _num(txt)
    if v is None:
        return None
    return (-v if txt.strip().startswith("-") and v > 0 else v) / 100


_LEVEL_WORD = {"alta": "high", "média": "medium", "media": "medium", "baixa": "low"}


def _lvl(txt: str | None) -> str | None:
    if not txt:
        return None
    return _LEVEL_WORD.get(txt.strip().lower().split()[0] if txt.strip() else "", None)


# Lê a tabela de categorias inteira (inclui as linhas abertas pela expansão).
_SCRAPE_CATS = r"""() => {
  const NL = String.fromCharCode(10);
  const cell = td => (td.innerText || '').split(NL).map(s => s.trim()).filter(Boolean);
  const out = [];
  for (const tr of document.querySelectorAll('tr')) {
    const tds = tr.querySelectorAll('td');
    if (tds.length < 8) continue;
    const nome = cell(tds[0]);
    if (!nome.length || nome[0] === 'Categoria') continue;
    const m = tr.className.match(/ant-table-row-level-(\d)/);
    // o link da categoria carrega nível e id: /dashboard/categories/2/MLB1747/products
    const a = tds[0].querySelector('a');
    const href = a ? (a.getAttribute('href') || '') : '';
    const idm = href.match(/\/categories\/(\d+)\/(MLB\d+)\//);
    out.push({
      depth: m ? Number(m[1]) : 0,
      catId: idm ? idm[2] : null,
      catLevel: idm ? Number(idm[1]) : null,
      nome: nome[0],
      opp: cell(tds[1])[0] || null,
      receita: cell(tds[2]),
      vendas: cell(tds[3]),
      vendedores: cell(tds[4]),
      mono: cell(tds[5]),
      sazon: cell(tds[6]),
      rps: cell(tds[7]),
      ticket: tds[10] ? cell(tds[10]) : [],
    });
  }
  return out;
}"""


def cat_to_row(c: dict, l1: str, l2: str | None, l3: str | None = None, depth: int | None = None) -> dict:
    """Linha da tabela de categorias -> dicionário no formato do CubeJS.

    A árvore do Mercado Livre é mais funda que os dois níveis que o radar pontua,
    então tudo abaixo do segundo nível é tratado como nível 3 do seu ramo.
    """
    depth = c["depth"] if depth is None else depth
    nome = c["nome"]
    rec, ven, vds, mono, rps, tk = c["receita"], c["vendas"], c["vendedores"], c["mono"], c["rps"], c["ticket"]
    g = lambda lst, i: lst[i] if len(lst) > i else None
    lvl = 2 if depth == 1 else 3            # 2 = subcategoria; 3 = qualquer folha abaixo
    return {
        # id verdadeiro quando o link da linha o revela; senão, o caminho
        "categoryId": c.get("catId") or "|".join(x for x in [l1, l2, l3] if x),
        "categoryName": nome,
        "level": lvl,
        "parentId": l1 if lvl == 2 else f"{l1}|{l2}",
        "merchantCategoryL1": l1,
        "merchantCategoryL2": l2,
        "merchantCategoryL3": l3 if lvl == 3 else None,
        "opportunityLevel": _lvl(c.get("opp")),
        "monopolisationFilter": _lvl(g(mono, 0)),
        "saturationFilter": None,
        "revenueGrowthFilter": None,
        "revenuePerSellerFilter": None,
        "seasonality": "non_seasonal" if "Sem período" in " ".join(c.get("sazon") or []) else "seasonal",
        "seasonalityHighMonth": "[]",
        # o site mostra sempre o mês fechado mais recente
        "date": _date.today().replace(day=1).isoformat(),
        "orderCount": _big(g(ven, 0)),
        "orderGmv": _big(g(rec, 0)),
        "orderGmvGrowth1m": _pct(g(rec, 1)),
        "orderCountGrowth1m": _pct(g(ven, 1)),
        "currentTrend12m": None,            # o site só mostra a variação do mês
        "currentTrend24m": None,
        "monopolisation": (_num(g(mono, 1)) or 0) / 100 if g(mono, 1) else None,
        "numSellers": _big(g(vds, 0)),
        "numSellersWithSales": None,
        "revenuePerSeller1m": _big(g(rps, 0)),
        "averageTicket": _big(g(tk, 0)),
        "numProducts": None,
        "numProductsWithSales": None,
    }


async def scrape_categories(page, expand_l2: bool = True) -> list[dict]:
    """Abre a página de Categorias e expande as linhas para pegar L2 (e L3)."""
    await page.goto(CATEGORIES, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
    for _ in range(12):
        if await page.evaluate("() => document.querySelectorAll('.ant-table-row-expand-icon').length"):
            break
        await page.wait_for_timeout(2500)

    n = await page.evaluate("() => document.querySelectorAll('.ant-table-row-expand-icon').length")
    log.info("categorias: %d linhas de nível 1", n)

    # A tabela funciona como acordeão — abrir uma categoria fecha a anterior — e
    # ainda é virtualizada. Então abrimos uma por vez, lemos as subcategorias que
    # ela revela, e passamos para a próxima.
    raw: list[dict] = []
    vistos: set[tuple] = set()

    def guardar(lote, pai=None):
        """Anota o pai na hora da leitura.

        Reconstruir a hierarquia pela ordem das linhas não funciona: como lemos em
        várias passadas (uma por categoria aberta), a ordem final mistura tudo e
        toda subcategoria acabaria herdando a última categoria vista.
        """
        novos = 0
        for c in lote:
            k = (c["depth"], c["nome"], c.get("catId"))
            if k in vistos:
                continue
            vistos.add(k)
            c["pai"] = pai if c["depth"] > 0 else None
            raw.append(c)
            novos += 1
        return novos

    guardar(await page.evaluate(_SCRAPE_CATS))          # as 28 de nível 1
    nomes_l1 = [c["nome"] for c in raw if c["depth"] == 0]

    if expand_l2:
        limite = time.monotonic() + EXPAND_BUDGET_S
        for nome in nomes_l1:
            if time.monotonic() > limite:
                log.info("tempo de expansão esgotado; %d de %d categorias abertas",
                         nomes_l1.index(nome), len(nomes_l1))
                break
            # Localizar por nome, e não por índice: a tabela é virtualizada, então
            # "a i-ésima linha" é a i-ésima RENDERIZADA — ao rolar, o índice deixa
            # de corresponder à categoria e as subcategorias vão para o pai errado.
            linha = page.locator("tr.ant-table-row-level-0").filter(has_text=nome).first
            try:
                await linha.scroll_into_view_if_needed(timeout=6000)
                await linha.locator(".ant-table-row-expand-icon").click(timeout=6000)
                await page.wait_for_timeout(900)
            except Exception:
                log.debug("não abriu %s", nome)
                continue
            guardar(await page.evaluate(_SCRAPE_CATS), nome)
            for _ in range(10):
                fim_pagina = await page.evaluate(
                    "() => { const y = window.scrollY;"
                    " window.scrollBy(0, window.innerHeight * 0.85); return window.scrollY === y; }")
                await page.wait_for_timeout(350)
                guardar(await page.evaluate(_SCRAPE_CATS), nome)
                if fim_pagina:
                    break
            # fecha antes da próxima: garante que o que estiver aberto no DOM
            # pertence sempre à categoria que acabamos de nomear
            try:
                await linha.scroll_into_view_if_needed(timeout=4000)
                await linha.locator(".ant-table-row-expand-icon").click(timeout=4000)
                await page.wait_for_timeout(400)
            except Exception:
                pass
            await page.evaluate("() => window.scrollTo(0, 0)")
            await page.wait_for_timeout(250)
        log.info("categorias no DOM após varredura: %d", len(raw))

    # A tabela vem achatada, com a profundidade em cada linha. Uma pilha reconstrói
    # o caminho: quem está em depth 2 pertence ao último depth 1, e assim por diante.
    # O radar só pontua nível 2 e 3; abaixo disso a linha vira nível 3 do seu ramo.
    rows = []
    for c in raw:
        d = c["depth"]
        if d == 0 or not c.get("pai"):
            continue                        # L1 não entra no ranking de subcategoria
        if d == 1:
            l1, l2, l3 = c["pai"], c["nome"], None
        else:
            l1, l2, l3 = c["pai"], None, c["nome"]
        rows.append(cat_to_row(c, l1, l2, l3, depth=d))
    log.info("categorias lidas: %d (níveis %s)", len(rows), sorted({r["level"] for r in rows}))
    return rows


# ------------------------------------------------- ids das categorias L1
# A busca filtra por `category=<nivel>,<id>`. Estes sao os ids do Mercado Livre
# para as 28 categorias de primeiro nivel.
L1_IDS: dict[str, str] = {
    'Acessórios para Veículos': 'MLB5672',
    'Agro': 'MLB271599',
    'Alimentos e Bebidas': 'MLB1403',
    'Antiguidades e Coleções': 'MLB1367',
    'Arte, Papelaria e Armarinho': 'MLB1368',
    'Bebês': 'MLB1384',
    'Beleza e Cuidado Pessoal': 'MLB1246',
    'Brinquedos e Hobbies': 'MLB1132',
    'Calçados, Roupas e Bolsas': 'MLB1430',
    'Casa, Móveis e Decoração': 'MLB1574',
    'Celulares e Telefones': 'MLB1051',
    'Construção': 'MLB1500',
    'Câmeras e Acessórios': 'MLB1039',
    'Eletrodomésticos': 'MLB5726',
    'Eletrônicos, Áudio e Vídeo': 'MLB1000',
    'Esportes e Fitness': 'MLB1276',
    'Ferramentas': 'MLB263532',
    'Festas e Lembrancinhas': 'MLB12404',
    'Games': 'MLB1144',
    'Indústria e Comércio': 'MLB1499',
    'Informática': 'MLB1648',
    'Instrumentos Musicais': 'MLB1182',
    'Joias e Relógios': 'MLB3937',
    'Livros, Revistas e Comics': 'MLB1196',
    'Mais Categorias': 'MLB1953',
    'Música, Filmes e Seriados': 'MLB1168',
    'Pet Shop': 'MLB1071',
    'Saúde': 'MLB264586',
}


# ------------------------------------------------------------------- fonte
class BrowserSource:
    """Implementa a mesma interface de radar.run.Source, mas lendo o site.

    Diferenças em relação ao MCP, todas por limitação do que a tela mostra:
      * o produto vem com a categoria de nível 1 apenas (a busca é feita por L1);
      * `numBuyBoxSellers` é contado pelas repetições do catálogo, não informado;
      * não há releitura por id — quem sai da descoberta é tratado como ausente.
    """

    def __init__(self, page, l1_ids: dict[str, str] | None = None):
        self.page = page
        self.l1_ids = l1_ids or {}
        self.calls = 0

    def _params(self, l1: str, extra: dict | None = None) -> dict:
        p: dict[str, str] = {"monthlySalesFrom": "30"}
        cid = self.l1_ids.get(l1)
        if cid:
            p["category"] = f"1,{cid}"
        p.update(extra or {})
        return p

    async def l2_targets(self) -> list[tuple[str, str, str]]:
        """(l1, nome da subcategoria, id) para cada nível 2 conhecido.

        A busca só devolve a categoria pela qual você filtrou, então é filtrando
        por subcategoria que o produto ganha um L2 — e é o L2 que casa com os
        dados de oportunidade e monopolização no score.
        """
        if not hasattr(self, "_cats"):
            self.calls += 1
            self._cats = await scrape_categories(self.page)
        alvos = [(c["merchantCategoryL1"], c["merchantCategoryL2"], c["categoryId"])
                 for c in self._cats
                 if c["level"] == 2 and str(c["categoryId"]).startswith("MLB")]
        # maiores primeiro: se o tempo apertar, o que fica de fora é o que menos pesa
        peso = {c["categoryId"]: (c.get("orderGmv") or 0) for c in self._cats}
        alvos.sort(key=lambda t: -peso.get(t[2], 0))
        if L2_LIMIT:
            alvos = alvos[:L2_LIMIT]
        log.info("subcategorias a varrer: %d", len(alvos))
        return alvos

    async def _search_l2(self, l1: str, l2: str, cid: str, extra: dict, limit: int) -> list[dict]:
        self.calls += 1
        try:
            params = {"monthlySalesFrom": "30", "category": f"2,{cid}", **extra}
            raw = await scrape_search(self.page, params, limit)
        except Exception as e:
            log.warning("falha lendo %s › %s: %s", l1, l2, type(e).__name__)
            return []
        bb = count_buybox(raw)
        return [to_product(r, l1=l1, l2=l2, bb=bb.get(r["id"]), l2id=cid) for r in raw]

    async def _search(self, l1: str, extra: dict, limit: int) -> list[dict]:
        self.calls += 1
        try:
            raw = await scrape_search(self.page, self._params(l1, extra), limit)
        except Exception as e:
            # o site às vezes engasga numa categoria; seguir com as outras vale
            # mais do que perder a rodada inteira
            log.warning("falha lendo %s (%s): %s", l1, extra or "top", type(e).__name__)
            return []
        bb = count_buybox(raw)
        return [to_product(r, l1=l1, bb=bb.get(r["id"])) for r in raw]

    async def _por_subcategoria(self, l1: str, extra: dict, limit: int) -> list[dict]:
        alvos = [t for t in await self.l2_targets() if t[0] == l1]
        if not alvos:                                   # sem subcategoria conhecida, cai no L1
            return await self._search(l1, extra, limit)
        out: list[dict] = []
        for _, l2, cid in alvos:
            out.extend(await self._search_l2(l1, l2, cid, extra, limit))
        return out

    async def products_top(self, l1: str) -> list[dict]:
        return await self._por_subcategoria(l1, {}, L2_MAIN_LIMIT)

    async def products_new(self, l1: str) -> list[dict]:
        if not L2_NEW_LIMIT:
            return []
        return await self._por_subcategoria(
            l1, {"adFrom": "0", "adTo": str(config.NEW_LISTING_MAX_DAYS)}, L2_NEW_LIMIT)

    async def products_by_ids(self, ids: list[str]) -> list[dict]:
        return []                            # a tela não permite reler por lista de ids

    async def categories(self, level: int) -> list[dict]:
        # a página traz a árvore inteira de uma vez; devolvemos o nível pedido
        if not hasattr(self, "_cats"):
            self.calls += 1
            self._cats = await scrape_categories(self.page)
        return [c for c in self._cats if c["level"] == level]

    async def joompro(self) -> list[dict]:
        return []                            # o pareamento JoomPro não está na tela de busca


async def open_source(l1_ids: dict[str, str] | None = None):
    """Contexto que devolve (BrowserSource, fechar) com a sessão guardada."""
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    ctx = await _ctx(pw, headless=os.environ.get("RADAR_BROWSER_HEADED") != "1")
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    if not await logged_in(page):
        await ctx.close()
        await pw.stop()
        raise SystemExit("Sessão do navegador expirada. Rode `python -m radar login-browser`.")

    async def close():
        await ctx.close()
        await pw.stop()

    return BrowserSource(page, l1_ids), close
