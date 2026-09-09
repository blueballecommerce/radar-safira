# Briefing do Radar Safira para um assistente (estado em 08/09/2026)

> Cole este texto inteiro na conversa com o assistente (ChatGPT ou outro) antes de pedir
> qualquer mudança no projeto. Ele diz o que o projeto é, onde cada coisa mora, o que
> verificar antes de mexer, onde mexer, como testar e como publicar.

---

## 0. Quem fala com você e como trabalhar

- Quem conversa com você é o **João** (Blue Ball Ecommerce). Ele **não é programador**: dê comandos
  prontos para colar no **PowerShell do notebook**, um passo por vez, e explique em uma linha o que
  cada comando faz. Ele cola a saída de volta para você ler.
- Fale em português. Não faça perguntas cuja resposta está nos arquivos: peça para ele rodar o
  comando que mostra a resposta.
- **Nunca peça senha, código de SMS ou token em texto.** Login na JoomPulse só pela janela do
  navegador que o próprio programa abre; o código chega no telefone do **sócio** (Fernando), então
  avise antes de qualquer coisa que force um novo login.
- O projeto também é mantido pelo Claude Code (na mesma máquina). Vocês dividem o mesmo repositório:
  a regra para os dois é **verificar antes, mudar no notebook, testar, publicar, registrar no GUIA.md**.

---

## 1. O que o projeto faz (em seis linhas)

1. Todo dia às **5h**, o notebook abre um Chromium invisível (Playwright) já logado na **JoomPulse**
   (site pago de dados do Mercado Livre) e lê ~390 subcategorias, ~2.200 anúncios. Nenhum modelo
   de IA participa: **a rotina diária custa zero tokens**.
2. `radar/engine.py` dá um **score de 0 a 100** a cada produto (demanda 35, pouca concorrência 25,
   categoria crescendo 25, novo e vendendo 15) e reordena o ranking inteiro.
3. O histórico fica em **`data/radar.db`** (SQLite): posição anterior, melhor posição, há quantas
   rodadas está no radar.
4. `radar/export.py` gera **`docs/data.json`**; **`docs/index.html`** é a página (sem build, JavaScript puro).
5. A aba **Fornecedores** cruza o catálogo da **Flexx Imports** (PDF de setembro, 198 produtos, e o
   site) com os anúncios do ML, com **conferência visual foto a foto** e cálculo de lucro por margem.
6. A rodada termina fazendo commit e publicando em **dois lugares**: GitHub (página pública) e o
   **Predator** (servidor da empresa, na rede Tailscale).

---

## 2. Onde o projeto mora (três lugares) e como se chega em cada um

| Lugar | O que é | Caminho / endereço |
|---|---|---|
| **Notebook** (`DoJoao`, na tailnet `dojooco`, 100.119.92.94) | Onde o João edita e onde a coleta das 5h roda hoje. É a máquina em que você manda os comandos. | `C:\Users\joaoj\OneDrive\Área de Trabalho\radar-safira` |
| **Predator** (`NavedoJao`, na tailnet `dojoo`, 100.101.114.106) | **Casa principal do projeto**, ligado 24h. Repositório central + cópia de trabalho + página servida na rede da empresa. Também roda o **Nexo Seller** (produção, porta 4000, PM2) — não tocar. | Central: `C:\Repos\radar-safira.git` · Cópia: `C:\Projeto - Radar Safira` · Página: https://dojoo.tailce25ed.ts.net:8444/ |
| **GitHub** | Cópia pública do código e dos dados; GitHub Pages serve a mesma página para quem não está no Tailscale. | https://github.com/blueballecommerce/radar-safira · https://blueballecommerce.github.io/radar-safira/ |

- Do notebook, o Predator se alcança por **`ssh predator`** (alias no `~/.ssh/config`, chave sem senha).
  A shell do outro lado é **bash**. `scp` trava e SMB não responde: arquivo vai por
  `ssh predator 'cat > destino' < arquivo` ou pelo `.\scripts\publicar.ps1 -Dados`.
