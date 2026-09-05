#!/usr/bin/env python3
"""Gera docs/oauth-client.json (documento de metadados do cliente OAuth) para a URL pública informada.

Uso: RADAR_CLIENT_METADATA_URL=https://SEU-USUARIO.github.io/radar-safira/oauth-client.json python scripts/make_client_metadata.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from radar import auth, config
doc = auth.client_metadata_document()
out = config.DOCS_DIR / "oauth-client.json"
out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")
print(json.dumps(doc, indent=2, ensure_ascii=False))
print(f"\n-> {out}")
