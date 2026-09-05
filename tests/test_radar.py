"""Testes: motor de score/ranking com dados reais (fixtures) e cliente MCP contra o servidor falso."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
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


# ------------------------------------------------------------------ engine
def test_normalize_dedupe_and_score(tmp_env):
    from radar import engine
    rows = json.loads((FIX / "ml_main_casa_moveis_decoracao.json").read_text("utf-8"))
    prods = [p for p in (engine.product_from_row(r, "main") for r in rows) if p]
    assert prods and all(p["w"] > 0 for p in prods)
    deduped = engine.dedupe(prods)
    assert len({p["key"] for p in deduped}) == len(deduped)
    cats = [engine.category_from_row(r) for r in json.loads((FIX / "cat_l2.json").read_text("utf-8"))]
    sc = engine.Scorer(deduped, cats)
    for p in deduped:
        sc.score(p)
        assert 0 <= p["score"] <= 100
        assert 0 <= p["_dp"] <= 1 and 0 <= p["_comp"] <= 1 and 0 <= p["_growth"] <= 1
    live = engine.rank(deduped)
    assert [p["rank"] for p in live] == list(range(1, len(live) + 1))
    assert all(live[i]["score"] >= live[i + 1]["score"] for i in range(len(live) - 1))


def test_category_and_import_scores(tmp_env):
    from radar import engine
    c = {"t12": 0.25, "gG": 0.4, "opp": "high", "mono": "low", "sat": "low", "gmv": 5e7}
    engine.score_category(c)
    assert c["cs"] >= 90
    j = {"mg": 0.6, "mo": 2000, "sc": 0.95}
    engine.score_import(j)
    assert 80 <= j["is"] <= 100


# ------------------------------------------------------------------ rodada com fixtures + histórico
def test_two_runs_history(tmp_env):
    from radar.db import DB
    from radar.run import FixtureSource, run_once
    db = DB()
    r1 = asyncio.run(run_once(FixtureSource(FIX), db, l1s=["Casa, Móveis e Decoração", "Pet Shop"]))
    assert r1["products"] > 50 and r1["ranked"] == r1["products"]
    r2 = asyncio.run(run_once(FixtureSource(FIX), db, l1s=["Casa, Móveis e Decoração", "Pet Shop"]))
    data = json.loads((tmp_env / "docs" / "data.json").read_text("utf-8"))
    top = data["products"][0]
    assert top["rank"] == 1 and top["prev"] == 1 and top["runs"] == 2 and top["best"] == 1
    assert len(top["hist"]) == 2
    assert data["meta"]["counts"]["active"] <= 300
    # categorias: só recarrega quando o mês muda (segunda rodada não refaz)
    assert r2["queries"] < r1["queries"]
    db.close()


def test_rank_reorders_when_better_product_appears(tmp_env):
    """Um produto melhor entra em 1º e empurra os demais para baixo (não há 'vaga fixa')."""
    from radar import engine
    base = {"u": None, "c": False, "n": "x", "img": None, "s": "loja", "b": None, "cid": None, "l2id": None,
            "l1": "A", "l2": "B", "l3": None, "md": None, "rep": None, "full": False, "fs": False, "lt": None,
            "cl": "mid", "m": 0, "g": 0, "rc": 100, "rr": 4.8, "bb": 1, "src": "main"}
    a = dict(base, i="MLB1", p="MLB-1", key="MLB-1", n="a", w=100, d=300, pr=50)
    b = dict(base, i="MLB2", p="MLB-2", key="MLB-2", n="b", w=1000, d=20, pr=50, cl="low")
    sc = engine.Scorer([a], [])
    sc.score(a)
    assert engine.rank([a])[0]["key"] == "MLB-1"
    sc = engine.Scorer([a, b], [])
    for p in (a, b):
        sc.score(p)
    live = engine.rank([a, b])
    assert live[0]["key"] == "MLB-2" and live[1]["key"] == "MLB-1" and a["rank"] == 2


# ------------------------------------------------------------------ cliente MCP
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="module")
def mock_server():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(ROOT / "tests" / "mock_server.py"), str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.2)
    yield f"http://127.0.0.1:{port}/mcp"
    proc.terminate()


def test_pulse_client_end_to_end(tmp_env, mock_server, monkeypatch):
    monkeypatch.setenv("RADAR_MCP_URL", mock_server)
    for m in list(sys.modules):
        if m.startswith("radar"):
            del sys.modules[m]
    from radar import queries
    from radar.db import DB
    from radar.pulse import Pulse
    from radar.run import PulseSource, run_once

    async def go():
        async with Pulse(None, url=mock_server) as p:
            assert set(await p.tools()) >= {"query_cubejs_meli", "query_cubejs_joompro"}
            rows = await p.meli(queries.products_top("Casa, Móveis e Decoração"))
            assert rows[0]["id"] == "MLB1" and rows[0]["orderCount1w"] == 1200
            db = DB()
            res = await run_once(PulseSource(p), db, l1s=["Casa, Móveis e Decoração"])
            assert res["products"] == 2 and res["ranked"] == 2
            data = json.loads((tmp_env / "docs" / "data.json").read_text("utf-8"))
            assert data["products"][0]["n"].startswith("Chaleira")  # baixa concorrência + novo + categoria em alta
            assert data["categories"][0]["cs"] > 0 and data["joompro"][0]["is"] > 0
            db.close()
    asyncio.run(go())


# ------------------------------------------------------------------ auth / token
def test_token_storage_and_crypto(tmp_env, monkeypatch):
    monkeypatch.setenv("RADAR_CLIENT_METADATA_URL", "https://exemplo.github.io/radar-safira/oauth-client.json")
    for m in list(sys.modules):
        if m.startswith("radar"):
            del sys.modules[m]
    from mcp.shared.auth import OAuthToken
    from radar import auth, config
    st = auth.FileTokenStorage()
    assert not st.has_tokens()
    asyncio.run(st.set_tokens(OAuthToken(access_token="a", token_type="Bearer", refresh_token="r", expires_in=3600)))
    assert st.has_tokens()
    if os.name != "nt":  # Windows nao suporta permissao POSIX 600
        assert oct(os.stat(config.TOKEN_PATH).st_mode)[-3:] == "600"
    auth.encrypt_token("senha-forte")
    config.TOKEN_PATH.unlink()
    auth.decrypt_token("senha-forte")
    assert asyncio.run(st.get_tokens()).refresh_token == "r"
    with pytest.raises(Exception):
        auth.decrypt_token("senha-errada")
    provider = auth.make_auth(st)
    assert provider is not None
    doc = auth.client_metadata_document()
    assert doc["client_id"] == config.CLIENT_METADATA_URL and doc["redirect_uris"] == ["http://localhost:8765/callback"]
    assert doc["token_endpoint_auth_method"] == "none" and doc["scope"] == "mcp"
