"""Configuração central do Radar Safira.

Tudo que é "regra de negócio" ajustável fica aqui: categorias, tamanhos de consulta,
pesos do score, janelas de retenção. Variáveis de ambiente com prefixo RADAR_ sobrescrevem.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("RADAR_ROOT", Path(__file__).resolve().parent.parent))
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
SECRETS_DIR = ROOT / ".secrets"
DB_PATH = DATA_DIR / "radar.db"
TOKEN_PATH = SECRETS_DIR / "token.json"
TOKEN_ENC_PATH = DATA_DIR / "token.enc"

# --- JoomPulse MCP ---------------------------------------------------------
MCP_URL = os.environ.get("RADAR_MCP_URL", "https://joompulse.com/mcp")
# Documento de metadados do cliente OAuth (CIMD). Precisa ser servido em HTTPS com
# Content-Type application/json — o GitHub Pages do próprio repositório faz isso.
CLIENT_METADATA_URL = os.environ.get("RADAR_CLIENT_METADATA_URL", "")
# Alternativa: client_id pré-registrado pela JoomPulse (se um dia fornecerem) — dispensa o CIMD.
CLIENT_ID = os.environ.get("RADAR_CLIENT_ID", "")
OAUTH_CALLBACK_PORT = int(os.environ.get("RADAR_OAUTH_PORT", "8765"))
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_CALLBACK_PORT}/callback"

TOOL_MELI = "query_cubejs_meli"
TOOL_JOOMPRO = "query_cubejs_joompro"

# --- Escopo da coleta ------------------------------------------------------
L1_CATEGORIES: list[str] = [
    "Acessórios para Veículos", "Agro", "Alimentos e Bebidas", "Arte, Papelaria e Armarinho",
    "Bebês", "Beleza e Cuidado Pessoal", "Brinquedos e Hobbies", "Calçados, Roupas e Bolsas",
    "Câmeras e Acessórios", "Casa, Móveis e Decoração", "Celulares e Telefones", "Construção",
    "Eletrodomésticos", "Eletrônicos, Áudio e Vídeo", "Esportes e Fitness", "Ferramentas",
    "Festas e Lembrancinhas", "Games", "Indústria e Comércio", "Informática",
    "Instrumentos Musicais", "Joias e Relógios", "Livros, Revistas e Comics", "Mais Categorias",
    "Música, Filmes e Seriados", "Pet Shop", "Saúde",
]

DISCOVERY_MAIN_LIMIT = int(os.environ.get("RADAR_MAIN_LIMIT", "50"))   # top vendas por L1
DISCOVERY_NEW_LIMIT = int(os.environ.get("RADAR_NEW_LIMIT", "30"))     # anúncios novos vendendo por L1
NEW_LISTING_MAX_DAYS = 90
TRACK_BATCH = 50            # ids por consulta de acompanhamento
CATEGORY_L3_MAX_PAGES = 8   # 800 subcategorias nível 3 (ordenadas por receita)
JOOMPRO_PAGES = 3           # 300 pares

# --- Ranking ---------------------------------------------------------------
TOP_N = 300                 # posições mantidas como "ativas" (a página mostra quantas quiser)
WATCH_RUNS = 28             # rodadas que um produto fica em observação depois de sair do TOP_N (14 dias × 2)
DROP_AFTER_ZERO_SALES_RUNS = 2
WEIGHTS = {"demand": 0.35, "competition": 0.25, "growth": 0.25, "novelty": 0.15}

# JoomPro: filtros mínimos para um par entrar no radar de importação
JOOMPRO_MIN_SCORE = 0.88
JOOMPRO_MIN_MARGIN = 0.25
JOOMPRO_MIN_ORDERS_1M = 20

# --- Rede -------------------------------------------------------------------
QUERY_TIMEOUT_S = 120
QUERY_RETRIES = 3
QUERY_RETRY_BACKOFF_S = 5
