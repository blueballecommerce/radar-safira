"""Cliente MCP da JoomPulse: abre a sessão, chama as ferramentas de consulta e devolve linhas.

As ferramentas (`query_cubejs_meli`, `query_cubejs_joompro`) recebem `{"query": "<JSON CubeJS>"}`
e devolvem JSON colunar: {"columns": [...], "data": [[...], ...]}. Aqui isso vira lista de dicts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from . import config

log = logging.getLogger("radar.pulse")


class PulseError(RuntimeError):
    pass


def rows_of(resp: dict) -> list[dict]:
    cols = [re.sub(r"^[A-Za-z]+\.", "", c) for c in resp["columns"]]
    return [dict(zip(cols, r)) for r in resp["data"]]


def _parse_result(result: Any) -> dict:
    """Extrai o JSON colunar de um CallToolResult (structuredContent ou texto)."""
    if getattr(result, "isError", False):
        text = " ".join(getattr(c, "text", "") for c in result.content)
        raise PulseError(text or "erro desconhecido da ferramenta")
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict) and "columns" in sc:
        return sc
    for c in result.content:
        t = getattr(c, "text", None)
        if not t:
            continue
        try:
            d = json.loads(t)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "columns" in d:
            return d
        if isinstance(d, dict) and "error" in d:
            raise PulseError(str(d["error"]))
    raise PulseError("resposta sem colunas: " + str(result)[:300])


class Pulse:
    """Sessão MCP viva. Use como `async with Pulse(auth) as p: await p.meli(query)`."""

    def __init__(self, auth: httpx.Auth | None, url: str = config.MCP_URL):
        self.auth = auth
        self.url = url
        self._cm = None
        self.session: ClientSession | None = None
        self.calls = 0

    async def __aenter__(self):
        self._cm = self._open()
        self.session = await self._cm.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self._cm.__aexit__(*exc)

    @asynccontextmanager
    async def _open(self):
        http = create_mcp_http_client(auth=self.auth, timeout=httpx.Timeout(config.QUERY_TIMEOUT_S, read=300))
        async with streamable_http_client(self.url, http_client=http) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                yield s

    async def tools(self) -> list[str]:
        res = await self.session.list_tools()
        return [t.name for t in res.tools]

    async def call(self, tool: str, query: dict) -> list[dict]:
        last: Exception | None = None
        for attempt in range(1, config.QUERY_RETRIES + 1):
            try:
                self.calls += 1
                res = await self.session.call_tool(tool, {"query": json.dumps(query, ensure_ascii=False)})
                return rows_of(_parse_result(res))
            except PulseError:
                # erro de consulta (campo inexistente etc.) não melhora com retry
                raise
            except Exception as e:  # rede / timeout
                last = e
                log.warning("consulta falhou (%s/%s): %s", attempt, config.QUERY_RETRIES, e)
                await asyncio.sleep(config.QUERY_RETRY_BACKOFF_S * attempt)
        raise PulseError(f"consulta falhou após {config.QUERY_RETRIES} tentativas: {last}")

    async def meli(self, query: dict) -> list[dict]:
        return await self.call(config.TOOL_MELI, query)

    async def joompro(self, query: dict) -> list[dict]:
        return await self.call(config.TOOL_JOOMPRO, query)

    async def paged(self, tool: str, query: dict, max_pages: int, page: int = 100) -> list[dict]:
        out: list[dict] = []
        for n in range(max_pages):
            q = dict(query, limit=page, offset=n * page)
            rows = await self.call(tool, q)
            out.extend(rows)
            if len(rows) < page:
                break
        return out