- Remotes do git no notebook: `origin` = GitHub, `predator` = `ssh://predator/c/Repos/radar-safira.git`.
  Na cópia do Predator o remote se chama `central` (= `C:/Repos/radar-safira.git`).
- A página da tailnet é servida pelo **Tailscale Serve** (porta 8444, só dentro da rede). As portas
  443 e 8443 do Predator são do Nexo. **Nunca rode `tailscale serve reset`** — apagaria o Nexo do ar.
- O sócio (Fernando) tem o PC na mesma tailnet; ele abre a página pelo link do Predator ou pelo do GitHub.

---

## 3. O ciclo diário (o que acontece sozinho)

> **Desde 09/09/2026 o ciclo diário é a rotina pelo MCP:** duas sessões do Claude Code agendadas
> no Predator (5h `novos`, 15h `atualiza`) consultam a JoomPulse pelo conector MCP e o script
> `radar/mcp.py` ingere, roda a rodada e publica. Passo a passo em `ROTINA_MCP.md`; explicação
> para o João no `GUIA.md`, seção "O que acontece sozinho". A tarefa do notebook descrita abaixo
> ficou como plano B e deve permanecer **desligada** enquanto a rotina pelo MCP estiver ativa.

`scripts\rodada.ps1`, disparado pela **Tarefa Agendada do Windows "Radar Safira"** (5h, no notebook):

1. `python -m radar check-browser` — se a sessão da JoomPulse expirou, **para** e escreve
   `SESSAO EXPIRADA` no log (de propósito: melhor sem rodada do que rodada vazia).
2. `python -m radar run --browser` — ~2h30: árvore de categorias, varredura das subcategorias
   (25 mais vendidos de cada), score, histórico, `docs/data.json`.
3. `git add data/radar.db docs/data.json` + commit com autor `radar-bot` + `git push origin main`
   (GitHub Pages atualiza em 1–2 min).
4. `scripts\publicar.ps1 -SoPredator` — leva o mesmo commit para o Predator e atualiza a cópia de
   lá (só fast-forward). Se o Predator estiver desligado, a rodada não falha: fica um AVISO no log.

Log: **`data\rodada.log`**. Uma rodada boa termina com `=== rodada concluida ===`.
Exemplo real: em 08/09/2026 o log parou em `=== rodada iniciada ===` e o banco ficou com uma rodada
nº 2 em `running` sem produtos — o processo morreu sem mensagem. Isso não estraga o ranking (o
código só compara rodadas com `status='ok'`), e a solução foi `git checkout -- data/radar.db`.

---

## 4. Mapa dos arquivos: o que é cada um, quando mexer, como conferir

### Código Python (`radar/`)

