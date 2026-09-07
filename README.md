# Radar Safira

Máquina de oportunidades do Mercado Livre: consulta a JoomPulse por conta própria (sem IA no meio),
mantém um ranking vivo com histórico e publica uma página estática. Roda sozinha todo dia às 8h,
pela Tarefa Agendada do Windows, sem consumir tokens de IA.

```
JoomPulse (site, sessão do navegador)  ──►  radar/browser.py (Playwright)
                                          │  54 buscas por rodada (27 categorias × top + novos) + a árvore de categorias
                                          ▼
                                  radar/engine.py  score 0–100 · dedupe · ranking
                                          ▼
                                  data/radar.db    histórico (produto × rodada), status, melhor posição
                                          ▼
                                  docs/data.json   ──►  docs/index.html (GitHub Pages)
```

## Como o ranking vive

- Cada rodada refaz a **descoberta** (top 50 por vendas + 30 anúncios novos vendendo, em cada uma das 27 categorias)
  e **relê pelo id** todo produto que já estava ativo ou em observação e não voltou na descoberta.
- Tudo é pontuado de novo e reordenado inteiro: um produto melhor entra no nº 1 e empurra os outros para baixo.
  Não existe vaga fixa.
- Status: `active` (posição ≤ 300), `watching` (saiu do top mas continua vendendo — até 28 rodadas / 14 dias),
  `candidate` (apareceu na descoberta, ainda não entrou no top), `dropped` (sem vendas em 2 rodadas ou anúncio sumiu).
- A página mostra posição anterior → atual, melhor posição, há quantas rodadas está no radar e o histórico.

## Score (0–100) — a única opinião do sistema

| Componente | Peso | De onde vem |
|---|---|---|
| Volume de vendas | 35 | posição de `orderCount1w` (estimativa JoomPulse) entre todos os produtos da rodada |
| Pouca concorrência | 25 | `l2CompetitivenessLevel`, `numBuyBoxSellers`, monopolização e saturação da subcategoria |
| Categoria crescendo | 25 | `currentTrend12m`, `orderGmvGrowth1m`, `opportunityLevel` da subcategoria (nível 3, senão 2) |
| Novo e vendendo | 15 | `daysInAd` (≤30 vale cheio, cai até 365) × volume |

Pesos e limiares em `radar/config.py`. Fórmula em `radar/engine.py`.

## Como a coleta acontece

A JoomPulse **recusa clientes OAuth de terceiros**: o `client_id` por metadata document
responde `invalid_client`, e o endpoint `/mcp` devolve `401` para cookie de sessão. O MCP
deles só aceita Claude e ChatGPT, que são clientes registrados por eles.

Por isso a coleta é feita **pelo site**, com a sua própria sessão: um Chromium com perfil
persistente guarda o login (feito uma vez, com o código por SMS/WhatsApp) e depois abre as
páginas sozinho, em segundo plano, lendo as tabelas com JavaScript. Nenhum dado passa por
um modelo de IA — vai da página direto para o SQLite.

Consequências disso:

- a rodada acontece **no seu PC** (tarefa agendada do Windows), não no GitHub Actions;
- o site não expõe a subcategoria do produto nem o nível de concorrência da subcategoria,
  então esses dois sinais entram no score de forma parcial;
- `numBuyBoxSellers` é reconstruído contando quantos anúncios dividem o mesmo catálogo.

Se um dia a JoomPulse fornecer um `client_id`, basta pôr em `RADAR_CLIENT_ID`, religar o
cron em `.github/workflows/refresh.yml` e voltar ao caminho MCP, que continua no código.

## Comandos

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium

python -m radar login-browser      # uma vez: abre o navegador para você entrar na JoomPulse
python -m radar check-browser      # diz se a sessão guardada ainda vale
python -m radar run --browser      # rodada completa lendo o site
.\scripts\agendar.ps1           # tarefa do Windows, todo dia às 8h

python -m radar login              # (caminho MCP — hoje recusado pela JoomPulse)
python -m radar check              # testa a conexão MCP
python -m radar run                # rodada completa
python -m radar run --fixtures tests/fixtures   # rodada com dados locais (sem rede)
python -m radar export             # só regenera docs/data.json
python -m radar token encrypt      # .secrets/token.json -> data/token.enc (senha em RADAR_TOKEN_KEY)
python -m pytest -q                # testes (motor, histórico, cliente MCP contra servidor falso, token)
```

Variáveis: `RADAR_CLIENT_METADATA_URL` (URL pública de `docs/oauth-client.json`), `RADAR_TOKEN_KEY` (senha do token
no repositório), `RADAR_CLIENT_ID` (opcional: client_id fixo, se a JoomPulse fornecer um).

## Autenticação, em uma frase

A JoomPulse expõe o MCP em `https://joompulse.com/mcp` com OAuth padrão (PKCE, refresh token, escopo `mcp`) e aceita
**client metadata document**: o `client_id` é a URL de `docs/oauth-client.json`, servido pelo GitHub Pages deste repositório.
O login acontece uma vez no seu navegador; o refresh token é guardado criptografado em `data/token.enc` e renovado a cada
rodada pelo workflow.

## Custos e limites

- 27 × 2 consultas de descoberta + ~6 de acompanhamento + 3 de JoomPro (1×/dia) + ~14 de categorias (1×/mês) ≈ 60–80 chamadas por rodada.
- Tudo dentro da conta JoomPulse que você já paga. Se a JoomPulse limitar chamadas do MCP, reduza `DISCOVERY_*_LIMIT` ou a frequência do cron.
- GitHub Actions: ~3–5 min por rodada, dentro da cota gratuita.

Veja `SETUP_CLAUDE_CODE.md` para o passo a passo de ativação.
