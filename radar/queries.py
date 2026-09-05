"""Construtores das consultas CubeJS (fonte única das colunas usadas)."""
from __future__ import annotations

from . import config

P = "MercadoProductsWeekly"
PI = "MlbProductsSortedByItemId"
C = "MlbCategoriesMonthly"
J = "JprProductsMeli"

PRODUCT_DIMS = ["id", "productId", "userProductId", "catalogProduct", "productName", "productImage",
                "merchantName", "brand", "categoryId", "merchantCategoryIdL2", "merchantCategoryL1",
                "merchantCategoryL2", "merchantCategoryL3", "sellerMedal", "sellerReputation", "isFull",
                "isFreeShipping", "listingType", "l2CompetitivenessLevel"]
PRODUCT_MEASURES = ["priceAmount", "orderCount1w", "orderCount1m", "orderGmv1m", "reviewsCount",
                    "reviewsRating", "daysInAd", "numBuyBoxSellers"]

CATEGORY_DIMS = ["categoryId", "categoryName", "level", "parentId", "merchantCategoryL1", "merchantCategoryL2",
                 "merchantCategoryL3", "opportunityLevel", "monopolisationFilter", "saturationFilter",
                 "revenueGrowthFilter", "revenuePerSellerFilter", "seasonality", "seasonalityHighMonth", "date"]
CATEGORY_MEASURES = ["orderCount", "orderGmv", "orderGmvGrowth1m", "orderCountGrowth1m", "currentTrend12m",
                     "currentTrend24m", "monopolisation", "numSellers", "numSellersWithSales", "revenuePerSeller1m",
                     "averageTicket", "numProducts", "numProductsWithSales"]

JOOMPRO_DIMS = ["joomproProductId", "title", "imageUrl", "qualityScore", "l1CategoryName", "categoryName",
                "productId", "meliTitle", "meliL1CategoryName", "meliCategoryName", "catalogProduct", "score",
                "meliCatalogOrders1m", "joomproPriceAmount", "minAvailableMoq", "smallBatchAvailable",
                "smallBatchMoq", "meliPriceMin", "meliPriceMax", "meliNumListings", "profit", "marginality",
                "volumetricEfficient", "boxQty", "joomproUrl", "meliUrl", "pulseUrl", "asOfDate"]


def _q(cube: str, names: list[str]) -> list[str]:
    return [f"{cube}.{n}" for n in names]


def _f(cube: str, member: str, op: str, values: list) -> dict:
    return {"member": f"{cube}.{member}", "operator": op, "values": [str(v) for v in values]}


def products_top(l1: str, limit: int = config.DISCOVERY_MAIN_LIMIT) -> dict:
    return {
        "dimensions": _q(P, PRODUCT_DIMS), "measures": _q(P, PRODUCT_MEASURES),
        "filters": [_f(P, "listingStatus", "equals", ["active"]), _f(P, "merchantCategoryL1", "equals", [l1]),
                    _f(P, "orderCount1w", "gt", [0])],
        "order": [[f"{P}.orderCount1w", "desc"]], "limit": limit,
    }


def products_new(l1: str, limit: int = config.DISCOVERY_NEW_LIMIT) -> dict:
    q = products_top(l1, limit)
    q["filters"].append(_f(P, "daysInAd", "lte", [config.NEW_LISTING_MAX_DAYS]))
    return q


def products_by_ids(ids: list[str]) -> dict:
    """Acompanhamento: relê anúncios já conhecidos pelo id (cubo clusterizado por id)."""
    return {
        "dimensions": _q(PI, PRODUCT_DIMS), "measures": _q(PI, PRODUCT_MEASURES),
        "filters": [_f(PI, "id", "equals", ids)], "limit": 100,
    }


def categories(level: int) -> dict:
    return {
        "dimensions": _q(C, CATEGORY_DIMS), "measures": _q(C, CATEGORY_MEASURES),
        "filters": [_f(C, "isCurrent", "equals", ["true"]), _f(C, "level", "equals", [level]),
                    _f(C, "orderCount", "gt", [0])],
        "order": [[f"{C}.orderGmv", "desc"]],
    }


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
