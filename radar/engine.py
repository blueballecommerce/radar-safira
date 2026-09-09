"""Normalização, deduplicação, score e ranking.

O score (0–100) é a única "opinião" do sistema; tudo o mais vem da JoomPulse:
  demanda 35 · pouca concorrência 25 · categoria crescendo 25 · novo e vendendo 15
"""
from __future__ import annotations

import bisect
import math
import re
import unicodedata

from . import config

W = config.WEIGHTS
CL = {"low": 1.0, "mid": 0.6, "high": 0.25}
MONO = {"low": 1.0, "medium": 0.6, "high": 0.2}
SAT = {"low": 1.0, "medium": 0.6, "high": 0.3}
OPP = {"high": 1.0, "medium": 0.5, "low": 0.0}


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _num(x):
    return None if x is None else (round(x, 2) if isinstance(x, float) else x)


def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


# ---------------------------------------------------------------- normalize
def product_from_row(r: dict, src: str) -> dict | None:
    if not r.get("orderCount1w") and src != "track":
        return None
    p = {
        "i": r["id"], "p": r.get("productId"), "u": r.get("userProductId"), "c": bool(r.get("catalogProduct")),
        "n": r.get("productName"), "img": r.get("productImage"), "s": r.get("merchantName"), "b": r.get("brand"),
        "cid": r.get("categoryId"), "l2id": r.get("merchantCategoryIdL2"),
        "l1": r.get("merchantCategoryL1"), "l2": r.get("merchantCategoryL2"), "l3": r.get("merchantCategoryL3"),
        "md": r.get("sellerMedal"), "rep": r.get("sellerReputation"),
        "full": bool(r.get("isFull")), "fs": bool(r.get("isFreeShipping")), "lt": r.get("listingType"),
        "cl": r.get("l2CompetitivenessLevel"),
        "pr": _num(r.get("priceAmount")), "w": int(r.get("orderCount1w") or 0), "m": r.get("orderCount1m"),
        "g": _num(r.get("orderGmv1m")), "rc": r.get("reviewsCount"), "rr": _num(r.get("reviewsRating")),
        "d": None if r.get("daysInAd") is None else int(round(r["daysInAd"])),
        "bb": r.get("numBuyBoxSellers"), "src": src,
        # data de criação do anúncio (só o MCP informa); a página calcula a idade na hora
        "pub": (r.get("adPublishDate") or None) and str(r["adPublishDate"])[:10],
        "riv": r.get("rivals") or [],       # outros anúncios do mesmo catálogo
    }
    p["key"] = p["p"] or p["i"]
    return p


def category_from_row(r: dict) -> dict:
    return {
        "id": r["categoryId"], "name": r.get("categoryName"), "lv": r.get("level"), "par": r.get("parentId"),
        "l1": r.get("merchantCategoryL1"), "l2": r.get("merchantCategoryL2"), "l3": r.get("merchantCategoryL3"),
        "opp": r.get("opportunityLevel"), "mono": r.get("monopolisationFilter"), "sat": r.get("saturationFilter"),
        "rg": r.get("revenueGrowthFilter"), "rps": r.get("revenuePerSellerFilter"),
        "seas": r.get("seasonality"), "seasM": r.get("seasonalityHighMonth"), "month": (r.get("date") or "")[:7],
        "oc": r.get("orderCount"), "gmv": _num(r.get("orderGmv")),
        "gG": _num(r.get("orderGmvGrowth1m")), "ocG": _num(r.get("orderCountGrowth1m")),
        "t12": r.get("currentTrend12m"), "t24": r.get("currentTrend24m"), "monoV": _num(r.get("monopolisation")),
        "ns": r.get("numSellers"), "nss": r.get("numSellersWithSales"),
        "rps1m": _num(r.get("revenuePerSeller1m")), "tk": _num(r.get("averageTicket")),
        "np": r.get("numProducts"), "nps": r.get("numProductsWithSales"),
    }


def joompro_from_row(r: dict) -> dict:
    return {
        "id": r.get("joomproProductId"), "t": r.get("title"), "img": r.get("imageUrl"), "q": _num(r.get("qualityScore")),
        "jl1": r.get("l1CategoryName"), "jcat": r.get("categoryName"),
        "p": r.get("productId"), "mt": r.get("meliTitle"), "ml1": r.get("meliL1CategoryName"), "mcat": r.get("meliCategoryName"),
        "c": bool(r.get("catalogProduct")), "sc": _num(r.get("score")), "mo": r.get("meliCatalogOrders1m"),
        "jp": _num(r.get("joomproPriceAmount")), "moq": r.get("minAvailableMoq"),
        "sb": bool(r.get("smallBatchAvailable")), "sbm": r.get("smallBatchMoq"),
        "mmin": _num(r.get("meliPriceMin")), "mmax": _num(r.get("meliPriceMax")), "nl": r.get("meliNumListings"),
        "pf": _num(r.get("profit")), "mg": _num(r.get("marginality")), "ve": r.get("volumetricEfficient"), "bq": r.get("boxQty"),
        "ju": r.get("joomproUrl"), "mu": r.get("meliUrl"), "pu": r.get("pulseUrl"), "asOf": (r.get("asOfDate") or "")[:10],
    }


