"""CLI do Radar Safira.

  python -m radar login-browser         # abre o navegador para você entrar na JoomPulse — uma vez, no seu PC
  python -m radar check-browser         # diz se a sessão guardada do navegador ainda vale
  python -m radar login                 # (caminho OAuth, hoje recusado pela JoomPulse)
  python -m radar check                 # testa a conexão MCP (lista ferramentas + 1 consulta)
  python -m radar run --browser         # rodada completa lendo o site (sessão do navegador)
  python -m radar run                   # rodada completa via MCP (precisa de client_id da JoomPulse)
  python -m radar run --fixtures DIR    # rodada usando JSONs locais (sem rede)
  python -m radar export                # só regenera docs/data.json
  python -m radar token encrypt|decrypt # token.json <-> data/token.enc (senha em RADAR_TOKEN_KEY)
  python -m radar client-metadata       # imprime o JSON do documento OAuth (docs/oauth-client.json)
  python -m radar fornecedor coletar    # baixa o catálogo da Flexx Imports -> data/fornecedor.json
  python -m radar fornecedor cruzar     # cruza o catálogo com o radar -> data/pares.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from . import auth, config, queries
from .db import DB
from .export import export_json


def _log():
    logging.basicConfig(level=os.environ.get("RADAR_LOG", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def cmd_login(_):
    from .pulse import Pulse
    storage = auth.FileTokenStorage()
    async with Pulse(auth.make_auth(storage, interactive=True)) as p:
        tools = await p.tools()
    print("Autorizado. Ferramentas disponíveis:", ", ".join(tools))
    print(f"Token salvo em {config.TOKEN_PATH}")


async def cmd_login_browser(_):
    from . import browser
    ok = await browser.login()
    if not ok:
        raise SystemExit("Login não concluído.")
    print(f"Perfil guardado em {browser.PROFILE_DIR}")


async def cmd_check_browser(_):
    from . import browser
    ok = await browser.check()
    print("Sessão do navegador:", "ativa" if ok else "expirada — rode `python -m radar login-browser`")
    if not ok:
        raise SystemExit(1)


async def cmd_check(_):
    from .pulse import Pulse
    storage = auth.FileTokenStorage()
    if not storage.has_tokens():
        raise SystemExit("Sem token. Rode `python -m radar login`.")
    async with Pulse(auth.make_auth(storage)) as p:
        tools = await p.tools()
        rows = await p.meli(queries.ping())
    print("OK — ferramentas:", tools, "| exemplo:", rows[:1])


async def cmd_run(a):
    from .run import FixtureSource, PulseSource, run_once
    db = DB()
    try:
        if a.browser:
            from . import browser as B
            src, close = await B.open_source(B.L1_IDS)
            try:
                res = await run_once(src, db, force_categories=a.force_categories,
                                     force_joompro=a.force_joompro, l1s=a.l1 or None)
            finally:
                await close()
        elif a.fixtures:
            src = FixtureSource(Path(a.fixtures))
            res = await run_once(src, db, force_categories=a.force_categories, force_joompro=a.force_joompro,
                                 l1s=a.l1 or None)
        else:
            from .pulse import Pulse
            storage = auth.FileTokenStorage()
            if not storage.has_tokens():
                raise SystemExit("Sem token. Rode `python -m radar login` (ou decrypt no CI).")
            async with Pulse(auth.make_auth(storage)) as p:
                res = await run_once(PulseSource(p), db, force_categories=a.force_categories,
                                     force_joompro=a.force_joompro, l1s=a.l1 or None)
        print(json.dumps(res, ensure_ascii=False))
    finally:
        db.close()


def cmd_export(_):
    db = DB()
    print(export_json(db))
    db.close()


def cmd_token(a):
    key = os.environ.get("RADAR_TOKEN_KEY")
    if not key:
        raise SystemExit("Defina RADAR_TOKEN_KEY (senha forte, a mesma nos Secrets do GitHub).")
    if a.op == "encrypt":
        auth.encrypt_token(key)
        print(f"Gravado {config.TOKEN_ENC_PATH} (pode ir para o git).")
    else:
        auth.decrypt_token(key)
        print(f"Restaurado {config.TOKEN_PATH}.")


def cmd_fornecedor(a):
    from . import fornecedor as F
    if a.op == "coletar":
        cat = F.coletar()
        print(json.dumps({"produtos": len(cat), "arquivo": str(F.SAIDA)}, ensure_ascii=False))
        return
    if not F.SAIDA.exists():
        raise SystemExit("Sem catálogo. Rode `python -m radar fornecedor coletar` antes.")
    cat = json.loads(F.SAIDA.read_text("utf-8"))
    dados = json.loads((config.DOCS_DIR / "data.json").read_text("utf-8"))
    pares = F.cruzar(cat, dados.get("products", []))
    print(json.dumps({"itens": len(cat), "com_candidato": len(pares), "arquivo": str(F.PARES)},
                     ensure_ascii=False))


def cmd_client_metadata(_):
    print(json.dumps(auth.client_metadata_document(), indent=2, ensure_ascii=False))


def main(argv=None):
    _log()
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("check")
    sub.add_parser("login-browser")
    sub.add_parser("check-browser")
    r = sub.add_parser("run")
    r.add_argument("--fixtures")
    r.add_argument("--browser", action="store_true",
                   help="coleta lendo o site com a sessão guardada (login-browser)")
    r.add_argument("--force-categories", action="store_true")
    r.add_argument("--force-joompro", action="store_true")
    r.add_argument("--l1", action="append", help="limita a coleta a uma categoria L1 (repetível)")
    sub.add_parser("export")
    t = sub.add_parser("token")
    t.add_argument("op", choices=["encrypt", "decrypt"])
    sub.add_parser("client-metadata")
    f = sub.add_parser("fornecedor")
    f.add_argument("op", choices=["coletar", "cruzar"])
    a = ap.parse_args(argv)
    if a.cmd == "login":
        asyncio.run(cmd_login(a))
    elif a.cmd == "login-browser":
        asyncio.run(cmd_login_browser(a))
    elif a.cmd == "check-browser":
        asyncio.run(cmd_check_browser(a))
    elif a.cmd == "check":
        asyncio.run(cmd_check(a))
    elif a.cmd == "run":
        asyncio.run(cmd_run(a))
    elif a.cmd == "export":
        cmd_export(a)
    elif a.cmd == "token":
        cmd_token(a)
    elif a.cmd == "client-metadata":
        cmd_client_metadata(a)
    elif a.cmd == "fornecedor":
        cmd_fornecedor(a)


if __name__ == "__main__":
    main()
