"""Gera docs/data.json — o arquivo que a página lê."""
from __future__ import annotations

import json
from pathlib import Path

from . import config
from .db import DB, now_iso


def export_json(db: DB, out: Path = config.DOCS_DIR / "data.json") -> Path:
    run_id = db.last_ok_run()
    prev_run = db.last_ok_run(before=run_id) if run_id else None
    products: list[dict] = []
    for r in db.all_products():
        if r["status"] not in ("active", "watching", "candidate"):
            continue
        cur = db.conn.execute("SELECT * FROM product_runs WHERE key=? AND run_id=?", (r["key"], run_id)).fetchone()
        if not cur or cur["rank"] is None:
            continue
        hist = db.history(r["key"], 14)
        products.append({
            "key": r["key"], "i": r["id"], "p": r["product_id"], "u": r["user_product_id"], "c": bool(r["catalog"]),
            "n": r["name"], "img": r["image"], "s": r["seller"], "b": r["brand"], "cid": r["category_id"], "l2id": r["l2_id"],
            "l1": r["l1"], "l2": r["l2"], "l3": r["l3"], "md": r["medal"], "rep": r["reputation"],
            "full": bool(r["is_full"]), "fs": bool(r["free_ship"]), "lt": r["listing_type"], "cl": r["comp_level"],
            "pr": cur["price"], "w": cur["w"], "m": cur["m"], "g": cur["gmv"], "rc": cur["reviews"], "rr": cur["rating"],
            "d": cur["days"], "bb": cur["bb"],
            "score": cur["score"], "sd": cur["s_demand"], "sc": cur["s_comp"], "sg": cur["s_growth"], "sn": cur["s_nov"],
            "rank": cur["rank"], "prev": db.rank_in_run(r["key"], prev_run), "best": r["best_rank"],
            "status": r["status"], "first": r["first_seen_at"], "runs": r["runs_seen"],
            "hist": [[h["started_at"], h["rank"], h["w"], h["price"]] for h in reversed(hist)],
        })
    products.sort(key=lambda p: p["rank"])
    cats = db.categories()
    jp = db.joompro()
    run = db.conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone() if run_id else None
    data = {
        "meta": {
            "generatedAt": run["finished_at"] if run else now_iso(), "runId": run_id,
            "catMonth": cats[0]["month"] if cats else None,
            "joomproAsOf": jp[0].get("asOf") if jp else None,
            "counts": {"products": len(products), "categories": len(cats), "joompro": len(jp),
                       "active": sum(1 for p in products if p["status"] == "active"),
                       "new_this_run": sum(1 for p in products if p["runs"] == 1)},
            "weights": config.WEIGHTS, "topN": config.TOP_N,
        },
        "products": products, "categories": cats, "joompro": jp,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    tmp.replace(out)
    return out
