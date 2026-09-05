"""Servidor MCP falso que imita a JoomPulse (mesmos nomes de ferramenta, mesmo formato colunar).

Uso: python tests/mock_server.py [porta]   (ou importado pelos testes)
"""
from __future__ import annotations

import json
import sys

from mcp.server.fastmcp import FastMCP

FIX = {
    "MercadoProductsWeekly": {
        "columns": ["id", "productId", "userProductId", "catalogProduct", "productName", "productImage", "merchantName",
                    "brand", "categoryId", "merchantCategoryIdL2", "merchantCategoryL1", "merchantCategoryL2",
                    "merchantCategoryL3", "sellerMedal", "sellerReputation", "isFull", "isFreeShipping", "listingType",
                    "l2CompetitivenessLevel", "priceAmount", "orderCount1w", "orderCount1m", "orderGmv1m", "reviewsCount",
                    "reviewsRating", "daysInAd", "numBuyBoxSellers"],
        "data": [["MLB1", "MLB-1", "MLBU1", False, "Chaleira Elétrica 1.8L", "https://img/1.webp", "LOJA A", "GEN", "MLB9",
                  "MLB8", "Casa, Móveis e Decoração", "Cozinha", "Chaleiras", "platinum", "5_green", True, True,
                  "gold_special", "low", 59.9, 1200, 5100, 305490.0, 340, 4.7, 40, 1],
                 ["MLB2", "MLB77", None, True, "Fone Bluetooth X", "https://img/2.webp", "LOJA B", "XYZ", "MLB10",
                  "MLB11", "Eletrônicos, Áudio e Vídeo", "Áudio", "Fones", None, "4_light_green", None, True,
                  "gold_pro", "high", 129.0, 400, 1700, 219300.0, 12, 4.1, 400, 7]],
    },
    "MlbCategoriesMonthly": {
        "columns": ["categoryId", "categoryName", "level", "parentId", "merchantCategoryL1", "merchantCategoryL2",
                    "merchantCategoryL3", "opportunityLevel", "monopolisationFilter", "saturationFilter",
                    "revenueGrowthFilter", "revenuePerSellerFilter", "seasonality", "seasonalityHighMonth", "date",
                    "orderCount", "orderGmv", "orderGmvGrowth1m", "orderCountGrowth1m", "currentTrend12m",
                    "currentTrend24m", "monopolisation", "numSellers", "numSellersWithSales", "revenuePerSeller1m",
                    "averageTicket", "numProducts", "numProductsWithSales"],
        "data": [["MLB8", "Cozinha", 2, "MLB1", "Casa, Móveis e Decoração", "Cozinha", None, "high", "low", "medium",
                  "medium", "high", "non_seasonal", "[]", "2026-08-01T00:00:00.000", 500000, 40000000.0, 0.05, 0.02,
                  0.12, 0.08, 0.04, 20000, 6000, 2000.0, 80.0, 1000000, 90000]],
    },
    "JprProductsMeli": {
        "columns": ["joomproProductId", "title", "imageUrl", "qualityScore", "l1CategoryName", "categoryName", "productId",
                    "meliTitle", "meliL1CategoryName", "meliCategoryName", "catalogProduct", "score", "meliCatalogOrders1m",
                    "joomproPriceAmount", "minAvailableMoq", "smallBatchAvailable", "smallBatchMoq", "meliPriceMin",
                    "meliPriceMax", "meliNumListings", "profit", "marginality", "volumetricEfficient", "boxQty",
                    "joomproUrl", "meliUrl", "pulseUrl", "asOfDate"],
        "data": [["abc123", "Electric Kettle 1.8L", "https://img/j.webp", 0.9, "Home & Kitchen", "Kettles", "MLB-1",
                  "Chaleira Elétrica 1.8L", "Casa, Móveis e Decoração", "Chaleiras", False, 0.93, 5100, 22.0, 50, True, 50,
                  59.9, 59.9, 1, 37.9, 0.63, True, 12, "https://joompro/abc", "https://ml/1", "https://pulse/1",
                  "2026-09-05T00:00:00.000"]],
    },
}

mcp = FastMCP("joompulse-mock", host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8931,
              stateless_http=True, json_response=True)


def _answer(query: str) -> str:
    q = json.loads(query)
    member = (q.get("dimensions") or q.get("measures"))[0]
    cube = member.split(".")[0]
    resp = FIX[cube]
    limit = q.get("limit") or 100
    offset = q.get("offset") or 0
    data = resp["data"][offset:offset + limit]
    return json.dumps({"columns": resp["columns"], "data": data, "totalRows": len(data)})


@mcp.tool()
def query_cubejs_meli(query: str) -> str:
    """mock"""
    return _answer(query)


@mcp.tool()
def query_cubejs_joompro(query: str) -> str:
    """mock"""
    return _answer(query)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
