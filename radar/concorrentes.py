"""Exporta dois concorrentes sem alterar o ranking ou os fornecedores.

Fonte preservada em data/concorrentes; nenhum acesso de rede neste exportador.
A identidade usa o produto do vendedor (MLBU) ou o SKU de catálogo confirmado.
Título parecido nunca é suficiente para eliminar um anúncio.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

# Lojas públicas conferidas no Mercado Livre em 08/09/2026.
VERIFIED_STOREFRONTS = {
    "1806697386": "https://www.mercadolivre.com.br/pagina/comercialbrinkando",
    "2520649184": "https://www.mercadolivre.com.br/pagina/confeccao_aml",
}


def rows(block):
    return [dict(zip(block["columns"], row)) for row in block["data"]]


def ml_url(item_id):
    return "https://produto.mercadolivre.com.br/" + item_id.replace("MLB", "MLB-", 1) + "-_JM"


def option_label(raw):
    return re.sub(r"^Botón \d+ de \d+, (?:Selecionado, )?", "", raw).strip()


def specs_dict(obs):
    result = {}
    for text in obs.get("specs", []):
        parts = text.split("\n", 1)
        if len(parts) == 2:
            result[parts[0].strip()] = parts[1].strip()
    return result


def product_page(obs):
    # ML can redirect inactive listings to a category with its own h1.
    return bool(obs.get("title") and obs.get("specs"))


def option_identity(option, seller, item_id):
    url = option.get("url", "")
    user = re.search(r"/up/(MLBU\d+)", url)
    if user:
        return seller + ":user:" + user[1]
    catalog = re.search(r"/p/(MLB\d+)", url)
    if catalog:
        return seller + ":catalog:" + catalog[1]
    # A legacy listing's options are only provably the same inside that listing.
    return seller + ":option:" + item_id + ":" + option_label(option["label"]).casefold()


def choose_main(refs, listing_map):
    # Stable tie-break. Never add metrics from duplicate/shared listings.
    return max(refs, key=lambda i: (
        listing_map[i].get("orderCount1m") if listing_map[i].get("orderCount1m") is not None else -1,
        listing_map[i].get("sold") if listing_map[i].get("sold") is not None else -1,
        i,
    ))


def build(raw, observations):
    inventory = [row for page in raw["pages"] for row in rows(page)]
    listing_map = {r["id"]: r for r in inventory}
    if len(inventory) != len(listing_map):
        raise ValueError("Páginas com anúncios duplicados: conferir paginação.")
    counts = {str(r["shopId"]): r["numItems"] for r in rows(raw["counts"])}
    profiles = {str(r["shopId"]): r for r in rows(raw["profiles"])}
    seeds = {str(r["shopId"]): r for r in rows(raw["seeds"])}
    # Alias user product to catalogue SKU only for identical catalogue IDs.
    aliases = {}
    for r in inventory:
        if r.get("userProductId") and r.get("catalogProduct") and re.fullmatch(r"MLB\d+", r.get("productId") or ""):
            aliases[r["shopId"] + ":user:" + r["userProductId"]] = r["shopId"] + ":catalog:" + r["productId"]

    groups = {}
    def add(key, row, label, url, shared, proof, attributes, reference_only=False):
        key = aliases.get(key, key)
        g = groups.setdefault(key, {"key": key, "labels": [], "refs": {}, "proof": proof, "attributes": attributes})
        if label and label not in g["labels"]:
            g["labels"].append(label)
        # A direct variant-specific source supersedes a shared reference.
        old = g["refs"].get(row["id"])
        if old is None or (old.get("referenceOnly") and not reference_only) or (old["shared"] and not shared):
            g["refs"][row["id"]] = {"id": row["id"], "url": url, "shared": shared, "referenceOnly": reference_only}
        if attributes and not g["attributes"]:
            g["attributes"] = attributes

    for r in inventory:
        sid, iid = r["shopId"], r["id"]
        obs = observations.get(iid, {})
        attrs = specs_dict(obs)
        opts = obs.get("options", []) if product_page(obs) else []
        actual_user = re.search(r"/up/(MLBU\d+)", obs.get("url", ""))
        own_user = r.get("userProductId") or (actual_user[1] if actual_user else None)
        own_key = sid + ":user:" + own_user if own_user else None
        if not own_key and r.get("catalogProduct") and re.fullmatch(r"MLB\d+", r.get("productId") or ""):
            own_key = sid + ":catalog:" + r["productId"]
        modern = any(re.search(r"/(up|p)/MLB", o.get("url", "")) for o in opts)
        seen = set()
        for opt in opts:
            label = option_label(opt["label"])
            if not label:
                continue
            key = option_identity(opt, sid, iid)
            if key in seen:
                continue
            seen.add(key)
            # Options other than this exact user-product have no separated sales.
            reference_only = modern and aliases.get(key, key) != aliases.get(own_key, own_key)
            shared = not modern and len(opts) > 1
            var_attrs = {k: v for k, v in attrs.items() if k not in ("Cor", "Tamanho", "Nome do desenho")}
            var_attrs["Variação"] = label
            add(key, r, label, opt.get("url") or ml_url(iid), shared, "Variação exibida no Mercado Livre", var_attrs, reference_only)
        # Some source records refer to a variant no longer offered on the page.
        own_key = own_key or (sid + ":catalog:" + r["productId"] if r.get("catalogProduct") and re.fullmatch(r"MLB\d+", r.get("productId") or "") else sid + ":listing:" + iid)
        represented = any(aliases.get(k, k) == aliases.get(own_key, own_key) for k in seen)
        if not opts or (modern and not represented):
            label = " · ".join(attrs[k] for k in ("Cor", "Tamanho") if attrs.get(k))
            proof = "Produto do vendedor identificado" if own_user else ("Mesmo SKU de catálogo" if ":catalog:" in own_key else "Identidade ainda não conferida")
            add(own_key, r, label, obs.get("url") if product_page(obs) else ml_url(iid), False, proof, attrs)

    sellers = []
    for sid, profile in profiles.items():
        records = [r for r in inventory if r["shopId"] == sid]
        if counts.get(sid) != len(records):
            raise ValueError(f"Cobertura incompleta: {sid}, {len(records)}/{counts.get(sid)}")
        products = []
        for key, g in groups.items():
            if not key.startswith(sid + ":"):
                continue
            # A sibling option is navigation evidence, not that sibling's sales.
            valid_refs = {i: ref for i, ref in g["refs"].items() if not ref.get("referenceOnly")}
            used_refs = valid_refs or g["refs"]
            refs = list(used_refs)
            main_id = choose_main(refs, listing_map)
            main = listing_map[main_id]
            pid = hashlib.sha256(key.encode()).hexdigest()[:16]
            direct_ids = [i for i in refs if not used_refs[i]["shared"] and not used_refs[i].get("referenceOnly")]
            products.append({
                "id": pid, "name": main["productName"], "variant": g["labels"][0] if g["labels"] else None,
                "image": main.get("productImage"), "category": main.get("merchantCategoryL2"),
                "brand": main.get("brand"), "identity": g["proof"], "identityKey": key,
                "attributes": g["attributes"], "mainListingId": main_id,
                "variantSales": None, "variantRevenue": None,
                "hasListingMetrics": bool(valid_refs),
                "directListingIds": direct_ids,
                "listings": sorted(used_refs.values(), key=lambda x: (x["id"] != main_id, -(listing_map[x["id"]].get("orderCount1m") or 0))),
            })
        products.sort(key=lambda p: (-(listing_map[p["mainListingId"]].get("orderCount1m") or 0), p["name"], p["variant"] or ""))
        checked = [r["id"] for r in records if product_page(observations.get(r["id"], {}))]
        listing_export = []
        for r in records:
            obs = observations.get(r["id"], {})
            listing_export.append({
                **r, "url": ml_url(r["id"]), "pageChecked": product_page(obs),
                "pageStatus": "checked" if product_page(obs) else ("redirected" if "redirectedFromVip=" in obs.get("url", "") else "unconfirmed"),
                "checkedAt": (obs.get("checkedAt") or raw["collectedAt"]) if product_page(obs) else None,
                "observedTitle": obs.get("title") if product_page(obs) else None, "attributes": specs_dict(obs),
                "optionCount": len(obs.get("options", [])), "firstSaleDate": None,
            })
        sellers.append({
            "id": sid, "name": profile["shopName"], "profile": profile,
            "url": VERIFIED_STOREFRONTS.get(sid, seeds[sid]["merchantUrl"].replace("http:", "https:")),
            "seed": {"id": seeds[sid]["id"], "name": seeds[sid]["productName"], "url": ml_url(seeds[sid]["id"])},
            "coverage": {"sourceListings": counts[sid], "collectedListings": len(records), "pagesChecked": len(checked),
                         "products": len(products), "variantProducts": sum(bool(p["variant"]) for p in products),
                         "completeStore": False},
            "products": products, "listings": listing_export,
        })
    return {
        "schemaVersion": 1, "snapshot": raw["snapshot"], "collectedAt": raw["collectedAt"],
        "source": "JoomPulse · Mercado Livre Brasil", "sellers": sellers,
        "method": {
            "sales": "Vendas e faturamento mensais/semanais são estimativas da JoomPulse, não totais oficiais nem janelas móveis de 7/30 dias.",
            "variants": "Cor, tamanho e quantidade diferentes aparecem separados quando identificados. A fonte não informa vendas por variação; consulte os números do anúncio principal, sem somá-los entre variações.",
            "duplicates": "Anúncios com identidade comprovada são agrupados. O principal é o de maior estimativa mensal de vendas; desempate pelo total público vendido e pelo ID. Título parecido sozinho não elimina anúncios.",
            "coverage": "Todos os anúncios ativos encontrados na base da JoomPulse nesta data foram incluídos. A loja pode ter outros anúncios fora da cobertura; a conferência de variações é parcial.",
            "tenure": "Em catálogo, o tempo no ar pode pertencer ao catálogo compartilhado. Avaliações do produto podem reunir variações e outros anúncios. Não há data confirmada da primeira venda.",
        },
    }


def main():
    base = ROOT / "data/concorrentes"
    raw = json.loads((base / "pesquisa-2026-09-08.json").read_text(encoding="utf-8-sig"))
    obs_path = base / "observacoes-2026-09-08.json"
    observations = json.loads(obs_path.read_text(encoding="utf-8-sig")) if obs_path.exists() else {}
    result = build(raw, observations)
    out = ROOT / "docs/concorrentes.json"
    out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for seller in result["sellers"]:
        print(seller["name"], seller["coverage"])


if __name__ == "__main__":
    main()
