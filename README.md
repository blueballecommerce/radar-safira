# Radar Safira

Máquina de oportunidades do Mercado Livre: consulta a JoomPulse por conta própria (sem IA no meio),
mantém um ranking vivo com histórico e publica uma página estática. Roda sozinha no GitHub Actions,
às 8h e 15h (horário de Brasília), com custo zero de tokens.

```
JoomPulse (servidor MCP, OAuth)  ──►  radar/pulse.py (cliente MCP em Python)
                                          │  56 consultas CubeJS por rodada (+ categorias 1×/mês, JoomPro 1×/dia)
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

## Comandos

```bash
pip install -r requirements.txt
python -m radar login              # uma vez, no seu PC: abre o navegador e autoriza na JoomPulse
python -m radar check              # testa a conexão
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
