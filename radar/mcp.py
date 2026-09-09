"""Rotina pelo conector MCP da JoomPulse — o Claude consulta, este módulo faz o resto.

A JoomPulse não aceita programa nosso no MCP dela, mas aceita o Claude. Então a rodada
automática (5h: produtos novos; 15h: releitura dos que já estão no radar) é uma sessão do
Claude Code agendada, e a divisão de trabalho é esta:

    python -m radar mcp plano novos      → o que falta consultar (e o modelo de cada consulta)
    <o Claude roda cada consulta na ferramenta query_cubejs_meli>
    python -m radar mcp ingerir passo=arquivo …   → converte o resultado para data/live/*.json
    python -m radar mcp fechar novos     → rodada (score, ranking, histórico), data.json, commit, push

O truque que deixa isso barato: as consultas pedem colunas suficientes para a resposta passar
de ~37 KB (MAX_MCP_OUTPUT_TOKENS=12000 em ~/.claude/settings.json). Aí o Claude Code não põe o
resultado no contexto — grava num arquivo e mostra o caminho — e o dado vai do arquivo para o
banco sem passar pelo modelo. (Acima de ~80 KB a JoomPulse recusa; as consultas ficam em
~60 KB.) Se uma resposta vier pequena (poucas linhas), o Claude salva o JSON num arquivo em
data/live/inbox/ e ingere do mesmo jeito.

Passos (o nome de cada consulta; o slug é o da fixture, sem acento):
    top/<slug da L1>       100 mais vendidos da categoria (fixture ml_main_<slug>.json)
    new/<slug da L1>       100 mais vendidos com até NOVOS_MAX_DIAS no ar (ml_new_<slug>.json)
    track/<n>              lote n de até 100 ids da página (ml_track.json): de manhã só os que a
                           descoberta não trouxe de novo; à tarde (modo atualiza) a página inteira
    cat/<nível>/<página>   categorias do mês, só quando o mês virou (cat_l<nível>.json)

O estado da rodada do dia fica em data/live/<modo>/estado.json (um por modo, para a rodada das
15h não atropelar uma das 5h que ficou aberta); `plano` de novo mostra só o que falta, então uma
rodada interrompida continua de onde parou — é assim que ela atravessa o limite por hora da
JoomPulse (ver MAX_POR_HORA).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config, queries
from .db import DB
from .run import FixtureSource, run_once, slug

LIVE = config.DATA_DIR / "live"          # data/live/<modo>/ guarda os arquivos e o estado de cada modo
INBOX = LIVE / "inbox"
ATUAL = LIVE / "atual.json"              # qual modo está em andamento (para `ingerir` e `status`)
LOG = config.DATA_DIR / "rodada_mcp.log"
LOTE = 100                                                   # ids por consulta de acompanhamento
NOVOS_MAX_DIAS = int(os.environ.get("RADAR_MCP_NOVOS_DIAS", "90"))
LIMITE = 100                                                 # o servidor corta em 100 de qualquer jeito
# A JoomPulse limita os pedidos ao MCP por hora (relógio UTC): em 09/09/2026 a 36ª consulta da
# hora voltou "Hourly request limit for your plan reached". Uma rodada `novos` inteira (54 de
# descoberta + lotes) não cabe numa hora, então `plano` só entrega o que cabe no orçamento; a
# sessão espera a hora virar (`esperar`) e continua a mesma rodada.
MAX_POR_HORA = int(os.environ.get("RADAR_MCP_MAX_POR_HORA", "36"))
# cada lote `track` impresso carrega 100 ids (~1,5 KB); mais que isto por `plano` estoura o que
# a sessão consegue ler de uma vez — ela roda `plano` de novo depois de ingerir
TRACK_POR_PLANO = 12
PAGINAS_CAT = {2: 6, 3: config.CATEGORY_L3_MAX_PAGES}
FERRAMENTA = "query_cubejs_meli (conector JoomPulse, MCP)"
MODOS = ("novos", "atualiza")


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{_agora()}  {msg}\n")


def _dir(modo: str) -> Path:
    return LIVE / modo


def _modo_atual() -> str | None:
    if ATUAL.exists():
        return json.loads(ATUAL.read_text("utf-8")).get("modo")
    return None


def _estado(modo: str | None = None) -> dict:
    modo = modo or _modo_atual()
    if not modo:
        return {}
    p = _dir(modo) / "estado.json"
    if p.exists():
        e = json.loads(p.read_text("utf-8"))
        e.setdefault("modo", modo)
        return e
    return {}


def _grava_estado(e: dict) -> None:
    d = _dir(e["modo"])
    d.mkdir(parents=True, exist_ok=True)
    (d / "estado.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), "utf-8")
    LIVE.mkdir(parents=True, exist_ok=True)
    ATUAL.write_text(json.dumps({"modo": e["modo"]}), "utf-8")


def _limpa_live(modo: str) -> None:
    d = _dir(modo)
    d.mkdir(parents=True, exist_ok=True)
    for p in d.glob("*.json"):
        p.unlink()


# ---------------------------------------------------------------- orçamento por hora
def _hora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")


def _uso_na_hora(e: dict) -> int:
    j = e.get("janela") or {}
    return int(j.get("consultas", 0)) if j.get("hora") == _hora_utc() else 0


def _conta_consulta(e: dict, n: int = 1) -> None:
    """Uma consulta ingerida = um pedido à JoomPulse nesta hora (aproximação: erros e
    repetições não entram, por isso o orçamento padrão fica abaixo do limite real)."""
    j = e.get("janela") or {}
    if j.get("hora") != _hora_utc():
        j = {"hora": _hora_utc(), "consultas": 0}
    j["consultas"] = int(j.get("consultas", 0)) + n
    e["janela"] = j


# ---------------------------------------------------------------- os passos
def _slug_l1(l1: str) -> str:
    """O mesmo slug que a FixtureSource usa para achar o arquivo da categoria."""
    return FixtureSource.SLUGS.get(l1, slug(l1))


def _l1_do_slug(s: str) -> str:
    for l1 in config.L1_CATEGORIES:
        if _slug_l1(l1) == s:
            return l1
    raise ValueError(f"categoria desconhecida: {s!r} (use o slug que `plano` imprime)")


def _arquivo_do_passo(passo: str, modo: str) -> tuple[Path, str]:
    """(arquivo de fixture, chave de deduplicação) — chave vazia = o arquivo é substituído."""
    tipo, _, resto = passo.partition("/")
    d = _dir(modo)
    if tipo == "top":
        return d / f"ml_main_{_slug_l1(_l1_do_slug(resto))}.json", ""
    if tipo == "new":
        return d / f"ml_new_{_slug_l1(_l1_do_slug(resto))}.json", ""
    if tipo == "track":
        return d / "ml_track.json", "id"
    if tipo == "cat":
        nivel = resto.split("/")[0]
        return d / f"cat_l{nivel}.json", "categoryId"
    raise SystemExit(f"passo desconhecido: {passo!r} (esperava top/…, new/…, track/n ou cat/nível/página)")


def _passos_descoberta(modo: str) -> list[str]:
    if modo != "novos":
        return []
    out = []
    for l1 in config.L1_CATEGORIES:
        out += [f"top/{_slug_l1(l1)}", f"new/{_slug_l1(l1)}"]
    return out


def _passos_categorias(db: DB) -> list[str]:
    cats = db.categories()
    mes = cats[0].get("month") if cats else None
    if mes == date.today().strftime("%Y-%m"):
        return []
    return [f"cat/{n}/{p}" for n in (2, 3) for p in range(1, PAGINAS_CAT[n] + 1)]


def _ids_descobertos(modo: str) -> set[str]:
    ids: set[str] = set()
    d = _dir(modo)
    for p in list(d.glob("ml_main_*.json")) + list(d.glob("ml_new_*.json")):
        try:
            ids.update(r["id"] for r in json.loads(p.read_text("utf-8")) if r.get("id"))
        except (ValueError, KeyError, TypeError):
            continue
    return ids


def _lotes_track(modo: str, db: DB, e: dict) -> list[list[str]]:
    """Os lotes de acompanhamento, calculados uma vez por rodada e guardados no estado."""
    if "lotes" in e:
        return e["lotes"]
    ids = db.page_ids()                      # tudo que está na página
    if modo == "novos":
        vistos = _ids_descobertos(modo)      # de manhã, só o que a descoberta não trouxe de novo
        ids = [i for i in ids if i not in vistos]
    ids = sorted(set(ids))
    lotes = [ids[k:k + LOTE] for k in range(0, len(ids), LOTE)]
    # o último lote completa com ids do primeiro: resposta cheia é resposta que cai em
    # arquivo em vez de entrar no contexto; a ingestão ignora as repetições
    if len(lotes) > 1 and len(lotes[-1]) < LOTE:
        extra = [i for i in lotes[0] if i not in lotes[-1]][:LOTE - len(lotes[-1])]
        lotes[-1] = lotes[-1] + extra
    e["lotes"] = lotes
    _grava_estado(e)
    return lotes


def consulta_do_passo(passo: str, e: dict | None = None) -> dict:
    tipo, _, resto = passo.partition("/")
    if tipo == "top":
        return queries.products_top(_l1_do_slug(resto), LIMITE, fat=True)
    if tipo == "new":
        return queries.products_new(_l1_do_slug(resto), LIMITE, fat=True, max_days=NOVOS_MAX_DIAS)
    if tipo == "track":
        e = e if e is not None else _estado()
        if not e:
            raise SystemExit("sem rodada aberta; rode `plano` antes")
        n = int(resto)
        lotes = e.get("lotes") or []
        if n < 1 or n > len(lotes):
            raise SystemExit(f"lote {n} não existe (há {len(lotes)}); rode `plano` antes")
        return queries.products_by_ids(lotes[n - 1], fat=True)
    if tipo == "cat":
        nivel, pagina = (int(x) for x in resto.split("/"))
        return queries.categories(nivel, fat=True, offset=(pagina - 1) * LIMITE, limit=LIMITE)
    raise SystemExit(f"passo desconhecido: {passo!r}")


def _json(q: dict) -> str:
    return json.dumps(q, ensure_ascii=False, separators=(",", ":"))


def _pendentes(modo: str, db: DB, e: dict) -> tuple[list[str], list[str]]:
    """(descoberta/categorias pendentes, acompanhamento pendente). O acompanhamento só é
    calculado depois que a descoberta acabou — os ids descobertos não precisam de releitura."""
    feitos = e.get("feitos", {})
    fase1 = [p for p in _passos_descoberta(modo) + _passos_categorias(db) if p not in feitos]
    if fase1:
        return fase1, []
    lotes = _lotes_track(modo, db, e)
    fase2 = [f"track/{i + 1}" for i in range(len(lotes)) if f"track/{i + 1}" not in feitos]
    return [], fase2


# ---------------------------------------------------------------- comandos
def cmd_plano(modo: str, reiniciar: bool) -> None:
    hoje = date.today().isoformat()
    e = _estado(modo)
    if reiniciar or not e or e.get("dia") != hoje:
        _limpa_live(modo)
        e = {"dia": hoje, "modo": modo, "inicio": _agora(), "feitos": {}}
        _grava_estado(e)
        _log(f"=== plano {modo} iniciado ===")
    elif e.get("fechado"):
        # continuação agendada de uma rodada que já terminou: não há o que fazer
        _grava_estado(e)                                  # só aponta `atual` para este modo
        print(f"A rodada de hoje ({modo}) já foi fechada às {e['fechado']}. Nada a fazer — encerre.")
        return
    else:
        _grava_estado(e)
    db = DB()
    fase1, fase2 = _pendentes(modo, db, e)
    db.close()
    feitos = len(e.get("feitos", {}))

    print(f"Rodada MCP · modo {modo} · {hoje} · {feitos} consulta(s) já ingerida(s)")
    if not fase1 and not fase2:
        print("Nada pendente. Feche a rodada com:  python -m radar mcp fechar " + modo)
        return
    orcamento = MAX_POR_HORA - _uso_na_hora(e)
    if orcamento <= 0:
        print(f"\nLIMITE DA HORA: já foram {_uso_na_hora(e)} consultas nesta hora (limite do plano JoomPulse, "
              f"orçamento {MAX_POR_HORA}). NÃO consulte agora. Rode `python -m radar mcp esperar` (repita até ele "
              f"dizer HORA NOVA) e depois `plano` de novo. Faltam {len(fase1) + len(fase2)} passo(s); a rodada fica aberta.")
        return
    print(f"Ferramenta: {FERRAMENTA}. Cada resposta grande vira um arquivo .txt (o Claude Code avisa o caminho);")
    print("depois: python -m radar mcp ingerir \"<passo>=<caminho do arquivo>\" (vários pares por comando).")
    print(f"Orçamento desta hora: {orcamento} consulta(s) (limite do plano JoomPulse). Faça SÓ as listadas abaixo; "
          "depois rode `plano` de novo. Se ele disser LIMITE DA HORA, rode `esperar` até HORA NOVA e volte ao `plano`.")
    if fase1:
        sobra = max(0, len(fase1) - orcamento)
        fase1 = fase1[:orcamento]
        print(f"\nFALTAM {len(fase1)} consulta(s) de descoberta/categorias agora"
              + (f" (mais {sobra} ficam para a próxima hora)" if sobra else "")
              + ", nesta ordem (passo → nome exato da L1):")
        for p in fase1:
            tipo, _, resto = p.partition("/")
            print(f"  {p:34} {_l1_do_slug(resto) if tipo in ('top', 'new') else ''}")
        tipos = {p.partition("/")[0] for p in fase1}
        if "top" in tipos:
            print("\nModelo de `top/<slug>` (troque {L1} pelo nome exato da categoria, com acentos):")
            print(_json(queries.products_top("{L1}", LIMITE, fat=True)))
        if "new" in tipos:
            print(f"\nModelo de `new/<slug>` (até {NOVOS_MAX_DIAS} dias no ar; troque {{L1}} pelo nome exato):")
            print(_json(queries.products_new("{L1}", LIMITE, fat=True, max_days=NOVOS_MAX_DIAS)))
        if "cat" in tipos:
            print("\nModelo de `cat/<nível>/<página>` (troque {N} pelo nível e {OFFSET} por (página−1)×100):")
            q = queries.categories(2, fat=True)
            q["filters"][1]["values"] = ["{N}"]
            q["offset"] = "{OFFSET}"
            print(_json(q).replace('"{OFFSET}"', "{OFFSET}"))
        print("\nQuando terminar estas, rode `plano` de novo: ele calcula os lotes de acompanhamento.")
    else:
        agora = min(orcamento, TRACK_POR_PLANO)
        sobra = max(0, len(fase2) - agora)
        fase2 = fase2[:agora]
        print(f"\nDescoberta completa. FALTAM {len(fase2)} lote(s) de acompanhamento agora"
              + (f" (mais {sobra} depois: ingira estes e rode `plano` de novo)" if sobra else "")
              + " (consulta pronta, é só copiar):")
        for p in fase2:
            print(f"\n{p}:")
            print(_json(consulta_do_passo(p, e)))
        print("\nDepois de ingerir: python -m radar mcp plano " + modo + "  (e, quando nada faltar, fechar " + modo + ")")


def _linhas(doc) -> tuple[list[dict], str | None]:
    docs = doc if isinstance(doc, list) else [doc]
    out: list[dict] = []
    refresh = None
    for d in docs:
        if not isinstance(d, dict) or "columns" not in d or "data" not in d:
            raise ValueError("JSON sem 'columns'/'data' — não é uma resposta do MCP")
        cols = [re.sub(r"^[A-Za-z]+\.", "", c) for c in d["columns"]]
        out.extend(dict(zip(cols, r)) for r in d["data"])
        refresh = refresh or d.get("lastRefreshTime")
    return out, refresh


def _le_resposta(caminho: str):
    p = Path(caminho)
    if not p.exists():
        raise ValueError(f"arquivo não existe: {caminho}")
    texto = p.read_text("utf-8")
    try:
        return json.loads(texto)
    except ValueError:
        # o Claude Code às vezes grava uma linha de cabeçalho antes do JSON
        i = texto.find("{")
        if i < 0:
            raise
        return json.loads(texto[i:])


def _valida(passo: str, rows: list[dict], e: dict) -> str:
    """Confere se o arquivo é mesmo a consulta que o passo diz. Devolve um aviso (ou '')."""
    tipo, _, resto = passo.partition("/")
    if not rows:
        raise ValueError("resposta sem linhas")
    if tipo in ("top", "new"):
        l1 = _l1_do_slug(resto)
        l1s = {r.get("merchantCategoryL1") for r in rows}
        if l1s != {l1}:
            raise ValueError(f"as linhas são de {sorted(map(str, l1s))}, não de {l1!r} — passo trocado?")
        if tipo == "new":
            dias = [r.get("daysInAd") for r in rows if r.get("daysInAd") is not None]
            if dias and max(dias) > NOVOS_MAX_DIAS:
                raise ValueError(f"há anúncio com {max(dias)} dias no ar — isto não é a consulta `new`")
        if "id" not in rows[0] or "orderCount1w" not in rows[0]:
            raise ValueError("faltam colunas básicas (id, orderCount1w) — consulta errada?")
        return "" if len(rows) >= LIMITE else f"só {len(rows)} linhas"
    if tipo == "track":
        n = int(resto)
        esperados = set((e.get("lotes") or [[]] * n)[n - 1]) if e.get("lotes") and n <= len(e["lotes"]) else set()
        ids = {r.get("id") for r in rows}
        if esperados and not ids & esperados:
            raise ValueError("nenhum id deste lote veio na resposta — arquivo de outro lote?")
        faltam = len(esperados - ids)
        return f"{faltam} id(s) do lote não voltaram (anúncio pausado/encerrado)" if faltam else ""
    if tipo == "cat":
        nivel = int(resto.split("/")[0])
        niveis = {r.get("level") for r in rows}
        if niveis != {nivel}:
            raise ValueError(f"as linhas são de nível {sorted(map(str, niveis))}, não {nivel}")
        return ""
    return ""


def cmd_ingerir(pares: list[str]) -> None:
    e = _estado()
    if not e or e.get("fechado"):
        raise SystemExit("sem rodada aberta: rode `python -m radar mcp plano novos|atualiza` antes")
    modo = e["modo"]
    erros = 0
    for par in pares:
        passo, sep, caminho = par.partition("=")
        passo, caminho = passo.strip(), caminho.strip().strip('"')
        if not sep or not caminho:
            print(f"IGNORADO {par!r}: use passo=caminho")
            erros += 1
            continue
        try:
            rows, refresh = _linhas(_le_resposta(caminho))
            aviso = _valida(passo, rows, e)
            destino, chave = _arquivo_do_passo(passo, modo)
            if chave:
                atuais = json.loads(destino.read_text("utf-8")) if destino.exists() else []
                por_chave = {r.get(chave): r for r in atuais}
                for r in rows:
                    por_chave[r.get(chave)] = r          # a leitura mais nova vale
                rows_out = list(por_chave.values())
            else:
                rows_out = rows
            destino.write_text(json.dumps(rows_out, ensure_ascii=False), "utf-8")
            e.setdefault("feitos", {})[passo] = {"linhas": len(rows), "arquivo": caminho, "em": _agora(),
                                                  "refresh": refresh, "aviso": aviso}
            _conta_consulta(e)
            _grava_estado(e)
            print(f"OK {passo}: {len(rows)} linhas -> {destino.name}" + (f"  (aviso: {aviso})" if aviso else ""))
            _log(f"ingerido {passo}: {len(rows)} linhas{' — ' + aviso if aviso else ''}")
        except Exception as ex:                          # noqa: BLE001 — o motivo vai para o Claude
            erros += 1
            print(f"ERRO {passo}: {ex}")
            _log(f"ERRO ao ingerir {passo}: {ex}")
    if erros:
        raise SystemExit(1)


def _git(*args: str) -> tuple[int, str]:
    r = subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return r.returncode, (r.stdout + r.stderr).strip()


def _publica(modo: str) -> list[str]:
    """Commit dos dados e push para os remotes que existirem. Devolve as linhas do relato."""
    relato = []
    _git("add", "data/radar.db", "docs/data.json")
    if _git("diff", "--cached", "--quiet")[0] == 0:
        relato.append("nada mudou nos dados, sem commit")
        return relato
    msg = f"radar: rodada MCP {modo} {datetime.now():%Y-%m-%d %H:%M}"
    rc, out = _git("-c", "user.name=radar-bot", "-c", "user.email=radar-bot@users.noreply.github.com",
                   "commit", "-q", "-m", msg)
    if rc != 0:
        relato.append(f"FALHA no commit: {out[:300]}")
        return relato
    relato.append(f"commit: {msg}")
    remotos = _git("remote")[1].split()
    for nome, rotulo in (("origin", "GitHub Pages (página pública)"), ("central", "repositório central do Predator")):
        if nome not in remotos:
            continue
        rc, out = _git("push", "-q", nome, "main")
        relato.append(f"publicado em {rotulo}" if rc == 0 else f"AVISO: push para {nome} falhou: {out[:300]}")
    return relato


def _resumo(res: dict, modo: str) -> str:
    dados = json.loads((config.DOCS_DIR / "data.json").read_text("utf-8"))
    prods = dados["products"]
    novos = [p for p in prods if (p.get("runs") or 1) <= 1]
    subiram = sorted((p for p in prods if p.get("prev") and p["prev"] - p["rank"] > 0),
                     key=lambda p: p["rank"] - p["prev"])[:5]
    linhas = [
        f"Rodada #{res['run_id']} ({modo}) fechada: {res['ranked']} produtos no ranking, "
        f"{len(novos)} entraram agora, {res['tracked']} relidos, {res['missing']} sumiram do ML, "
        f"{res.get('rekeyed', 0)} chaves migradas.",
        "Top 5 do radar: " + "; ".join(f"#{p['rank']} {p['n'][:50]} ({p['score']:.0f} pts)" for p in prods[:5]),
    ]
    if novos:
        linhas.append("Novos com maior score: " + "; ".join(
            f"#{p['rank']} {p['n'][:50]} ({p['score']:.0f} pts, {p.get('d', '?')} dias no ar)" for p in novos[:5]))
    if subiram:
        linhas.append("Quem mais subiu: " + "; ".join(f"{p['n'][:40]} {p['prev']}→{p['rank']}" for p in subiram))
    return "\n".join(linhas)


def cmd_fechar(modo: str) -> None:
    e = _estado(modo)
    if not e or e.get("dia") != date.today().isoformat():
        raise SystemExit(f"não há rodada `{modo}` aberta hoje — rode `plano {modo}` antes")
    if e.get("fechado"):
        raise SystemExit(f"a rodada de {e.get('dia')} ({modo}) já foi fechada às {e['fechado']}")
    db = DB()
    fase1, fase2 = _pendentes(modo, db, e)
    if fase1 or fase2:
        db.close()
        print(f"Ainda faltam {len(fase1) + len(fase2)} consulta(s) — rode `plano {modo}` (sem --reiniciar) para "
              "ver o que cabe nesta hora. A rodada continua aberta; nada foi perdido.")
        for p in (fase1 + fase2)[:12]:
            print("  " + p)
        raise SystemExit(2)
    if modo == "novos" and not list(_dir(modo).glob("ml_main_*.json")):
        db.close()
        raise SystemExit(f"modo novos sem nenhum arquivo de descoberta em {_dir(modo)}")
    _log(f"fechando rodada {modo}: {len(e.get('feitos', {}))} consultas ingeridas")
    try:
        res = asyncio.run(run_once(FixtureSource(_dir(modo)), db, discover=(modo == "novos")))
    finally:
        db.close()
    _log(f"rodada #{res['run_id']} ok: {res['ranked']} no ranking, tracked={res['tracked']} missing={res['missing']}")
    relato = _publica(modo)
    for linha in relato:
        _log(linha)
    e["fechado"] = _agora()
    e["resultado"] = res
    _grava_estado(e)
    print(_resumo(res, modo))
    print("Publicação: " + " · ".join(relato))
    refresh = next((f.get("refresh") for f in e.get("feitos", {}).values() if f.get("refresh")), None)
    if refresh:
        print(f"Dados da JoomPulse atualizados em (lastRefreshTime): {refresh}")
    _log("=== rodada concluida ===")


def cmd_esperar(forcar: bool = False) -> None:
    """Espera a hora da JoomPulse virar (relógio UTC, hora cheia) — em fatias de até 590 s,
    porque cada chamada do Bash do Claude Code tem um teto de 10 minutos. A sessão repete o
    comando até ler HORA NOVA. `forcar` ignora o contador (quando a JoomPulse cortou antes
    do orçamento, por uso de outra sessão na mesma hora)."""
    e = _estado()
    agora = datetime.now(timezone.utc)
    if not forcar and (not e or _uso_na_hora(e) < MAX_POR_HORA):
        print("HORA NOVA: há orçamento nesta hora. Rode `plano` de novo.")
        return
    prox = agora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, seconds=45)
    falta = (prox - agora).total_seconds()
    dorme = max(0, min(falta, 590))
    print(f"esperando {int(dorme)} s — a hora da JoomPulse vira às {prox.astimezone():%H:%M} (hora local); "
          f"faltam {int(falta)} s no total", flush=True)
    time.sleep(dorme)
    if datetime.now(timezone.utc) >= prox:
        if e:
            e["janela"] = {"hora": _hora_utc(), "consultas": 0}
            _grava_estado(e)
        print("HORA NOVA: o orçamento voltou. Rode `plano` de novo.")
    else:
        print(f"AINDA NÃO: faltam {int((prox - datetime.now(timezone.utc)).total_seconds())} s. Rode `esperar` de novo.")


def cmd_status() -> None:
    e = _estado()
    if not e:
        print("sem rodada aberta")
        return
    outro = "atualiza" if e["modo"] == "novos" else "novos"
    eo = _estado(outro)
    if eo and eo.get("dia") == date.today().isoformat() and not eo.get("fechado"):
        print(f"(há também uma rodada `{outro}` de hoje aberta, com {len(eo.get('feitos', {}))} consulta(s))")
    feitos = e.get("feitos", {})
    print(f"{e.get('dia')} · modo {e.get('modo')} · início {e.get('inicio')} · fechada: {e.get('fechado') or 'não'}")
    print(f"{len(feitos)} consulta(s) ingerida(s), {sum(f['linhas'] for f in feitos.values())} linhas; "
          f"nesta hora (UTC {_hora_utc()[-2:]}h): {_uso_na_hora(e)} de {MAX_POR_HORA}")
    avisos = [(p, f["aviso"]) for p, f in feitos.items() if f.get("aviso")]
    for p, a in avisos:
        print(f"  aviso {p}: {a}")


def main(argv=None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(prog="radar mcp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="op", required=True)
    p = sub.add_parser("plano", help="o que falta consultar")
    p.add_argument("modo", choices=MODOS)
    p.add_argument("--reiniciar", action="store_true", help="apaga o estado do dia e começa do zero")
    i = sub.add_parser("ingerir", help="passo=arquivo … (resposta do MCP -> data/live)")
    i.add_argument("pares", nargs="+")
    f = sub.add_parser("fechar", help="roda a rodada com o que foi ingerido, gera data.json e publica")
    f.add_argument("modo", choices=MODOS)
    c = sub.add_parser("consulta", help="imprime a consulta CubeJS de um passo")
    c.add_argument("passo")
    sub.add_parser("status")
    w = sub.add_parser("esperar", help="espera a hora da JoomPulse virar (repita até HORA NOVA)")
    w.add_argument("--forcar", action="store_true", help="espera mesmo que o contador diga que há orçamento")
    a = ap.parse_args(argv)
    if a.op == "plano":
        cmd_plano(a.modo, a.reiniciar)
    elif a.op == "ingerir":
        cmd_ingerir(a.pares)
    elif a.op == "fechar":
        cmd_fechar(a.modo)
    elif a.op == "consulta":
        print(_json(consulta_do_passo(a.passo)))
    elif a.op == "status":
        cmd_status()
    elif a.op == "esperar":
        cmd_esperar(a.forcar)


if __name__ == "__main__":
    main()
