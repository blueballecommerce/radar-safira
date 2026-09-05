"""Autenticação OAuth com a JoomPulse (servidor MCP).

Fluxo: uma vez, no seu computador, `python -m radar login` abre o navegador, você entra na
JoomPulse e autoriza. O token (com refresh) fica em `.secrets/token.json` (fora do git).
Para rodar no GitHub Actions, `python -m radar token encrypt` gera `data/token.enc`
(criptografado com a senha em RADAR_TOKEN_KEY); o workflow descriptografa, roda e regrava.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

from . import config


class FileTokenStorage(TokenStorage):
    """Guarda tokens e info do cliente num JSON local (permissão 600)."""

    def __init__(self, path: Path = config.TOKEN_PATH):
        self.path = Path(path)

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text("utf-8") or "{}")

    def _write(self, d: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2), "utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    async def get_tokens(self) -> OAuthToken | None:
        t = self._read().get("tokens")
        return OAuthToken.model_validate(t) if t else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        d = self._read()
        d["tokens"] = tokens.model_dump(exclude_none=True)
        self._write(d)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        c = self._read().get("client")
        return OAuthClientInformationFull.model_validate(c) if c else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        d = self._read()
        d["client"] = client_info.model_dump(exclude_none=True, mode="json")
        self._write(d)

    def has_tokens(self) -> bool:
        return bool(self._read().get("tokens"))


def client_metadata() -> OAuthClientMetadata:
    return OAuthClientMetadata(
        client_name="Radar Safira",
        redirect_uris=[config.OAUTH_REDIRECT_URI],  # type: ignore[list-item]
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
        scope="mcp",
    )


def client_metadata_document() -> dict:
    """Conteúdo de docs/oauth-client.json (CIMD). O client_id É a URL onde este JSON vive."""
    if not config.CLIENT_METADATA_URL:
        raise SystemExit("Defina RADAR_CLIENT_METADATA_URL (URL pública HTTPS de docs/oauth-client.json).")
    m = client_metadata().model_dump(exclude_none=True, mode="json")
    m["client_id"] = config.CLIENT_METADATA_URL
    m["client_uri"] = config.CLIENT_METADATA_URL.rsplit("/", 1)[0]
    return m


class _CallbackServer:
    """Servidor HTTP mínimo que espera o redirect do OAuth em localhost."""

    def __init__(self, port: int):
        self.port = port
        self.result: dict | None = None
        self._event = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                q = parse_qs(urlparse(self.path).query)
                if urlparse(self.path).path != "/callback":
                    self.send_response(404); self.end_headers(); return
                server.result = {k: v[0] for k, v in q.items()}
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                ok = "code" in server.result
                self.wfile.write(("<h2>Radar Safira: autorização concluída. Pode fechar esta aba.</h2>" if ok
                                  else f"<h2>Falha na autorização: {server.result}</h2>").encode())
                server._event.set()

            def log_message(self, *a):  # silencia
                pass

        self.httpd = HTTPServer(("localhost", port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def wait(self, timeout: float | None = None) -> dict:
        timeout = config.OAUTH_WAIT_S if timeout is None else timeout
        self._event.wait(timeout)
        self.httpd.shutdown()
        if not self.result:
            raise TimeoutError("Nenhum redirect recebido em localhost; tente de novo.")
        if "code" not in self.result:
            raise RuntimeError(f"OAuth negado: {self.result}")
        return self.result


def make_auth(storage: FileTokenStorage | None = None, interactive: bool = False) -> OAuthClientProvider:
    """Cria o httpx.Auth que injeta o Bearer e renova o token sozinho.

    interactive=True abre o navegador quando não há token (comando `login`).
    interactive=False (Actions) falha alto se precisar de login.
    """
    storage = storage or FileTokenStorage()
    cb = _CallbackServer(config.OAUTH_CALLBACK_PORT) if interactive else None
    if config.CLIENT_ID and not storage._read().get("client"):
        # client_id fixo fornecido pela JoomPulse: grava como "já registrado" para o SDK não tentar registrar
        info = OAuthClientInformationFull(client_id=config.CLIENT_ID, **client_metadata().model_dump(exclude_none=True))
        d = storage._read(); d["client"] = info.model_dump(exclude_none=True, mode="json"); storage._write(d)

    async def redirect_handler(url: str) -> None:
        if not interactive:
            raise RuntimeError("Token ausente ou inválido e sessão não interativa. Rode `python -m radar login` no seu computador.")
        cb.start()
        print("\nAbra este endereço no navegador (abrindo automaticamente se possível):\n" + url + "\n")
        webbrowser.open(url)

    async def callback_handler() -> tuple[str, str | None]:
        r = await asyncio.get_event_loop().run_in_executor(None, cb.wait)
        return r["code"], r.get("state")

    return OAuthClientProvider(
        server_url=config.MCP_URL,
        client_metadata=client_metadata(),
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
        client_metadata_url=config.CLIENT_METADATA_URL or None,
    )


# --- criptografia do token para o repositório --------------------------------
def _fernet(key: str):
    from cryptography.fernet import Fernet
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(key: str, src: Path = config.TOKEN_PATH, dst: Path = config.TOKEN_ENC_PATH) -> None:
    data = Path(src).read_bytes()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(_fernet(key).encrypt(data))


def decrypt_token(key: str, src: Path = config.TOKEN_ENC_PATH, dst: Path = config.TOKEN_PATH) -> None:
    data = _fernet(key).decrypt(Path(src).read_bytes())
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    os.chmod(dst, 0o600)
