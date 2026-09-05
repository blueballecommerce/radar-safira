#!/usr/bin/env python3
"""Converte respostas columnares do MCP JoomPulse (columns/data) em fixtures do radar.

O plano B usa o conector MCP do Claude como coletor: cada consulta e salva crua em
data/live/raw/<nome>.json no formato columnar devolvido pelo servidor, e este script
transforma tudo em data/live/<nome>.json (lista de objetos), que e o formato que
radar.run.FixtureSource le.

Uso: python scripts/columnar_to_fixtures.py [pasta_raw] [pasta_saida]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "live" / "raw"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "live"


def rows(doc: dict) -> list[dict]:
    cols = doc["columns"]
    return [dict(zip(cols, r)) for r in doc["data"]]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for p in sorted(RAW.glob("*.json")):
        doc = json.loads(p.read_text("utf-8"))
        # varias paginas de uma mesma consulta podem vir como lista de respostas
        docs = doc if isinstance(doc, list) else [doc]
        out: list[dict] = []
        for d in docs:
            out.extend(rows(d))
        (OUT / p.name).write_text(json.dumps(out, ensure_ascii=False), "utf-8")
        total += len(out)
        print(f"{p.name}: {len(out)} linhas")
    print(f"\n-> {total} linhas em {OUT}")


if __name__ == "__main__":
    main()
