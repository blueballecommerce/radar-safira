"""Testes da rotina pelo MCP: migração de chaves, releitura por id a partir de ml_track.json,
ingestão das respostas colunares e o plano da rodada."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RADAR_ROOT", str(tmp_path))
    for m in list(sys.modules):
        if m.startswith("radar"):
            del sys.modules[m]
    import radar.config as cfg
    assert cfg.ROOT == tmp_path
    return tmp_path


def _row(i: str, pid: str | None, **kw) -> dict:
    r = {"id": i, "productId": pid, "userProductId": None, "catalogProduct": pid is not None and not pid.startswith("MLB-"),
         "productName": kw.get("nome", "Produto " + i), "productImage": "https://img/" + i, "merchantName": "LOJA",
         "brand": None, "categoryId": "MLB9", "merchantCategoryIdL2": "MLB8", "merchantCategoryL1": "Pet Shop",
         "merchantCategoryL2": "Cães", "merchantCategoryL3": None, "sellerMedal": None, "sellerReputation": "5_green",
         "isFull": None, "isFreeShipping": True, "listingType": "gold_special", "priceAmount": 10.0,
         "orderCount1w": kw.get("w", 100), "orderCount1m": 400, "orderGmv1m": 4000.0, "reviewsCount": 10,
         "reviewsRating": 4.5, "daysInAd": kw.get("d", 50), "numBuyBoxSellers": 1,
         "adPublishDate": kw.get("pub")}
    return r


def test_rekey_keeps_history_when_source_changes(tmp_env):
    """O produto lido pelo site (chave inventada) e depois pelo MCP (productId real) é o mesmo registro."""
    from radar.db import DB
    from radar.run import FixtureSource, run_once
    live = tmp_env / "live"
    live.mkdir()
    # rodada 1: "coleta pelo site" — catálogo com chave cat:hash e anúncio próprio com chave = id
    (live / "ml_main_pet_shop.json").write_text(json.dumps([
        _row("MLB1", "cat:abc", w=500), _row("MLB2", None, w=300)]), "utf-8")
    db = DB()
    r1 = asyncio.run(run_once(FixtureSource(live), db, l1s=["Pet Shop"]))
    assert r1["products"] == 2 and r1["rekeyed"] == 0
    assert {r["key"] for r in db.all_products()} == {"cat:abc", "MLB2"}
    # rodada 2: os mesmos anúncios vêm do MCP com o productId real
    (live / "ml_main_pet_shop.json").write_text(json.dumps([
        _row("MLB1", "MLB777", w=520, pub="2026-03-13T17:05:09.000"), _row("MLB2", "MLB-2", w=310)]), "utf-8")
    r2 = asyncio.run(run_once(FixtureSource(live), db, l1s=["Pet Shop"]))
    assert r2["rekeyed"] == 2 and r2["missing"] == 0
    keys = {r["key"]: r for r in db.all_products()}
    assert set(keys) == {"MLB777", "MLB-2"}
    assert keys["MLB777"]["runs_seen"] == 2 and keys["MLB777"]["first_seen_run"] == 1
    assert keys["MLB777"]["published"] == "2026-03-13"
    data = json.loads((tmp_env / "docs" / "data.json").read_text("utf-8"))
    top = data["products"][0]
    assert top["key"] == "MLB777" and top["prev"] == 1 and top["runs"] == 2 and top["pub"] == "2026-03-13"
    db.close()


def test_rekey_merges_when_new_key_already_exists(tmp_env):
    from radar.db import DB
    db = DB()
    run = db.start_run()
    db.upsert_product({"key": "cat:x", "i": "MLB1", "p": "cat:x", "u": None, "c": True, "n": "a", "img": None, "s": "l",
                       "b": None, "cid": None, "l2id": None, "l1": "A", "l2": "B", "l3": None, "md": None, "rep": None,
                       "full": False, "fs": False, "lt": None, "cl": None, "w": 10}, run, 3, "active")
    db.finish_run(run, "ok", 1, 0)
    run2 = db.start_run()
    db.upsert_product({"key": "MLB9", "i": "MLB1", "p": "MLB9", "u": None, "c": True, "n": "a", "img": None, "s": "l",
                       "b": None, "cid": None, "l2id": None, "l1": "A", "l2": "B", "l3": None, "md": None, "rep": None,
                       "full": False, "fs": False, "lt": None, "cl": None, "w": 10}, run2, 1, "active")
    db.finish_run(run2, "ok", 1, 0)
    db.rekey("cat:x", "MLB9")
    p = db.product("MLB9")
    assert db.product("cat:x") is None
    assert p["best_rank"] == 1 and p["first_seen_run"] == run and p["runs_seen"] == 2
    assert [h["rank"] for h in db.history("MLB9")] == [1, 3]
    db.close()


def test_track_without_discovery_rereads_and_reranks(tmp_env):
    """A rodada das 15h: sem descoberta, relê os ids do radar a partir de ml_track.json."""
    from radar.db import DB
    from radar.run import FixtureSource, run_once
    live = tmp_env / "live"
    live.mkdir()
    (live / "ml_main_pet_shop.json").write_text(json.dumps([
        _row("MLB1", "MLB10", w=500), _row("MLB2", "MLB20", w=300)]), "utf-8")
    db = DB()
    asyncio.run(run_once(FixtureSource(live), db, l1s=["Pet Shop"]))
    # à tarde só o acompanhamento: o segundo passou a vender mais e o primeiro sumiu do ML
    (live / "ml_track.json").write_text(json.dumps([_row("MLB2", "MLB20", w=900)]), "utf-8")
    r = asyncio.run(run_once(FixtureSource(live), db, discover=False))
    assert r["tracked"] == 2 and r["missing"] == 1 and r["products"] == 1
    data = json.loads((tmp_env / "docs" / "data.json").read_text("utf-8"))
    assert [p["key"] for p in data["products"]] == ["MLB20"]
    assert data["products"][0]["prev"] == 2 and data["products"][0]["rank"] == 1
    db.close()


def test_upsert_keeps_name_when_new_row_has_none(tmp_env):
    from radar.db import DB
    db = DB()
    base = {"key": "K", "i": "MLB1", "p": "K", "u": None, "c": False, "img": "i", "s": "l", "b": "b", "cid": None,
            "l2id": None, "l1": "A", "l2": "B", "l3": None, "md": None, "rep": None, "full": False, "fs": False,
            "lt": None, "cl": None, "w": 1}
    db.upsert_product(dict(base, n="Nome bom"), 1, 1, "active")
    db.upsert_product(dict(base, n=None, img=None), 2, 1, "active")
    p = db.product("K")
    assert p["name"] == "Nome bom" and p["image"] == "i"
    db.close()


def test_ingerir_and_plano_flow(tmp_env, capsys, monkeypatch):
    from radar import config, mcp
    from radar.db import DB
    monkeypatch.setattr(config, "L1_CATEGORIES", ["Pet Shop"])
    # banco com um produto ativo e categorias do mês (não pede cat/)
    db = DB()
    run = db.start_run()
    db.upsert_product({"key": "MLB10", "i": "MLB1", "p": "MLB10", "u": None, "c": True, "n": "a", "img": None, "s": "l",
                       "b": None, "cid": None, "l2id": None, "l1": "Pet Shop", "l2": "Cães", "l3": None, "md": None,
                       "rep": None, "full": False, "fs": False, "lt": None, "cl": None, "w": 10}, run, 1, "active")
    db.upsert_product({"key": "MLB20", "i": "MLB2", "p": "MLB20", "u": None, "c": True, "n": "b", "img": None, "s": "l",
                       "b": None, "cid": None, "l2id": None, "l1": "Pet Shop", "l2": "Cães", "l3": None, "md": None,
                       "rep": None, "full": False, "fs": False, "lt": None, "cl": None, "w": 10}, run, 2, "active")
    db.finish_run(run, "ok", 2, 0)
    from datetime import date
    from radar import engine
    mes = date.today().strftime("%Y-%m")
    cat = engine.category_from_row({"categoryId": "MLB8", "categoryName": "Cães", "level": 2, "merchantCategoryL1": "Pet Shop",
                                    "merchantCategoryL2": "Cães", "date": mes + "-01T00:00:00.000"})
    db.replace_categories([cat], mes, run)
    db.commit()
    db.close()

    # orçamento por hora: com limite 1, o plano só entrega um passo e avisa que sobra outro
    monkeypatch.setattr(mcp, "MAX_POR_HORA", 1)
    mcp.main(["plano", "novos", "--reiniciar"])
    out = capsys.readouterr().out
    assert "top/pet_shop" in out and "new/pet_shop" not in out.split("Modelo de")[0] and "mais 1 ficam" in out
    monkeypatch.setattr(mcp, "MAX_POR_HORA", 36)

    mcp.main(["plano", "novos", "--reiniciar"])
    out = capsys.readouterr().out
    assert "top/pet_shop" in out and "new/pet_shop" in out and "MercadoProductsWeekly.bestsellersInfo" in out

    # resposta colunar como o MCP devolve (com prefixo do cubo nas colunas)
    cols = ["MercadoProductsWeekly." + k for k in _row("x", None)]
    def doc(rows):
        return {"columns": cols, "data": [[r[k] for k in _row("x", None)] for r in rows],
                "lastRefreshTime": "2026-09-09T12:00:00Z", "totalRows": len(rows)}
    top = tmp_env / "top.txt"
    top.write_text(json.dumps(doc([_row("MLB1", "MLB10", w=50), _row("MLB3", "MLB30", w=40)])), "utf-8")
    new = tmp_env / "new.txt"
    new.write_text(json.dumps(doc([_row("MLB3", "MLB30", w=40, d=20)])), "utf-8")
    errado = tmp_env / "errado.txt"
    errado.write_text(json.dumps(doc([_row("MLB4", "MLB40", d=500)])), "utf-8")

    with pytest.raises(SystemExit):        # `new` com anúncio de 500 dias: passo trocado
        mcp.main(["ingerir", f"new/pet_shop={errado}"])
    mcp.main(["ingerir", f"top/pet_shop={top}", f"new/pet_shop={new}"])
    assert (tmp_env / "data" / "live" / "novos" / "ml_main_pet_shop.json").exists()
    capsys.readouterr()

    # descoberta completa: o plano passa ao acompanhamento — só o MLB2 (o MLB1 foi descoberto)
    mcp.main(["plano", "novos"])
    out = capsys.readouterr().out
    assert "track/1" in out and '"MLB2"' in out and '"MLB1"' not in out.split("track/1")[1]
    estado = json.loads((tmp_env / "data" / "live" / "novos" / "estado.json").read_text("utf-8"))
    assert estado["lotes"] == [["MLB2"]]

    # a rodada `atualiza` tem estado próprio: abrir uma não apaga a `novos` em andamento
    mcp.main(["plano", "atualiza", "--reiniciar"])
    out = capsys.readouterr().out
    assert "track/1" in out and '"MLB1"' in out            # relê todos os ativos, sem descontar a descoberta
    assert (tmp_env / "data" / "live" / "novos" / "ml_main_pet_shop.json").exists()
    mcp.main(["plano", "novos"])                            # volta para a novos, que continua aberta
    assert "track/1" in capsys.readouterr().out

    tr = tmp_env / "track.txt"
    tr.write_text(json.dumps(doc([_row("MLB2", "MLB20", w=5)])), "utf-8")
    # limite da hora estourado: o plano manda esperar em vez de listar o lote
    monkeypatch.setattr(mcp, "MAX_POR_HORA", 2)
    mcp.main(["plano", "novos"])
    assert "LIMITE DA HORA" in capsys.readouterr().out
    monkeypatch.setattr(mcp, "MAX_POR_HORA", 36)
    mcp.main(["esperar"])                                  # com orçamento, volta na hora
    assert "HORA NOVA" in capsys.readouterr().out
    mcp.main(["ingerir", f"track/1={tr}"])
    mcp.main(["plano", "novos"])
    assert "Nada pendente" in capsys.readouterr().out

    # fechar sem git remoto: roda a rodada e gera data.json (o commit falha de leve, sem derrubar)
    mcp.main(["fechar", "novos"])
    out = capsys.readouterr().out
    assert "Rodada #" in out and "3 produtos no ranking" in out
    data = json.loads((tmp_env / "docs" / "data.json").read_text("utf-8"))
    assert {p["key"] for p in data["products"]} == {"MLB10", "MLB20", "MLB30"}
    assert data["products"][0]["key"] == "MLB10"      # continua vendendo mais
    with pytest.raises(SystemExit):                    # não fecha duas vezes
        mcp.main(["fechar", "novos"])
    mcp.main(["plano", "novos"])                       # continuação agendada depois de fechada: só avisa
    assert "já foi fechada" in capsys.readouterr().out
    assert (tmp_env / "data" / "live" / "novos" / "ml_main_pet_shop.json").exists()
