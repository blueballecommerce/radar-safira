"""Coletor de pedidos: recebe a foto e o formulário da aba "Pedir pesquisa".

A página do radar é um arquivo estático — não tem para onde mandar um formulário.
Este é o pedaço que falta: um servidor pequeno que fica no PC, recebe o pedido,
grava em `data/pedidos/<id>/` e dispara a busca na JoomPulse.

    .\\.venv\\Scripts\\python.exe scripts\\coletor.py

Ele escuta só em 127.0.0.1 — de fora ninguém chega nele direto. Quem publica na
tailnet é o Tailscale, com o coletor pendurado no MESMO endereço da página, no
caminho /api:

    tailscale serve --bg --https=8444 --set-path=/api http://127.0.0.1:8445

Mesmo endereço importa: a página é https, e um navegador não deixa página https
falar com servidor http. Pendurado em /api os dois viram a mesma origem e o
problema some. É também por isso que a página pública do GitHub nunca alcança o
coletor — de lá o pedido fica guardado no aparelho até você abrir pela tailnet.

Rotas, como a página as chama:
    GET  /api/saude              o coletor está de pé? a busca consegue rodar?
    GET  /api/pedidos            a fila, com o estado de cada um
    GET  /api/foto/<id>/<arq>    a foto de um pedido (para ver os que vieram de
                                 outro aparelho)
    POST /api/pedido             grava um pedido novo e dispara a busca

Atenção: o `--set-path=/api` **remove** o /api antes de encaminhar, então aqui
chega `/saude`, não `/api/saude`. Batendo direto no 127.0.0.1 chega com o
prefixo. O `_rota()` aceita as duas formas, para não depender do caminho que a
requisição fez para chegar.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from radar import pedidos as P            # noqa: E402

log = logging.getLogger("coletor")

PORTA = int(os.environ.get("RADAR_COLETOR_PORTA", "8445"))
CORPO_MAX = 25 * 1024 * 1024              # 25 MB: umas 40 fotos já encolhidas
CHECA_SESSAO_A_CADA = 10 * 60             # segundos
RETENTA_EM = 30                           # quando a conferência não conseguiu rodar

# De onde a página pode chamar. Só a tailnet e o próprio PC: o coletor grava
# arquivos, então não vale deixar qualquer site do mundo conversar com ele.
# O endereço da tailnet tem dois rótulos antes do ts.net (dojoo.tailce25ed.ts.net),
# por isso o (?:[\w-]+\.)+ e não um rótulo só.
ORIGEM_OK = re.compile(r"^https?://(?:localhost|127\.0\.0\.1|(?:[\w-]+\.)+ts\.net)(?::\d+)?$")


# ------------------------------------------------------- a busca é possível?
class Sessao:
    """Se a sessão da JoomPulse ainda vale.

    Descobrir isso abre um navegador e leva ~20 s — caro demais para responder a
    cada vez que a página carrega. Então a resposta fica guardada e é refeita de
    dez em dez minutos, numa linha de execução à parte.
    """

    def __init__(self):
        self.ok = False
        self.motivo = "ainda conferindo a sessão da JoomPulse"
        self.em = 0.0
        self.intervalo = CHECA_SESSAO_A_CADA
        self._lock = threading.Lock()

    def confere(self):
        """`check-browser` sai com erro em DOIS casos diferentes: a sessão
        expirou, ou a conferência nem conseguiu rodar (o perfil do navegador
        fica trancado enquanto outra janela o usa — a do próprio login, por
        exemplo). Tratar os dois como "expirada" fazia uma falha de bastidor
        virar um diagnóstico errado sobre o login do João, guardado por dez
        minutos. Quem separa os casos é o texto na saída."""
        with self._lock:
            if time.time() - self.em < self.intervalo:
                return
            self.em = time.time()
        try:
            r = subprocess.run([sys.executable, "-m", "radar", "check-browser"],
                               cwd=RAIZ, capture_output=True, timeout=120)
            saida = (r.stdout or b"").decode("utf-8", "replace")
            if r.returncode == 0:
                self.ok, self.motivo, self.intervalo = True, "", CHECA_SESSAO_A_CADA
            elif "expirada" in saida:
                self.ok, self.intervalo = False, CHECA_SESSAO_A_CADA
                # texto puro: vai direto para a tela, sem marcação
                self.motivo = "a sessão da JoomPulse expirou — rode  python -m radar login-browser  no PC"
            else:
                self.ok, self.intervalo = False, RETENTA_EM
                self.motivo = "não consegui conferir a sessão agora (o navegador estava ocupado); tentando de novo"
        except Exception as e:
            self.ok, self.intervalo = False, RETENTA_EM
            self.motivo = f"não consegui conferir a sessão ({type(e).__name__}); tentando de novo"
        log.info("sessão da JoomPulse: %s", "ativa" if self.ok else self.motivo)

    def em_segundo_plano(self):
        threading.Thread(target=self.confere, daemon=True).start()


SESSAO = Sessao()


# ---------------------------------------------------------------- a busca
class Busca:
    """Uma busca por vez. Duas ao mesmo tempo brigariam pelo mesmo navegador."""

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    @property
    def rodando(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def dispara(self) -> bool:
        with self._lock:
            if self.rodando:
                return False
            self.proc = subprocess.Popen(
                [sys.executable, "-m", "radar", "pedidos", "pesquisar"],
                cwd=RAIZ,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            log.info("busca disparada (pid %s)", self.proc.pid)
            return True


BUSCA = Busca()


# ------------------------------------------------------------------ o servidor
def _estado_para_tela(p: dict) -> str:
    """O nome que a página usa. `na_fila` vira `entregue` — do lado dele, o que
    importa é que chegou."""
    return {"na_fila": "entregue", "buscando": "buscando",
            "pronto": "pronto", "erro": "erro"}.get(p.get("status"), "entregue")


class Handler(BaseHTTPRequestHandler):
    server_version = "RadarColetor/1.0"

    # o log padrão do http.server escreve uma linha por requisição em stderr
    def log_message(self, fmt, *a):
        log.debug("%s - %s", self.address_string(), fmt % a)

    # ---------------------------------------------------------------- ajuda
    def _cors(self):
        origem = self.headers.get("Origin")
        if origem and ORIGEM_OK.match(origem):
            self.send_header("Access-Control-Allow-Origin", origem)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, codigo=200):
        corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(corpo)

    def _rota(self) -> str:
        """A rota, com ou sem o prefixo /api.

        O `tailscale serve --set-path=/api` TIRA o /api antes de encaminhar: a
        página pede /api/saude e aqui chega /saude. Batendo direto no
        127.0.0.1 chega /api/saude. Aceitar as duas formas evita depender do
        caminho que a requisição fez para chegar.
        """
        r = self.path.split("?")[0].rstrip("/")
        if r == "/api":
            return "/"
        if r.startswith("/api/"):
            r = r[len("/api"):]
        return r

    # ---------------------------------------------------------------- rotas
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        rota = self._rota()
        if rota == "/saude":
            SESSAO.em_segundo_plano()
            return self._json({
                "ok": True,
                "busca_possivel": SESSAO.ok,
                "motivo": SESSAO.motivo,
                "buscando_agora": BUSCA.rodando,
                "na_fila": len(P.pendentes()),
            })
        if rota == "/pedidos":
            return self._json([{
                "id": p["id"],
                "nome": p.get("nome"),
                "status": _estado_para_tela(p),
                "criado": p.get("criado"),
                "fornecedor": p.get("fornecedor"),
                "custo": p.get("custo"),
                "qtd_caixa": p.get("qtd_caixa"),
                "obs": p.get("obs") or "",
                "fotos": p.get("fotos_arquivos") or [],
                "resultado": p.get("resultado"),
                "motivo": p.get("motivo") or "",
            } for p in P.lista()])
        if rota.startswith("/foto/"):
            return self._foto(rota)
        self._json({"ok": False, "erro": "rota desconhecida"}, 404)

    def _foto(self, rota: str):
        """A foto de um pedido, para a página conseguir mostrar os que vieram de
        outro aparelho. Os dois pedaços do caminho são conferidos contra um
        formato fechado — nada de `..` chegar ao disco."""
        partes = rota[len("/foto/"):].split("/")
        if len(partes) != 2:
            return self._json({"ok": False, "erro": "caminho inválido"}, 400)
        pid, arq = partes
        if not re.fullmatch(r"ped-[a-z0-9-]{1,40}", pid) or not re.fullmatch(r"foto-\d{1,3}\.jpg", arq):
            return self._json({"ok": False, "erro": "caminho inválido"}, 400)
        f = P.PASTA / pid / arq
        if not f.is_file():
            return self._json({"ok": False, "erro": "não achei essa foto"}, 404)
        dados = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "max-age=3600")
        self._cors()
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):
        if self._rota() != "/pedido":
            return self._json({"ok": False, "erro": "rota desconhecida"}, 404)

        origem = self.headers.get("Origin")
        if origem and not ORIGEM_OK.match(origem):
            log.warning("recusei um pedido vindo de %s", origem)
            return self._json({"ok": False, "erro": "origem não autorizada"}, 403)

        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > CORPO_MAX:
            return self._json({"ok": False, "erro": f"corpo vazio ou maior que {CORPO_MAX // 1048576} MB"}, 413)

        try:
            dados = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            return self._json({"ok": False, "erro": f"JSON inválido: {e}"}, 400)

        pid = str(dados.get("id") or "")
        if not re.fullmatch(r"ped-[a-z0-9-]{1,40}", pid):
            return self._json({"ok": False, "erro": "id do pedido fora do formato"}, 400)
        nome = (dados.get("nome") or "").strip()
        if not nome:
            return self._json({"ok": False, "erro": "sem o nome do produto, não há o que buscar"}, 400)

        pasta = P.PASTA / pid
        pasta.mkdir(parents=True, exist_ok=True)

        arquivos = []
        for i, foto in enumerate(dados.get("fotos") or [], 1):
            try:
                b64 = foto.split(",", 1)[1] if "," in foto else foto
                caminho = pasta / f"foto-{i}.jpg"
                caminho.write_bytes(base64.b64decode(b64))
                arquivos.append(caminho.name)
            except Exception as e:
                log.warning("foto %d do pedido %s não gravou: %s", i, pid, e)

        ja = P.carrega(pid)
        p = {
            "id": pid,
            "criado": dados.get("criado") or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "recebido": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "nome": nome,
            "fornecedor": (dados.get("fornecedor") or "").strip(),
            "custo": dados.get("custo"),
            "qtd_caixa": dados.get("qtd_caixa"),
            "obs": (dados.get("obs") or "").strip(),
            "fotos_arquivos": arquivos,
            # reenviar um pedido já pesquisado não apaga o resultado
            "status": (ja or {}).get("status") if (ja or {}).get("status") == "pronto" else "na_fila",
            "resultado": (ja or {}).get("resultado"),
            "motivo": "",
        }

        if not SESSAO.ok:
            p["motivo"] = SESSAO.motivo or "a busca não pode rodar agora"
        P.grava(p)
        log.info("pedido %s recebido: %r (%d foto[s])", pid, nome[:50], len(arquivos))

        if p["status"] == "na_fila" and SESSAO.ok:
            BUSCA.dispara()

        self._json({"ok": True, "status": _estado_para_tela(p), "motivo": p["motivo"]})


class Servidor(ThreadingHTTPServer):
    """No Windows o SO_REUSEADDR — que o http.server liga por padrão — deixa
    DOIS processos prenderem a mesma porta, e as requisições vão para um ou para
    o outro sem critério. Um coletor antigo continuava respondendo com uma
    resposta velha depois de eu achar que tinha reiniciado. Desligado, o segundo
    processo falha na hora e diz o que está acontecendo."""

    allow_reuse_address = False
    daemon_threads = True


def main():
    logging.basicConfig(level=os.environ.get("RADAR_LOG", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    P.PASTA.mkdir(parents=True, exist_ok=True)
    SESSAO.em_segundo_plano()

    try:
        srv = Servidor(("127.0.0.1", PORTA), Handler)
    except OSError as e:
        print(f"Não consegui ouvir na porta {PORTA}: {e}")
        print("Já existe um coletor rodando. Feche o outro antes de abrir este.")
        raise SystemExit(1)
    print(f"Coletor de pedidos ouvindo em http://127.0.0.1:{PORTA}")
    print(f"Pedidos em {P.PASTA}")
    print()
    print("Para a página do celular alcançar, publique no mesmo endereço dela:")
    print(f"  tailscale serve --bg --https=8444 --set-path=/api http://127.0.0.1:{PORTA}")
    print()
    print("Ctrl+C para parar.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nparando…")
        srv.shutdown()


if __name__ == "__main__":
    main()
