"""Uma rodada completa do radar: coleta → ranking → histórico → export."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

from . import config, engine, queries
from .db import DB, now_iso
from .export import export_json

log = logging.getLogger("radar.run")


def slug(l1: str) -> str:
    s = unicodedata.normalize("NFKD", l1).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(e|para|de)\b", " ", s)  # "Joias e Relógios" -> joias_relogios
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


class Source:
    """Interface mínima de coleta — implementada pela JoomPulse (MCP) ou por fixtures locais."""

    async def products_top(self, l1: str) -> list[dict]: ...
    async def products_new(self, l1: str) -> list[dict]: ...
    async def products_by_ids(self, ids: list[str]) -> list[dict]: ...
    async def categories(self, level: int) -> list[dict]: ...
    async def joompro(self) -> list[dict]: ...
    calls: int = 0


class PulseSource(Source):
    def __init__(self, pulse):
        self.pulse = pulse

    @property
    def calls(self):
        return self.pulse.calls

    async def products_top(self, l1):
        return await self.pulse.meli(queries.products_top(l1))

    async def products_new(self, l1):
        return await self.pulse.meli(queries.products_new(l1))

    async def products_by_ids(self, ids):
        return await self.pulse.meli(queries.products_by_ids(ids))

    async def categories(self, level):
        pages = 6 if level == 2 else config.CATEGORY_L3_MAX_PAGES
        return await self.pulse.paged(config.TOOL_MELI, queries.categories(level), pages)

    async def joompro(self):
        return await self.pulse.paged(config.TOOL_JOOMPRO, queries.joompro_pairs(), config.JOOMPRO_PAGES)


class FixtureSource(Source):
    """Lê os JSONs normalizados (tests/fixtures) — para testes e para popular o banco sem rede."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.calls = 0
        self._track: dict[str, dict] | None = None

    def _load(self, name: str) -> list[dict]:
        p = self.folder / name
        self.calls += 1
        return json.loads(p.read_text("utf-8")) if p.exists() else []

    # slugs usados nos fixtures de hoje
    SLUGS = {"Acessórios para Veículos": "acessorios_veiculos", "Casa, Móveis e Decoração": "casa_moveis_decoracao",
             "Calçados, Roupas e Bolsas": "calcados_roupas_bolsas", "Esportes e Fitness": "esportes_fitness",
             "Arte, Papelaria e Armarinho": "arte_papelaria", "Beleza e Cuidado Pessoal": "beleza_cuidado",
             "Festas e Lembrancinhas": "festas_lembrancinhas", "Livros, Revistas e Comics": "livros_revistas",
             "Eletrônicos, Áudio e Vídeo": "eletronicos_audio_video", "Música, Filmes e Seriados": "musica_filmes",
             "Câmeras e Acessórios": "cameras_acessorios"}

    def _slug(self, l1):
        return self.SLUGS.get(l1, slug(l1))

    async def products_top(self, l1):
        return self._load(f"ml_main_{self._slug(l1)}.json")

    async def products_new(self, l1):
        return self._load(f"ml_new_{self._slug(l1)}.json")

    async def products_by_ids(self, ids):
        # a releitura por id vem de ml_track.json (a coleta pelo MCP grava lá os lotes
        # de acompanhamento); fixtures de teste não têm o arquivo e devolvem vazio
        if self._track is None:
            self._track = {r["id"]: r for r in self._load("ml_track.json") if r.get("id")}
        return [self._track[i] for i in ids if i in self._track]

    async def categories(self, level):
        return self._load(f"cat_l{level}.json")

    async def joompro(self):
        return self._load("joompro.json")


async def _categories_if_needed(src: Source, db: DB, run_id: int, force: bool) -> str | None:
    have = db.categories()
    month = have[0].get("month") if have else None
    if have and not force and month == date.today().strftime("%Y-%m"):
        return month
    rows2 = await src.categories(2)
    if not rows2:
        return month
    rows3 = await src.categories(3)
    cats = [engine.category_from_row(r) for r in rows2 + rows3]
    for c in cats:
        engine.score_category(c)
    db.replace_categories(cats, cats[0]["month"], run_id)
    return cats[0]["month"]


