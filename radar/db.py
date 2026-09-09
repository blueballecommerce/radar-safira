"""Banco local (SQLite) com o histórico do radar."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL DEFAULT 'running',
  products_seen INTEGER DEFAULT 0, queries INTEGER DEFAULT 0, notes TEXT
);
CREATE TABLE IF NOT EXISTS products (
  key TEXT PRIMARY KEY,
  id TEXT, product_id TEXT, user_product_id TEXT, catalog INTEGER,
  name TEXT, image TEXT, seller TEXT, brand TEXT,
  category_id TEXT, l2_id TEXT, l1 TEXT, l2 TEXT, l3 TEXT,
  medal TEXT, reputation TEXT, is_full INTEGER, free_ship INTEGER, listing_type TEXT, comp_level TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  first_seen_run INTEGER, last_seen_run INTEGER, first_seen_at TEXT, last_seen_at TEXT,
  best_rank INTEGER, runs_seen INTEGER DEFAULT 0, zero_sales_runs INTEGER DEFAULT 0,
  out_of_top_runs INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_products_id ON products(id);
CREATE TABLE IF NOT EXISTS product_runs (
  run_id INTEGER NOT NULL, key TEXT NOT NULL,
  rank INTEGER, score REAL, s_demand REAL, s_comp REAL, s_growth REAL, s_nov REAL,
  price REAL, w INTEGER, m INTEGER, gmv REAL, reviews INTEGER, rating REAL, days INTEGER, bb INTEGER,
  rivals TEXT,                       -- JSON: outros anúncios do mesmo catálogo nesta rodada
  PRIMARY KEY (run_id, key)
);
CREATE INDEX IF NOT EXISTS ix_pr_key ON product_runs(key, run_id);
CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, month TEXT, run_id INTEGER, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS joompro (id TEXT PRIMARY KEY, run_id INTEGER, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path = config.DB_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # bancos criados antes destas colunas continuam funcionando
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(product_runs)")}
        if "rivals" not in cols:
            self.conn.execute("ALTER TABLE product_runs ADD COLUMN rivals TEXT")
        pcols = {r[1] for r in self.conn.execute("PRAGMA table_info(products)")}
        if "published" not in pcols:
            # data de criação do anúncio no ML (vem do MCP; a coleta pelo site não informa)
            self.conn.execute("ALTER TABLE products ADD COLUMN published TEXT")

    # --- meta ---
    def get_meta(self, k: str, default=None):
        r = self.conn.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default

    def set_meta(self, k: str, v) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, json.dumps(v)))

    # --- runs ---
    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO runs(started_at) VALUES(?)", (now_iso(),))
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, status: str, products_seen: int, queries: int, notes: str = "") -> None:
        self.conn.execute("UPDATE runs SET finished_at=?, status=?, products_seen=?, queries=?, notes=? WHERE id=?",
                          (now_iso(), status, products_seen, queries, notes, run_id))
        self.conn.commit()

    def last_ok_run(self, before: int | None = None) -> int | None:
        q = "SELECT id FROM runs WHERE status='ok'" + (" AND id<?" if before else "") + " ORDER BY id DESC LIMIT 1"
        r = self.conn.execute(q, (before,) if before else ()).fetchone()
        return r["id"] if r else None

    # --- products ---
    def tracked_ids(self) -> list[str]:
        """ids (anúncio) dos produtos ativos ou em observação — releitura a cada rodada."""
        return [r["id"] for r in self.conn.execute(
            "SELECT id FROM products WHERE status IN ('active','watching') AND id IS NOT NULL")]

    def product(self, key: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM products WHERE key=?", (key,)).fetchone()

    def products_by_listing(self, listing_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM products WHERE id=?", (listing_id,)).fetchall()

    def all_products(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM products").fetchall()

    def rekey(self, old_key: str, new_key: str) -> None:
        """Troca a chave de um produto sem perder o histórico.

        A coleta pelo site inventava a chave (`cat:<hash>` da foto+título, ou o id do
        anúncio); a coleta pelo MCP usa o `productId` real do Mercado Livre. Quando o
        mesmo anúncio volta com a chave nova, o histórico (posições, rodadas, melhor
        posição) passa para ela. Se a chave nova já existe, os dois registros são
        fundidos: fica o mais antigo como primeira aparição e a melhor posição das duas.
        """
        if old_key == new_key:
            return
        old = self.product(old_key)
        if old is None:
            return
        new = self.product(new_key)
        if new is None:
            self.conn.execute("UPDATE products SET key=? WHERE key=?", (new_key, old_key))
            self.conn.execute("UPDATE product_runs SET key=? WHERE key=?", (new_key, old_key))
            return
        first_run = min(x for x in (old["first_seen_run"], new["first_seen_run"]) if x is not None) \
            if (old["first_seen_run"] is not None or new["first_seen_run"] is not None) else None
        first_at = min(x for x in (old["first_seen_at"], new["first_seen_at"]) if x) \
            if (old["first_seen_at"] or new["first_seen_at"]) else None
        best = min((x for x in (old["best_rank"], new["best_rank"]) if x is not None), default=None)
        # rodadas em que só o registro antigo apareceu passam para o novo; onde os dois
        # apareceram (mesma rodada), fica a linha do novo
        self.conn.execute("UPDATE OR IGNORE product_runs SET key=? WHERE key=?", (new_key, old_key))
        self.conn.execute("DELETE FROM product_runs WHERE key=?", (old_key,))
        runs_seen = self.conn.execute("SELECT COUNT(*) FROM product_runs WHERE key=?", (new_key,)).fetchone()[0]
        self.conn.execute("UPDATE products SET first_seen_run=?, first_seen_at=?, best_rank=?, runs_seen=? WHERE key=?",
                          (first_run, first_at, best, max(runs_seen, new["runs_seen"] or 0), new_key))
        self.conn.execute("DELETE FROM products WHERE key=?", (old_key,))

    def upsert_product(self, p: dict, run_id: int, rank: int | None, status: str) -> None:
        old = self.product(p["key"])
        ts = now_iso()
        best = min([x for x in [old["best_rank"] if old else None, rank] if x is not None], default=None)
        runs_seen = (old["runs_seen"] if old else 0) + 1
        zero = 0 if (p.get("w") or 0) > 0 else ((old["zero_sales_runs"] if old else 0) + 1)
        oot = 0 if status == "active" else ((old["out_of_top_runs"] if old else 0) + 1)
        # os campos descritivos só mudam quando a leitura trouxe valor: uma releitura mais
        # magra (ou uma coluna que sumiu do cubo) não apaga nome, foto ou categoria
        self.conn.execute("""
        INSERT INTO products(key,id,product_id,user_product_id,catalog,name,image,seller,brand,category_id,l2_id,l1,l2,l3,
          medal,reputation,is_full,free_ship,listing_type,comp_level,status,first_seen_run,last_seen_run,first_seen_at,last_seen_at,
          best_rank,runs_seen,zero_sales_runs,out_of_top_runs,published)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(key) DO UPDATE SET id=excluded.id, product_id=excluded.product_id,
          user_product_id=COALESCE(excluded.user_product_id, products.user_product_id),
          catalog=excluded.catalog, name=COALESCE(excluded.name, products.name), image=COALESCE(excluded.image, products.image),
          seller=COALESCE(excluded.seller, products.seller), brand=COALESCE(excluded.brand, products.brand),
          category_id=COALESCE(excluded.category_id, products.category_id), l2_id=COALESCE(excluded.l2_id, products.l2_id),
          l1=COALESCE(excluded.l1, products.l1), l2=COALESCE(excluded.l2, products.l2), l3=COALESCE(excluded.l3, products.l3),
          medal=COALESCE(excluded.medal, products.medal), reputation=COALESCE(excluded.reputation, products.reputation),
          is_full=excluded.is_full, free_ship=excluded.free_ship,
          listing_type=COALESCE(excluded.listing_type, products.listing_type),
          comp_level=COALESCE(excluded.comp_level, products.comp_level), status=excluded.status,
          last_seen_run=excluded.last_seen_run, last_seen_at=excluded.last_seen_at, best_rank=excluded.best_rank,
          runs_seen=excluded.runs_seen, zero_sales_runs=excluded.zero_sales_runs, out_of_top_runs=excluded.out_of_top_runs,
          published=COALESCE(excluded.published, products.published)
        """, (p["key"], p["i"], p["p"], p["u"], int(bool(p["c"])), p["n"], p["img"], p["s"], p["b"], p["cid"], p["l2id"],
              p["l1"], p["l2"], p["l3"], p["md"], p["rep"], int(bool(p["full"])), int(bool(p["fs"])), p["lt"], p["cl"],
              status, old["first_seen_run"] if old else run_id, run_id, old["first_seen_at"] if old else ts, ts,
              best, runs_seen, zero, oot, p.get("pub")))
        riv = p.get("riv") or []
        self.conn.execute("""INSERT OR REPLACE INTO product_runs(run_id,key,rank,score,s_demand,s_comp,s_growth,s_nov,
            price,w,m,gmv,reviews,rating,days,bb,rivals) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, p["key"], rank, p.get("score"), p.get("_dp"), p.get("_comp"), p.get("_growth"), p.get("_nov"),
             p.get("pr"), p.get("w"), p.get("m"), p.get("g"), p.get("rc"), p.get("rr"), p.get("d"), p.get("bb"),
             json.dumps(riv, ensure_ascii=False) if riv else None))

    def mark_missing(self, keys_seen: set[str], run_id: int) -> int:
        """Produtos rastreados que não voltaram nesta rodada (anúncio pausado/removido)."""
        n = 0
        for r in self.conn.execute("SELECT key FROM products WHERE status IN ('active','watching')").fetchall():
            if r["key"] not in keys_seen:
                self.conn.execute("UPDATE products SET status='dropped', out_of_top_runs=out_of_top_runs+1 WHERE key=?", (r["key"],))
                n += 1
        return n

    def history(self, key: str, n: int = 12) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT pr.run_id, pr.rank, pr.score, pr.w, pr.price, r.started_at FROM product_runs pr JOIN runs r ON r.id=pr.run_id "
            "WHERE pr.key=? AND r.status='ok' ORDER BY pr.run_id DESC LIMIT ?", (key, n)).fetchall()

    def rank_in_run(self, key: str, run_id: int | None) -> int | None:
        if run_id is None:
            return None
        r = self.conn.execute("SELECT rank FROM product_runs WHERE key=? AND run_id=?", (key, run_id)).fetchone()
        return r["rank"] if r else None

    # --- categories / joompro ---
    def replace_categories(self, rows: list[dict], month: str, run_id: int) -> None:
        self.conn.execute("DELETE FROM categories")
        self.conn.executemany("INSERT OR REPLACE INTO categories(id,month,run_id,json) VALUES(?,?,?,?)",
                              [(c["id"], month, run_id, json.dumps(c, ensure_ascii=False)) for c in rows])

    def categories(self) -> list[dict]:
        return [json.loads(r["json"]) for r in self.conn.execute("SELECT json FROM categories")]

    def replace_joompro(self, rows: list[dict], run_id: int) -> None:
        self.conn.execute("DELETE FROM joompro")
        self.conn.executemany("INSERT OR REPLACE INTO joompro(id,run_id,json) VALUES(?,?,?)",
                              [(j["id"], run_id, json.dumps(j, ensure_ascii=False)) for j in rows])

    def joompro(self) -> list[dict]:
        return [json.loads(r["json"]) for r in self.conn.execute("SELECT json FROM joompro")]

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
