"""Construtores das consultas CubeJS (fonte única das colunas usadas).

Dois conjuntos de colunas:

* ``PRODUCT_DIMS`` / ``PRODUCT_MEASURES`` — o mínimo que o motor (`engine.product_from_row`)
  lê. É o que o cliente MCP próprio (`pulse.py`, caminho hoje recusado pela JoomPulse) pede.
* ``PRODUCT_DIMS_MCP`` / ``PRODUCT_MEASURES_MCP`` — o conjunto usado quando **o Claude** faz a
  consulta pelo conector MCP (ver `radar/mcp.py`). O tamanho da resposta é calculado: acima de
  ``MAX_MCP_OUTPUT_TOKENS`` (12.000 tokens ≈ 37 KB, definido em ~/.claude/settings.json) o
  Claude Code não põe o resultado no contexto — grava num arquivo e mostra só o caminho —, e
  acima de ~80 KB a própria JoomPulse recusa a consulta ("result is too large"). Com 100 linhas
  de ~600 bytes a resposta fica em ~60 KB, no meio da faixa. É isso que deixa a rotina diária
  barata em tokens: o dado vai do arquivo para o banco por script, sem passar pelo modelo. As
  colunas extras (buy box, loja, data de criação) enchem a linha e ainda servem à ficha.
"""
from __future__ import annotations

from . import config

P = "MercadoProductsWeekly"
PI = "MlbProductsSortedByItemId"
C = "MlbCategoriesMonthly"
J = "JprProductsMeli"

# ``l2CompetitivenessLevel`` saiu do cubo em set/2026 ("not found for path"); o motor trata
# a ausência como neutro (0,5). Fica fora das consultas para não derrubar a chamada inteira.
PRODUCT_DIMS = ["id", "productId", "userProductId", "catalogProduct", "productName", "productImage",
                "merchantName", "brand", "categoryId", "merchantCategoryIdL2", "merchantCategoryL1",
                "merchantCategoryL2", "merchantCategoryL3", "sellerMedal", "sellerReputation", "isFull",
                "isFreeShipping", "listingType"]
PRODUCT_MEASURES = ["priceAmount", "orderCount1w", "orderCount1m", "orderGmv1m", "reviewsCount",
                    "reviewsRating", "daysInAd", "numBuyBoxSellers"]

# conjunto do MCP (ver docstring): ~600 bytes por linha. Primeiro o que o motor lê, depois o resto.
PRODUCT_DIMS_MCP = PRODUCT_DIMS + [
    "adPublishDate", "buyBoxWiner", "shopId", "merchantUrl", "officialStore", "bestsellersInfo",
]
PRODUCT_MEASURES_MCP = PRODUCT_MEASURES + [
    "catalogOrderCount1w", "catalogOrderCount1m", "sold", "buyBoxShopName", "buyBoxPriceAmount",
    "buyBoxSellerMedal", "shopSales1m", "shopListingsCount", "shopSales365Days",
]

CATEGORY_DIMS = ["categoryId", "categoryName", "level", "parentId", "merchantCategoryL1", "merchantCategoryL2",
                 "merchantCategoryL3", "opportunityLevel", "monopolisationFilter", "saturationFilter",
                 "revenueGrowthFilter", "revenuePerSellerFilter", "seasonality", "seasonalityHighMonth", "date"]
CATEGORY_MEASURES = ["orderCount", "orderGmv", "orderGmvGrowth1m", "orderCountGrowth1m", "currentTrend12m",
                     "currentTrend24m", "monopolisation", "numSellers", "numSellersWithSales", "revenuePerSeller1m",
                     "averageTicket", "numProducts", "numProductsWithSales"]

# idem para categorias (~550 bytes por linha; só 14 páginas por mês)
CATEGORY_DIMS_MCP = CATEGORY_DIMS + [
    "categoryNameNormalized", "merchantCategoryIdL1", "merchantCategoryIdL2", "merchantCategoryIdL3",
    "monopolisationFilterInt", "saturationFilterInt", "revenuePerSellerInt", "revenueGrowthFilterInt",
    "opportunityLevelInt",
]
CATEGORY_MEASURES_MCP = CATEGORY_MEASURES + [
    "orderCount1m", "orderGmv1m", "numItems", "numItems1m", "numProducts1m", "numProductsWithSales1m",
    "numCatalogProducts", "numCatalogProductsWithSales", "numBrands", "numSellers1m", "sellersGrowth1m",
    "numSellersWithSales1m", "numPlatinumSellers", "numGoldSellers", "numSilverSellers", "numUsualSellers",
    "percentFullItems", "revenuePerSellerGrowth1m", "categoryMaxDepth", "numKeywords",
]