| Arquivo | O que faz | Mexer quando… | Como conferir |
|---|---|---|---|
| `config.py` | **Todas as regras ajustáveis**: pastas (`RADAR_ROOT`), categorias L1, limites de coleta, `TOP_N=300`, `WATCH_RUNS=28`, `DROP_AFTER_ZERO_SALES_RUNS=2`, `WEIGHTS` (pesos do score), `NEW_LISTING_MAX_DAYS=30`. Variáveis de ambiente `RADAR_*` sobrescrevem. | quiser mudar pesos, janelas, limites | `python -m pytest -q` e uma rodada de teste (seção 5) |
| `engine.py` | Normalização, dedupe por catálogo, **fórmula do score** (`Scorer.score`), ranking | mudar a lógica da nota | idem; os testes `test_normalize_dedupe_and_score` e `test_rank_reorders…` cobrem isso |
| `run.py` | Orquestra a rodada: coleta → ranking → histórico → export. `FixtureSource` lê JSONs locais (`--fixtures`). Status `active / watching / candidate / dropped`. | mudar o ciclo de vida de um produto | idem |
| `db.py` | SQLite: tabelas `runs`, `products`, `product_runs`, `categories`, `joompro`, `meta`. Só rodadas `status='ok'` contam como "anterior". | mudar o que fica guardado | `test_two_runs_history` |
| `export.py` | Gera `docs/data.json` (o contrato com a página) | a página precisar de um campo novo | abrir a página local (seção 5) |
| `browser.py` | **O coletor** (Playwright). Perfil em `.secrets/browser-profile`. Pausa `RADAR_BROWSER_PAUSE=2.5` s entre páginas (menos que isso dá `429 bot.limit_reached`). `RADAR_L2_LIMIT` (0 = todas), `RADAR_L2_MAIN=25`, `RADAR_L2_NEW=0`, `RADAR_EXPAND_BUDGET=150`, `RADAR_BROWSER_HEADED=1` (mostra a janela). | o site da JoomPulse mudar de layout, ou para ajustar velocidade | `python -m radar check-browser` (10 s) e uma rodada curta com `RADAR_L2_LIMIT=5` |
| `fornecedor.py` | Catálogo da Flexx: `coletar` (site), `cruzar` (candidatos), `pesquisar` (busca na JoomPulse por nome, lotes de `RADAR_LOTE=30`; `RADAR_REFAZER="nome a,nome b"` refaz itens), `categorias` (categoria de cada produto na JoomPulse) | adicionar lote, refazer busca | ver contagens em `data/fornecedor_busca.json` |
| `fornecedor_export.py` | Junta `fornecedor.json` + `fornecedor_busca.json` + `fornecedor_veredito.json` e gera `docs/fornecedores.json` | depois de qualquer veredito ou pesquisa nova | abrir a aba Fornecedores na página local |
| `__main__.py` | A linha de comando (`python -m radar …`, ver seção 8) | novo subcomando | `python -m radar --help` |
| `pulse.py`, `queries.py`, `auth.py` | Caminho antigo por MCP/OAuth. **Beco sem saída**: a JoomPulse recusa clientes de terceiros (`invalid_client`, `/mcp` = 401). Fica no código só por precaução. | **não mexer, não tentar de novo** | — |

### Scripts (`scripts/`)

| Arquivo | O que faz |
|---|---|
| `rodada.ps1` | A rodada das 5h (seção 3). Para mudar limites por padrão, ponha `$env:RADAR_…` no começo dele. |
| `agendar.ps1` | Cria/atualiza a Tarefa Agendada "Radar Safira" (5h). Mudou o horário? edite `5am` e rode de novo. |
| `publicar.ps1` | **Publica**: `git push origin` + `git push predator` + `git pull --ff-only` na cópia do Predator. Mostra o commit de cada lado antes e depois. `-SoPredator` pula o GitHub; `-Dados` leva também os arquivos fora do git (pranchas, decisões, fornecedor*.json, catálogo). |
| `prancha.py` | Monta as **pranchas de conferência** (`data\pranchas\<n>.jpg` + `indice.json`): produto do fornecedor à esquerda, anúncios da JoomPulse numerados à direita. |
| `veredito.py` | Registra a conferência visual: lê um JSON `[{"n":1,"pos":2,"veredito":"igual","obs":"…","qtd":2}]` e grava em `data/fornecedor_veredito.json` (chave por catálogo: foto + título). |
| `columnar_to_fixtures.py`, `make_client_metadata.py` | Do caminho MCP/OAuth. Não usar. |

### Página (`docs/`) — servida pelo GitHub Pages e pelo Predator