# ---------------------------------------------------------------- dedupe
def _merge_rivals(fica: dict, sai: dict) -> list[dict]:
    """Junta as listas de concorrentes de dois anúncios do mesmo produto.

    Quem perde o lugar no ranking não desaparece: passa a constar como
    concorrente de quem ficou, para dar para comparar preço e tempo de anúncio.
    """
    vistos, saida = {fica["i"]}, []
    for r in (fica.get("riv") or []) + (sai.get("riv") or []) + [
            {"id": sai["i"], "s": sai.get("s"), "pr": sai.get("pr"), "d": sai.get("d")}]:
        rid = r.get("id")
        if not rid or rid in vistos:
            continue
        vistos.add(rid)
        saida.append(r)
    return saida


def dedupe(products: list[dict]) -> list[dict]:
    """Um por produto de catálogo (fica o anúncio que mais vende) e um por (vendedor, título)."""
    by_key: dict[str, dict] = {}
    for p in products:
        prev = by_key.get(p["key"])
        if prev is None or p["w"] > prev["w"]:
            if prev:
                if prev["src"] == "new":
                    p["src"] = "new"
                # o anúncio que sai vira concorrente do que fica
                p["riv"] = _merge_rivals(p, prev)
            by_key[p["key"]] = p
        else:
            if p["src"] == "new":
                prev["src"] = "new"
            prev["riv"] = _merge_rivals(prev, p)
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for p in sorted(by_key.values(), key=lambda x: -x["w"]):
        k2 = (norm(p["s"]), norm(p["n"]))
        if k2 in seen:
            continue
        seen.add(k2)
        out.append(p)
    return out


# ---------------------------------------------------------------- scoring
class Scorer:
    def __init__(self, products: list[dict], categories: list[dict]):
        self.l3 = {(c["l1"], c["l2"], c["l3"]): c for c in categories if c.get("lv") == 3}
        self.l2 = {c["id"]: c for c in categories if c.get("lv") == 2}
        self.logw = sorted(math.log(max(p["w"], 1)) for p in products if p["w"] > 0) or [0.0]

    def pct(self, w: int) -> float:
        if w <= 0:
            return 0.0
        return bisect.bisect_left(self.logw, math.log(w)) / len(self.logw)

    def cat(self, p: dict) -> dict | None:
        return self.l3.get((p["l1"], p["l2"], p["l3"])) or self.l2.get(p["l2id"])

    def score(self, p: dict) -> None:
        c = self.cat(p)
        cl = CL.get(p["cl"], 0.5)
        bb = 0.6 if p["bb"] is None else (1.0 if p["bb"] <= 1 else 0.7 if p["bb"] <= 3 else 0.4 if p["bb"] <= 6 else 0.15)
        mono = MONO.get(c["mono"], 0.5) if c else 0.5
        sat = SAT.get(c["sat"], 0.5) if c else 0.5
        comp = 0.35 * cl + 0.3 * bb + 0.2 * mono + 0.15 * sat
        t12 = c["t12"] if c and c.get("t12") is not None else 0.0
        gg = c["gG"] if c and c.get("gG") is not None else 0.0
        opp = OPP.get(c["opp"], 0.5) if c else 0.5
        growth = 0.5 * clamp((t12 + 0.05) / 0.30) + 0.3 * clamp((gg + 0.2) / 0.6) + 0.2 * opp
        d = p["d"] if p["d"] is not None else 999
        nov = 1.0 if d <= 30 else 0.85 if d <= 60 else 0.7 if d <= 90 else 0.4 if d <= 180 else 0.15 if d <= 365 else 0.05
        dp = self.pct(p["w"])
        novs = nov * (0.5 + 0.5 * dp)
        sc = 100 * (W["demand"] * dp + W["competition"] * comp + W["growth"] * growth + W["novelty"] * novs)
        if (p["rr"] or 5) < 3.5 and (p["rc"] or 0) > 50:
            sc *= 0.85
        if p["w"] <= 0:
            sc = 0.0
        p["score"] = round(sc, 1)
        p["_dp"], p["_comp"], p["_growth"], p["_nov"] = round(dp, 3), round(comp, 3), round(growth, 3), round(novs, 3)
        p["cat"] = c["id"] if c else None
        p["flags"] = {"vol": dp >= 0.8, "comp": comp >= 0.8,
                      "grow": (t12 >= 0.08 or gg >= 0.15) and (not c or c.get("opp") != "low"), "new": d <= 90}


def score_category(c: dict) -> None:
    t = clamp(((c.get("t12") or 0) + 0.05) / 0.30)
    g = clamp(((c.get("gG") or 0) + 0.2) / 0.6)
    opp, mono, sat = OPP.get(c.get("opp"), 0.3), MONO.get(c.get("mono"), 0.5), SAT.get(c.get("sat"), 0.5)
    size = clamp(math.log10(max(c.get("gmv") or 1, 1) / 1e5) / 2.5)
    c["cs"] = round(100 * (0.3 * opp + 0.2 * mono + 0.1 * sat + 0.2 * t + 0.1 * g + 0.1 * size))


def score_import(j: dict) -> None:
    mg = clamp((j.get("mg") or 0) / 0.8)
    mo = clamp(math.log10(max(j.get("mo") or 1, 1) / 20) / 2)
    sc = clamp(((j.get("sc") or 0.7) - 0.85) / 0.15)
    j["is"] = round(100 * (0.4 * mg + 0.35 * mo + 0.25 * sc))


def rank(products: list[dict]) -> list[dict]:
    """Ordena por score (desempate: vendas/semana) e numera. Produtos sem venda ficam sem posição."""
    live = [p for p in products if p["w"] > 0]
    live.sort(key=lambda p: (-p["score"], -p["w"]))
    for i, p in enumerate(live, 1):
        p["rank"] = i
    for p in products:
        if p["w"] <= 0:
            p["rank"] = None
    return live
