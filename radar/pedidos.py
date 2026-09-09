"""Pedidos de pesquisa: um produto fotografado na loja entra na fila e a busca roda.

O João fotografa o produto na prateleira pela aba "Pedir pesquisa", o
`scripts/coletor.py` grava o pedido aqui, e este módulo faz o mesmo que
`radar fornecedor pesquisar` faz com o catálogo da Flexx: pergunta o nome à
JoomPulse e agrupa os anúncios por catálogo do Mercado Livre.

Cada pedido mora em `data/pedidos/<id>/`:

    pedido.json     o que ele preencheu + o estado
    foto-1.jpg …    as fotos, já encolhidas pelo navegador
    resultado.json  os catálogos encontrados, no mesmo formato do
                    fornecedor_busca.json — assim entra na conferência de sempre

O estado vive no próprio pedido.json:

    na_fila   o coletor gravou; a busca ainda não rodou
    buscando  a busca está rodando agora
    pronto    tem resultado
    erro      a busca falhou; o motivo fica no pedido

O que este módulo NÃO faz: decidir se o anúncio é o mesmo produto. Isso é
conferência foto a foto, feita por quem olha — aqui só chega a lista de
candidatos.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

PASTA = config.DATA_DIR / "pedidos"
CAND_POR_ITEM = 12               # catálogos distintos por pedido
LINHAS_POR_BUSCA = 60            # anúncios lidos por busca


# ------------------------------------------------------------------ arquivos
def _ficha(pid: str) -> Path:
    return PASTA / pid / "pedido.json"


def carrega(pid: str) -> dict | None:
    f = _ficha(pid)
    if not f.exists():
        return None
    return json.loads(f.read_text("utf-8"))


def grava(p: dict) -> None:
    d = PASTA / p["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "pedido.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), "utf-8")


def lista() -> list[dict]:
    """Todos os pedidos, do mais novo para o mais velho."""
    if not PASTA.exists():
        return []
    fora = []
    for d in PASTA.iterdir():
        f = d / "pedido.json"
        if not f.is_file():
            continue
        try:
            fora.append(json.loads(f.read_text("utf-8")))
        except Exception as e:                      # um arquivo torto não derruba a lista
            log.warning("pedido ilegível em %s: %s", d.name, e)
    fora.sort(key=lambda p: p.get("criado") or "", reverse=True)
    return fora


def pendentes() -> list[dict]:
    return [p for p in lista() if p.get("status") in ("na_fila", "buscando")]


# ------------------------------------------------------------------- a busca
async def _busca_um(page, p: dict) -> tuple[dict, int]:
    """Os catálogos que a JoomPulse devolve para o nome deste pedido.

    Mesma receita do `fornecedor.pesquisar`: tenta consultas cada vez mais
    curtas e para assim que juntar catálogos suficientes.
    """
    from . import browser as B
    from . import fornecedor as F

    achados: dict[str, dict] = {}
    for i, q in enumerate(F._consulta(p["nome"])):
        if i >= 2 and achados:                      # a busca de 2 palavras é o último recurso
            break
        try:
            linhas = await B.scrape_search(page, {"query": q}, LINHAS_POR_BUSCA)
        except Exception as e:
            log.warning("busca falhou para %r: %s", q, type(e).__name__)
            continue
        for r in linhas:
            achados.setdefault(r["id"], r)
        if len({B.catalog_key(r) for r in achados.values()}) >= CAND_POR_ITEM:
            break

    cands = F._agrupa_por_catalogo(list(achados.values()), p.get("custo"))[:CAND_POR_ITEM]
    # mesmo formato do data/fornecedor_busca.json, para entrar na conferência de sempre
    item = {
        "url": "pedido:" + p["id"],
        "nome": p["nome"],
        "unit": p.get("custo"),
        "qtd": p.get("qtd_caixa"),
        "fornecedor": p.get("fornecedor"),
        "fotos": p.get("fotos_arquivos") or [],
        "obs": p.get("obs") or "",
    }
    return {"fornecedor": item, "anuncios": cands}, len(achados)


def pesquisar(limite: int | None = None) -> dict:
    """Roda a busca de todos os pedidos na fila. Abre o navegador uma vez só."""
    from . import browser as B

    fila = pendentes()
    if limite:
        fila = fila[:limite]
    if not fila:
        return {"pedidos": 0, "motivo": "nada na fila"}

    async def _run():
        src, close = await B.open_source(B.L1_IDS)
        feitos, erros = 0, 0
        try:
            for p in fila:
                p["status"] = "buscando"
                p["motivo"] = ""
                grava(p)
                try:
                    res, linhas = await _busca_um(src.page, p)
                    (PASTA / p["id"] / "resultado.json").write_text(
                        json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
                    p["resultado"] = {
                        "catalogos": len(res["anuncios"]),
                        "anuncios": linhas,
                        "arquivo": f"data/pedidos/{p['id']}/resultado.json",
                    }
                    p["status"] = "pronto"
                    p["buscado_em"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    feitos += 1
                    log.info("%s: %d catálogos", p["nome"][:40], len(res["anuncios"]))
                except Exception as e:
                    p["status"] = "erro"
                    p["motivo"] = f"{type(e).__name__}: {e}"
                    erros += 1
                    log.exception("pedido %s falhou", p["id"])
                grava(p)
        finally:
            await close()
        return {"pedidos": len(fila), "prontos": feitos, "erros": erros}

    return asyncio.run(_run())