| Arquivo | O que é |
|---|---|
| `index.html` (~1.500 linhas) | **A página inteira**: abas Oportunidades ML, Categorias em alta, Importação JoomPro (vazia), Simulador de preço, Fornecedores, Shopee (em breve). Constantes no começo do JavaScript, perto da linha 556: `NEW_MAX_DAYS = 30` (o que é "novo"), `HIDE_RULES` (nichos escondidos; botão "Mostrar tudo") e `OPP_*` (semáforo de oportunidade de cada card: limiares 60/45, penalidades da porta de entrada, taxa de 5 pontos para produto de catálogo e a verificação "vende fora do catálogo?" por anúncios próprios de título parecido na mesma subcategoria; regra explicada na legenda da página e no GUIA). A página do produto (`mlProduto`, `custoMaximo`) inverte a ficha de fornecedor: custo máximo para ganhar 10/15/20% vendendo ao preço do concorrente, calculadora com o custo digitado, e as listas "mesmo produto" e "parecidos" com a mesma conta em cada preço. Busca `data.json` na linha ~1185. Premissas do Simulador (peso, reputação, imposto, embalagem, ads) alimentam também os lucros da aba Fornecedores (~linha 1265). |
| `oportunidades.js`, `oportunidades.css`, `oportunidades-ficha.js` | Aba Oportunidade de fornecedores: Etapa 1, cartões compactos que abrem a ficha e comparação de fotos por anúncio, contas compartilhadas, menos de 45 dias desde a criação e 1 venda/dia. Integração/publicação: `scripts/integrar_oportunidades.py` e `scripts/publicar_oportunidades.py`. |
| `data.json` (~1,8 MB) | Saída da rodada. **Gerado**, não editar à mão. |
| `fornecedores.json` (~2,6 MB) | Saída de `radar.fornecedor_export`. **Gerado**, não editar à mão. |
| `img/catalogo/*.jpg`, `img/flexx-logo.webp` | Fotos do catálogo de setembro (recortadas do PDF). |
| `oauth-client.json` | Do caminho OAuth morto. Ignorar. |

### Dados (`data/`)

| Arquivo | Versionado? | O que é |
|---|---|---|
| `radar.db` | sim | O banco vivo (histórico do radar). Só a rodada escreve nele. |
| `radar.db.full` | sim | Cópia de segurança antiga do banco (commit f618011). O código não a lê. |
| `fornecedor_busca.v1.json`, `.v2.json` | sim | Versões antigas da busca de fornecedores, guardadas como referência. |
| `fornecedor.json` | não | Catálogo raspado do site da Flexx. |
| `catalogo_set26.json` | não | O PDF de setembro da Flexx em JSON (198 produtos) — é a **fila** dos lotes. |
| `fornecedor_busca.json` | não | O que a JoomPulse devolveu para cada produto pesquisado (194 produtos hoje). |
| `fornecedor_categorias.json` | não | Categoria, tendência e quem mais vende, por produto. |
| `fornecedor_veredito.json` | não | A conferência visual: 3.901 vereditos por catálogo, com `qtd` (unidades por anúncio). |
| `decisoes_*.json` | não | As decisões de cada sessão de conferência, como foram registradas (entrada do `veredito.py`). |
| `pranchas/` | não | 170 imagens de conferência + `indice.json`. |
| `rodada.log`, `*.log` | não | Logs. |
| `pares.json` | não | Candidatos do `fornecedor cruzar` (caminho antigo). |

Os arquivos "não versionados" existem no notebook e foram copiados para o Predator em 08/09/2026.
Se mudarem, `.\scripts\publicar.ps1 -Dados` leva de novo.

### Segredos e o resto

| Item | O que é |
|---|---|
| `.secrets/browser-profile/` (~700 MB) | A sessão logada da JoomPulse. **Não copiar para outra máquina** (os cookies são presos ao usuário do Windows); em outra máquina é preciso `login-browser` de novo. Fora do git. |
| `.secrets/token.json` | Token do caminho OAuth morto. Fora do git. |
| `tests/` | 6 testes (`python -m pytest -q`), isolados em pasta temporária via `RADAR_ROOT`. `tests/fixtures/` tem dados reais de 05/09/2026 para rodada sem rede. |
| `.github/workflows/refresh.yml` | **Desligado** (só `workflow_dispatch`). Dependia do MCP. Não religar. |
| `GUIA.md` | **O manual do João.** Toda mudança de comportamento tem que ser registrada aqui, em linguagem simples. |
| `README.md` | Arquitetura, score, comandos. |
| `SETUP_CLAUDE_CODE.md`, `PEDIDO_JOOMPULSE.md` | Históricos. O pedido à JoomPulse **não deve ser enviado** (decisão do João). |
| `requirements.txt`, `requirements-dev.txt`, `requirements-lock.txt` | Dependências; o lock tem as versões exatas que funcionam (Python 3.12 no notebook, 3.13 no Predator). |