async def _joompro_if_needed(src: Source, db: DB, run_id: int, force: bool) -> None:
    last = db.get_meta("joompro_date")
    if last == date.today().isoformat() and not force and db.joompro():
        return
    rows = await src.joompro()
    if not rows:
        return
    jp = [engine.joompro_from_row(r) for r in rows]
    for j in jp:
        engine.score_import(j)
    db.replace_joompro(jp, run_id)
    db.set_meta("joompro_date", date.today().isoformat())


def _rekey_known(db: DB, raw: list[dict]) -> int:
    """Liga cada anúncio já conhecido à chave nova quando a fonte mudou.

    A coleta pelo site guardava o produto por uma chave inventada (`cat:<hash>` ou o id
    do anúncio); o MCP traz o `productId` real. Sem esta ponte, o mesmo produto viraria
    um registro novo ("entrou agora") e o antigo sumiria com o histórico junto.
    """
    n = 0
    for p in raw:
        for old in db.products_by_listing(p["i"]):
            if old["key"] != p["key"] and old["status"] != "dropped":
                db.rekey(old["key"], p["key"])
                n += 1
    return n


async def run_once(src: Source, db: DB, *, force_categories: bool = False, force_joompro: bool = False,
                   l1s: list[str] | None = None, discover: bool = True) -> dict:
    """Uma rodada. `discover=False` pula a descoberta e só relê o que já está no radar
    (a rodada das 15h): tudo é pontuado e reordenado de novo com os números do dia."""
    run_id = db.start_run()
    try:
        month = await _categories_if_needed(src, db, run_id, force_categories)
        await _joompro_if_needed(src, db, run_id, force_joompro)

        raw: list[dict] = []
        if discover:
            for l1 in (l1s or config.L1_CATEGORIES):
                for kind, rows in (("main", await src.products_top(l1)), ("new", await src.products_new(l1))):
                    raw.extend(p for p in (engine.product_from_row(r, kind) for r in rows) if p)
                log.info("%s: %d linhas acumuladas", l1, len(raw))

        discovered_ids = {p["i"] for p in raw}
        to_track = [i for i in db.tracked_ids() if i not in discovered_ids]
        for k in range(0, len(to_track), config.TRACK_BATCH):
            rows = await src.products_by_ids(to_track[k:k + config.TRACK_BATCH])
            raw.extend(p for p in (engine.product_from_row(r, "track") for r in rows) if p)
        log.info("acompanhamento: %d ids relidos", len(to_track))

        rekeyed = _rekey_known(db, raw)
        if rekeyed:
            log.info("chaves migradas para o productId real: %d", rekeyed)

        products = engine.dedupe(raw)
        cats = db.categories()
        scorer = engine.Scorer(products, cats)
        for p in products:
            scorer.score(p)
        live = engine.rank(products)

        seen: set[str] = set()
        for p in products:
            old = db.product(p["key"])
            if p["rank"] is not None and p["rank"] <= config.TOP_N:
                status = "active"
            elif p["w"] > 0 and old and old["status"] in ("active", "watching") and old["out_of_top_runs"] < config.WATCH_RUNS:
                status = "watching"
            elif p["w"] > 0:
                status = "candidate"
            else:
                status = "dropped" if (old and old["zero_sales_runs"] + 1 >= config.DROP_AFTER_ZERO_SALES_RUNS) else "watching"
            db.upsert_product(p, run_id, p["rank"], status)
            seen.add(p["key"])
        missing = db.mark_missing(seen, run_id)

        db.finish_run(run_id, "ok", len(products), src.calls,
                      f"tracked={len(to_track)} missing={missing} month={month} rekeyed={rekeyed} discover={int(discover)}")
        db.commit()
        out = export_json(db)
        return {"run_id": run_id, "products": len(products), "ranked": len(live), "queries": src.calls,
                "tracked": len(to_track), "missing": missing, "rekeyed": rekeyed, "month": month, "export": str(out)}
    except Exception as e:
        db.conn.rollback()
        db.finish_run(run_id, "error", 0, src.calls, repr(e)[:500])
        raise
