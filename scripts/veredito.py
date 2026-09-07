#!/usr/bin/env python3
"""Registra a conferência visual das pranchas em data/fornecedor_veredito.json.

Entrada: um JSON com a lista de decisões, uma por candidato da prancha:
    [{"n": 1, "pos": 2, "veredito": "igual", "obs": "mesma cor, mesma corda"}, ...]

`n` é o número da prancha, `pos` a posição do candidato nela. O veredito vale para
TODOS os anúncios que dividem a mesma foto (mesmo catálogo) — a prancha mostra um
por catálogo, o site mostra todos.

Uso: python scripts/veredito.py decisoes.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDICE = ROOT / "data" / "pranchas" / "indice.json"
SAIDA = ROOT / "data" / "fornecedor_veredito.json"
VALIDOS = {"igual", "parecido", "diferente"}


def main(arq: str) -> None:
    decisoes = json.loads(Path(arq).read_text("utf-8"))
    indice = {b["n"]: b for b in json.loads(INDICE.read_text("utf-8"))}
    atual = json.loads(SAIDA.read_text("utf-8")) if SAIDA.exists() else {}
    novos = 0
    for d in decisoes:
        if d["veredito"] not in VALIDOS:
            raise SystemExit(f"veredito inválido: {d}")
        bloco = indice[d["n"]]
        cand = next(c for c in bloco["candidatos"] if c["pos"] == d["pos"])
        reg = {"veredito": d["veredito"], "obs": d.get("obs", "")}
        for aid in cand["ids_mesma_foto"]:
            atual[f'{bloco["url"]}|{aid}'] = reg
            novos += 1
        if cand.get("chave"):                       # sobrevive a uma nova pesquisa
            atual[f'{bloco["url"]}|cat:{cand["chave"]}'] = reg
    SAIDA.write_text(json.dumps(atual, ensure_ascii=False, indent=1), "utf-8")
    print(f"{novos} anúncios com veredito ({len(atual)} no total) -> {SAIDA}")


if __name__ == "__main__":
    main(sys.argv[1])
