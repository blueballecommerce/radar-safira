#!/usr/bin/env python3
"""Registra a conferência visual das pranchas em data/fornecedor_veredito.json.

Entrada: um JSON com a lista de decisões, uma por candidato da prancha:
    [{"n": 1, "pos": 2, "veredito": "igual", "obs": "mesma cor, mesma corda", "qtd": 2}, ...]

`qtd` (opcional, padrão 1) é quantas unidades do produto do fornecedor o anúncio
entrega — "Kit 2", "Kit 3 toucas", "2 varais". O lucro usa custo × qtd, e a
comparação de preço é por unidade.

`n` é o número da prancha, `pos` a posição do candidato nela. O veredito vale para
TODOS os anúncios que dividem a mesma foto (mesmo catálogo) — a prancha mostra um
por catálogo, o site mostra todos.

Uso: python scripts/veredito.py decisoes.json
"""
from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDICE = ROOT / "data" / "pranchas" / "indice.json"
SAIDA = ROOT / "data" / "fornecedor_veredito.json"
VALIDOS = {"igual", "parecido", "diferente"}


def registrar_direto(decisoes, root=ROOT):
    """Decisões humanas explícitas por URL/MLB; valida tudo antes de gravar."""
    root=Path(root)
    produtos=json.loads((root/'docs/fornecedores.json').read_text('utf-8-sig'))['produtos']
    por_url={p['url']:p for p in produtos}
    path=root/'data/fornecedor_veredito.json'
    atual=json.loads(path.read_text('utf-8-sig')) if path.exists() else {}
    if not isinstance(decisoes,list) or not isinstance(atual,dict):
        raise ValueError('Esperada uma lista de decisões e um mapa de vereditos.')
    changes={}
    for d in decisoes:
        if d.get('veredito') not in VALIDOS: raise ValueError('Veredito inválido.')
        p=por_url.get(d.get('url'))
        a=next((a for a in (p or {}).get('anuncios',[]) if a['id']==d.get('id')),None)
        if not a: raise ValueError('Par URL/anúncio não encontrado: '+str(d.get('id')))
        reg={'veredito':d['veredito'],'obs':d.get('obs','')}
        old=atual.get(p['url']+'|'+a['id'],{})
        qtd=d.get('qtd',old.get('qtd',a.get('qtd')))
        if qtd is not None:
            if isinstance(qtd,bool) or not isinstance(qtd,int) or qtd<1: raise ValueError('Quantidade inválida.')
            reg['qtd']=qtd
        changes[p['url']+'|'+a['id']]=reg
        if a.get('chave'): changes[p['url']+'|cat:'+a['chave']]=reg
    atual.update(changes)
    tmp=path.with_suffix('.json.tmp');tmp.write_text(json.dumps(atual,ensure_ascii=False,indent=1),'utf-8');tmp.replace(path)
    return changes


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
        if d.get("qtd"):                            # kit: quantas unidades do fornecedor o anúncio entrega
            reg["qtd"] = int(d["qtd"])
        for aid in cand["ids_mesma_foto"]:
            atual[f'{bloco["url"]}|{aid}'] = reg
            novos += 1
        if cand.get("chave"):                       # sobrevive a uma nova pesquisa
            atual[f'{bloco["url"]}|cat:{cand["chave"]}'] = reg
    SAIDA.write_text(json.dumps(atual, ensure_ascii=False, indent=1), "utf-8")
    print(f"{novos} anúncios com veredito ({len(atual)} no total) -> {SAIDA}")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo');parser.add_argument('--direto',action='store_true');parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    if args.direto:
        changes=registrar_direto(json.loads(Path(args.arquivo).read_text('utf-8-sig')),args.root)
        print(f'{len(changes)} chaves registradas em {args.root}')
    else:
        if args.root!=ROOT:parser.error('--root só está disponível no modo direto')
        main(args.arquivo)