---

## 5. Passo a passo para qualquer mudança

**Passo 1 — Verificar antes de mexer** (no notebook, na pasta do projeto):

```powershell
cd "C:\Users\joaoj\OneDrive\Área de Trabalho\radar-safira"
git status -sb                       # tem que estar limpo e "main...origin/main"
git log --oneline -3                 # último commit aqui
Get-Content data\rodada.log -Tail 5  # a última rodada terminou bem?
tasklist | findstr /i python         # vazio = nenhuma coleta rodando agora
ssh predator 'cd "/c/Projeto - Radar Safira" && git status -sb && git log --oneline -1'   # o Predator está no mesmo commit?
```

Se o Predator tiver um commit que o notebook não tem (alguém trabalhou lá), traga primeiro:
`git pull --ff-only predator main`. Se `git status` mostrar arquivos mexidos, pergunte ao João
antes de sobrescrever qualquer coisa.

**Passo 2 — Mudar no notebook.** Código em `radar/`, página em `docs/index.html`, regras em
`radar/config.py`, scripts em `scripts/`. Nunca editar direto na cópia do Predator (a não ser que
o João esteja trabalhando de lá — aí o fluxo inverte: commit lá, `git push central main`, e no
notebook `git pull --ff-only predator main`).

**Passo 3 — Testar sem tocar no banco real.**

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q          # esperado: 6 passed
```

Rodada completa com dados locais, numa pasta temporária (o banco e o `data.json` reais ficam intocados):

```powershell
$env:RADAR_ROOT = Join-Path $env:TEMP "radar-teste"
New-Item -ItemType Directory -Force "$env:RADAR_ROOT\data", "$env:RADAR_ROOT\docs" | Out-Null
& ".\.venv\Scripts\python.exe" -m radar run --fixtures tests\fixtures
Remove-Item Env:RADAR_ROOT
```

Esperado: JSON final com `products` ≈ 1999 e `export` apontando para a pasta temporária.
**Nunca rode `run --fixtures` sem `RADAR_ROOT`**: ele sobrescreveria `data/radar.db` e `docs/data.json`
com dados de teste (já aconteceu; commit 339c3b8 restaurou o banco).

Página local (para ver `index.html` com os dados de verdade):

```powershell
& ".\.venv\Scripts\python.exe" -m http.server 8080 --directory docs
```

e abrir http://localhost:8080/ no navegador (Ctrl+C no PowerShell para parar).

Para testar o coletor de verdade sem esperar 2h30: `$env:RADAR_L2_LIMIT = "5"` antes de
`python -m radar run --browser` — **mas isso grava uma rodada real no banco**; só faça com o João
ciente, e depois `git checkout -- data/radar.db docs/data.json` se for para descartar.

**Passo 4 — Commitar e publicar.**

```powershell
git add -A
git commit -m "o que mudou, em uma linha"
.\scripts\publicar.ps1            # acrescente -Dados se mexeu em pranchas/decisões/fornecedor*.json
```

Conferir: o script mostra `Predator: <commit> (depois)` igual ao `Notebook:`; a página da tailnet
responde em https://dojoo.tailce25ed.ts.net:8444/ e a pública em 1–2 min.

**Passo 5 — Registrar.** Toda mudança de comportamento vai para o `GUIA.md` (o manual do João),
na seção que corresponde, em linguagem simples. Se mudou a lista de arquivos ou o fluxo, atualize
este briefing também.

---

## 6. Regras que não podem ser quebradas

1. **Uma coleta por vez.** A JoomPulse aceita uma sessão por conta: abrir dois coletores (ou o Chrome
   do João logado na JoomPulse junto com o coletor) derruba a sessão e força novo login (código no
   telefone do sócio). Antes de `run --browser`, `fornecedor pesquisar` ou `fornecedor categorias`,
   confira `tasklist | findstr /i python`.
2. **Tokens só onde o João aprovou.** A rotina pelo MCP (5h/15h) gasta tokens de propósito — é o
   Claude que faz as consultas —, mas o dado não passa pelo modelo (resposta grande vira arquivo,
   ver `radar/mcp.py`). Fora disso, nada de IA na coleta; ler pranchas de fotos é a exceção
   aceita (~4–5 mil tokens por prancha), sempre avisando antes.
3. **Não contatar a JoomPulse** em nome do João e **não tentar o caminho OAuth com client_id
   próprio de novo** (`pulse.py`/`auth.py`). O conector MCP **do Claude** é o caminho oficial
   desde 09/09/2026 — é ele que a rotina usa.
4. **`git pull` no Predator só com `--ff-only`**; nunca `tailscale serve reset`; nunca mexer no Nexo
   (PM2, portas 4000/4001, 443, 8443).
5. **Nunca `run --fixtures` na pasta real** (só com `RADAR_ROOT`). Nunca commitar `.secrets/`.
6. **Funnel desligado**: a página da tailnet não é pública. Abrir para a internet é decisão do João.
7. **Regras de negócio da aba Fornecedores:** kit conta unidades (anúncio "6 bombas" = custo × 6 até
   a Flexx confirmar o conteúdo da caixa; nome do fornecedor com quantidade — "Kit com 50" — vale como
   confirmação); ranking = lucro medido primeiro, mesmo negativo, "sem informação" por último; margem
   zero de verdade é informação.
8. **Na página, só o botão "Mercado Livre ↗" leva para fora**; detalhes da JoomPulse abrem em card.
9. **Nunca inventar dado.** Falta número → mostra que falta.
10. Avisar o João antes de qualquer coisa cara (tokens), lenta (horas) ou que force re-login.

---

## 7. Ajustes comuns: onde ficam

| Quero mudar… | Onde |
|---|---|
| Pesos do score | `radar/config.py` → `WEIGHTS = {"demand": 0.35, "competition": 0.25, "growth": 0.25, "novelty": 0.15}` |
| Quantos ficam "ativos", tempo em observação, queda por falta de venda | `radar/config.py` → `TOP_N`, `WATCH_RUNS`, `DROP_AFTER_ZERO_SALES_RUNS` |
| O que conta como "novo" | dois lugares: `radar/config.py` → `NEW_LISTING_MAX_DAYS` (score) e `docs/index.html` → `NEW_MAX_DAYS` (exibição) |
| Nichos escondidos na lista | `docs/index.html` → `HIDE_RULES` |
| Velocidade/tamanho da rodada | `$env:RADAR_L2_LIMIT`, `RADAR_L2_MAIN`, `RADAR_L2_NEW`, `RADAR_BROWSER_PAUSE` no começo de `scripts/rodada.ps1` |
| Horário da rodada | `scripts/agendar.ps1` (`-At 5am`) e rodar de novo |
| Premissas de preço (comissão, imposto, embalagem, frete, ads) | aba **Simulador de preço** da própria página (alimenta a aba Fornecedores); código perto da linha 1265 de `index.html` |
| Próximo lote de fornecedores | sequência do GUIA.md: `fornecedor pesquisar` → `scripts\prancha.py` → conferência + `scripts\veredito.py` → `fornecedor categorias` → `python -m radar.fornecedor_export` → commit → `publicar.ps1 -Dados` |
| Categorias L1 do caminho MCP | `radar/config.py` → `L1_CATEGORIES` (o coletor pelo site lê a árvore do próprio site, não usa esta lista) |

---

## 8. Comandos de referência

```powershell
& ".\.venv\Scripts\python.exe" -m radar check-browser        # a sessão da JoomPulse ainda vale? (10 s)
& ".\.venv\Scripts\python.exe" -m radar login-browser        # novo login (abre janela; código vai para o sócio)
& ".\.venv\Scripts\python.exe" -m radar run --browser        # rodada completa (~2h30)
& ".\.venv\Scripts\python.exe" -m radar export               # só regenera docs/data.json a partir do banco
& ".\.venv\Scripts\python.exe" -m radar fornecedor pesquisar # próximo lote (RADAR_LOTE=30)
& ".\.venv\Scripts\python.exe" -m radar fornecedor categorias
& ".\.venv\Scripts\python.exe" -m radar.fornecedor_export    # gera docs/fornecedores.json
& ".\.venv\Scripts\python.exe" scripts\prancha.py            # pranchas do que falta conferir
& ".\.venv\Scripts\python.exe" scripts\veredito.py data\decisoes_AAAA-MM-DD.json
Start-ScheduledTask -TaskName "Radar Safira"                 # rodar a rodada agora
Get-ScheduledTaskInfo -TaskName "Radar Safira" | Select NextRunTime, LastTaskResult
.\scripts\publicar.ps1 [-SoPredator] [-Dados]                # publicar
ssh predator 'cd "/c/Projeto - Radar Safira" && git status -sb && git log --oneline -1'
```

---

## 9. Diagnóstico rápido

| Sintoma | Onde olhar | Saída típica |
|---|---|---|
| Página com data velha | `Get-Content data\rodada.log -Tail 20`; `Get-ScheduledTaskInfo -TaskName "Radar Safira"` | `SESSAO EXPIRADA` → `login-browser`; log parado em "iniciada" → processo morreu, ver se o PC dormiu às 5h; `LastTaskResult` ≠ 0 |
| `429 bot.limit_reached` no log | ritmo alto demais | aumentar `RADAR_BROWSER_PAUSE` (ex.: 4) |
| Página da tailnet não abre | `tailscale status` (notebook) e `ssh predator '"/c/Program Files/Tailscale/tailscale.exe" serve status'` | precisa estar logado no Tailscale; a linha `:8444 … path C:\Projeto - Radar Safira\docs` tem que existir |
| Predator não atualiza | saída do `publicar.ps1` | "nao consegui falar com o Predator" = Predator desligado ou Tailscale fora; "nao aceitou fast-forward" = commit lá que falta aqui |
| GitHub Pages velho | `git log origin/main -1` vs `git log -1` | falta `git push origin main` (ou o Pages ainda está publicando, espere 2 min) |
| Aba Fornecedores sem produto novo | `docs/fornecedores.json` não foi regenerado | `python -m radar.fornecedor_export` + commit + publicar |
| Banco com rodada `running` pendurada | `python -c "import sqlite3;print(sqlite3.connect('data/radar.db').execute('select id,status from runs order by id desc limit 3').fetchall())"` | rodada morreu; não atrapalha o ranking; `git checkout -- data/radar.db` se não houver mais nada a salvar |

---

## 10. Estado em 08/09/2026

- Última rodada boa: **nº 1, 07/09/2026 05:39** (2.225 produtos, 388 subcategorias). A de 08/09 morreu
  sem mensagem; próxima em 09/09 às 5h.
- Fornecedores: 5 lotes de 30 do catálogo de setembro pesquisados e conferidos (194 produtos com busca,
  3.901 vereditos); a fila continua pelo `catalogo_set26.json`.
- Predator: cópia pronta (Python 3.13, Chromium, testes verdes, dados copiados) e página no ar na
  tailnet; **sem sessão da JoomPulse** — a coleta continua no notebook até alguém fazer `login-browser`
  no Predator e mover a tarefa (GUIA.md, seção "Onde o projeto mora").
- Workflow do GitHub Actions desligado; caminho OAuth/MCP morto.