JOOMPRO_DIMS = ["joomproProductId", "title", "imageUrl", "qualityScore", "l1CategoryName", "categoryName",
                "productId", "meliTitle", "meliL1CategoryName", "meliCategoryName", "catalogProduct", "score",
                "meliCatalogOrders1m", "joomproPriceAmount", "minAvailableMoq", "smallBatchAvailable",
                "smallBatchMoq", "meliPriceMin", "meliPriceMax", "meliNumListings", "profit", "marginality",
                "volumetricEfficient", "boxQty", "joomproUrl", "meliUrl", "pulseUrl", "asOfDate"]


def _q(cube: str, names: list[str]) -> list[str]:
    return [f"{cube}.{n}" for n in names]


def _f(cube: str, member: str, op: str, values: list) -> dict:
    return {"member": f"{cube}.{member}", "operator": op, "values": [str(v) for v in values]}


def products_top(l1: str, limit: int = config.DISCOVERY_MAIN_LIMIT, *, fat: bool = False) -> dict:
    dims, meas = (PRODUCT_DIMS_MCP, PRODUCT_MEASURES_MCP) if fat else (PRODUCT_DIMS, PRODUCT_MEASURES)
    return {
        "dimensions": _q(P, dims), "measures": _q(P, meas),
        "filters": [_f(P, "listingStatus", "equals", ["active"]), _f(P, "merchantCategoryL1", "equals", [l1]),
                    _f(P, "orderCount1w", "gt", [0])],
        "order": [[f"{P}.orderCount1w", "desc"]], "limit": limit,
    }


def products_new(l1: str, limit: int = config.DISCOVERY_NEW_LIMIT, *, fat: bool = False,
                 max_days: int = config.NEW_LISTING_MAX_DAYS) -> dict:
    q = products_top(l1, limit, fat=fat)
    q["filters"].append(_f(P, "daysInAd", "lte", [max_days]))
    return q


def products_by_ids(ids: list[str], *, fat: bool = False) -> dict:
    """Acompanhamento: relê anúncios já conhecidos pelo id (cubo clusterizado por id)."""
    dims, meas = (PRODUCT_DIMS_MCP, PRODUCT_MEASURES_MCP) if fat else (PRODUCT_DIMS, PRODUCT_MEASURES)
    return {
        "dimensions": _q(PI, dims), "measures": _q(PI, meas),
        "filters": [_f(PI, "id", "equals", ids)], "limit": 100,
    }


def categories(level: int, *, fat: bool = False, offset: int = 0, limit: int = 100) -> dict:
    dims, meas = (CATEGORY_DIMS_MCP, CATEGORY_MEASURES_MCP) if fat else (CATEGORY_DIMS, CATEGORY_MEASURES)
    q = {
        "dimensions": _q(C, dims), "measures": _q(C, meas),
        "filters": [_f(C, "isCurrent", "equals", ["true"]), _f(C, "level", "equals", [level]),
                    _f(C, "orderCount", "gt", [0])],
        "order": [[f"{C}.orderGmv", "desc"]],
    }
    if fat:
        q["limit"], q["offset"] = limit, offset
    return q


def joompro_pairs() -> dict:
    return {
        "dimensions": _q(J, JOOMPRO_DIMS),
        "filters": [_f(J, "hasMeliMatch", "equals", ["true"]), _f(J, "score", "gte", [config.JOOMPRO_MIN_SCORE]),
                    _f(J, "marginality", "gte", [config.JOOMPRO_MIN_MARGIN]),
                    _f(J, "meliCatalogOrders1m", "gte", [config.JOOMPRO_MIN_ORDERS_1M])],
        "order": [[f"{J}.meliCatalogOrders1m", "desc"]],
    }


def ping() -> dict:
    return {"dimensions": [f"{P}.id"], "filters": [_f(P, "listingStatus", "equals", ["active"])], "limit": 1}
