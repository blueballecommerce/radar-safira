# Radar Safira — guia de uso

Este é o manual do dia a dia. Se algo parar de funcionar, a resposta provavelmente
está aqui.

**A página:** https://blueballecommerce.github.io/radar-safira/
**A página na rede da empresa (Tailscale):** https://dojoo.tailce25ed.ts.net:8444/

---

## Onde o projeto mora (desde 08/09/2026)

O Radar segue o desenho do Nexo: **o Predator (a Nave do João, `dojoo` no Tailscale) é a casa
principal**, o notebook (DOJOÇO) é onde a coleta roda hoje e onde o código é escrito, e o GitHub
é a cópia pública.

| Onde | O que tem | Como chegar |
|---|---|---|
| **Predator** (`dojoo`, 100.101.114.106) | repositório central `C:\Repos\radar-safira.git` e a cópia de trabalho `C:\Projeto - Radar Safira`, com `.venv` e Chromium prontos; serve a página da tailnet pelo Tailscale Serve (porta 8444) | `ssh predator` deste notebook · página em https://dojoo.tailce25ed.ts.net:8444/ |
| **Notebook** (`dojooco`, este PC) | esta pasta; a tarefa "Radar Safira" das 5h roda aqui e, ao terminar, publica no GitHub **e** no Predator | — |
| **GitHub** | cópia pública do código e dos dados; página pública | https://github.com/blueballecommerce/radar-safira · https://blueballecommerce.github.io/radar-safira/ |

**Quem abre a página da tailnet:** qualquer aparelho ligado no Tailscale da empresa — os seus dois
PCs, o iPhone e o PC do Fernando. Não tem senha nem porta aberta na internet; fora do Tailscale o
link não abre (aí vale o link público do GitHub, que mostra a mesma coisa).

**Levar uma mudança para o Predator** (código, dados, vereditos): commite aqui e rode

```powershell
.\scripts\publicar.ps1           # GitHub + Predator
.\scripts\publicar.ps1 -Dados    # idem, e ainda copia pranchas, decisões e fornecedor*.json
```

Ele empurra para o GitHub e para o Predator, atualiza a cópia de trabalho de lá e mostra o commit
que ficou em cada lugar. Se o Predator tiver um commit que o notebook não tem, ele para e avisa,
em vez de misturar. Antes de mexer em qualquer arquivo, a regra é a do Nexo: olhe o estado do
Predator primeiro:

```powershell
ssh predator 'cd "/c/Projeto - Radar Safira" && git status -sb && git log --oneline -1'
```

**Trabalhando do Predator** (Claude Code aberto lá): a pasta é `C:\Projeto - Radar Safira`.
Commit lá, `git push central main`; depois, aqui no notebook, `git pull --ff-only predator main`.

**Para a coleta das 5h rodar no Predator** (ele fica ligado 24h; o notebook não): lá já tem
`.venv` e Chromium, falta só a sessão da JoomPulse, que não copia entre máquinas. No Predator:

```powershell
cd "C:\Projeto - Radar Safira"
& ".\.venv\Scripts\python.exe" -m radar login-browser    # abre o navegador; código pelo sócio
.\scripts\agendar.ps1                                    # cria a tarefa das 5h lá
```

e aqui no notebook `Disable-ScheduledTask -TaskName "Radar Safira"`. **Uma coleta por vez:** a
JoomPulse derruba a outra sessão. A partir daí a rodada guarda o commit no repositório central do
Predator sozinha, e o notebook puxa com `git pull --ff-only predator main`. Para a página pública
continuar atualizando, o Predator também precisa do GitHub: `git remote add origin
https://github.com/blueballecommerce/radar-safira.git` e um login do GitHub lá.

**Sócio (Fernando):** o PC dele está na mesma rede Tailscale (aparece conversando com o Predator),
então o link da tailnet deve abrir lá direto. Se não abrir, no painel do Tailscale
(https://login.tailscale.com/admin/machines), na máquina `dojoo`, use **Share** e mande o convite
para ele. O repositório é público para leitura; para ele também poder enviar mudanças, adicione o
GitHub dele em https://github.com/blueballecommerce/radar-safira/settings/access. A página **não**
está aberta para a internet inteira (Funnel desligado); se quiser isso, é um comando no Predator.

---

## O que acontece sozinho, todo dia às 5h

Você não precisa fazer nada. Esta é a sequência:

**1. O Windows dispara a tarefa "Radar Safira"** (5h00)
Se o computador estiver desligado nesse horário, ela roda assim que você ligar.

**2. O programa confere se ainda está logado na JoomPulse** (5h00, ~10 segundos)
Se a sessão tiver expirado, ele **para aqui** e escreve no log. Isso é de propósito:
melhor não ter rodada nova do que gravar uma rodada vazia por cima da boa.

**3. Abre o Chromium sem janela e lê a árvore de categorias** (5h01, ~6 minutos)
Abre uma categoria por vez no site, anota as subcategorias e os números de cada uma
(oportunidade, monopolização, receita, vendedores). São cerca de 390 subcategorias.

**4. Varre as subcategorias, uma a uma** (5h07 às 7h40, ~2h30)
Para cada subcategoria, abre a busca filtrada, clica em "Desagrupar catálogos",
troca para 100 itens por página e lê a tabela. Pega os 25 que mais vendem.
Se uma subcategoria travar, ele registra e segue para a próxima.

**5. Calcula o ranking** (7h40, segundos)
Junta os anúncios repetidos do mesmo catálogo (fica o que mais vende) e guarda os
demais como concorrentes — eles aparecem na ficha do produto, com link para o
Mercado Livre. Depois dá nota de 0 a 100 e ordena tudo.

**6. Guarda o histórico** (7h40)
Grava em `data/radar.db`. É assim que a página consegue mostrar "subiu 12 posições"
e "está no radar há 8 rodadas".

**7. Publica** (7h41, ~1 minuto)
Gera o `docs/data.json`, faz commit e envia para o GitHub. O site atualiza sozinho
em 1 ou 2 minutos.

**Custo: zero.** Nenhum token de IA é gasto. É só o seu computador e a sua conta
da JoomPulse.

---

## Como saber se funcionou

Abra a página e olhe o cabeçalho, no canto direito: ele mostra a data e a hora da
última rodada. Se disser hoje de manhã, deu certo.

Se quiser o detalhe, no Terminal:

```powershell
Get-Content data\rodada.log -Tail 20
```

Uma rodada boa termina com `=== rodada concluida ===`.

---

## Quando a sessão da JoomPulse expirar

Vai acontecer de tempos em tempos — semanas ou meses, não dias. O sintoma é a
página parar de atualizar, e no log aparecer:

```
SESSAO EXPIRADA - rode: .venv\Scripts\python.exe -m radar login-browser
```

A correção leva um minuto:

```powershell
cd "C:\Users\joaoj\OneDrive\Área de Trabalho\radar-safira"
& ".\.venv\Scripts\python.exe" -m radar login-browser
```

Abre uma janela do navegador. Digite o telefone, peça o código ao seu sócio, cole.
Quando o painel da JoomPulse aparecer, a janela fecha sozinha e está resolvido —
a rodada de amanhã volta ao normal.

Para conferir a sessão a qualquer momento, sem esperar a rodada:

```powershell
& ".\.venv\Scripts\python.exe" -m radar check-browser
```

---

## Comandos que você pode precisar

```powershell
# rodar agora, sem esperar as 5h
Start-ScheduledTask -TaskName "Radar Safira"

# ver quando é a próxima rodada
Get-ScheduledTaskInfo -TaskName "Radar Safira" | Select NextRunTime, LastTaskResult

# desligar o automático (a tarefa fica guardada, só não dispara)
Disable-ScheduledTask -TaskName "Radar Safira"
Enable-ScheduledTask  -TaskName "Radar Safira"

# mudar o horário: edite o 5am em scripts\agendar.ps1 e rode de novo
.\scripts\agendar.ps1
```

---

## Ajustes que talvez você queira

Todos são variáveis de ambiente — dá para testar uma vez sem mexer em arquivo:

| O que muda | Como | Efeito |
|---|---|---|
| Rodada mais rápida | `RADAR_L2_LIMIT=200` | só as 200 maiores subcategorias, ~1h30 |
| Mais produtos por subcategoria | `RADAR_L2_MAIN=40` | de 25 para 40, rodada mais longa |
| Caça dedicada a lançamentos | `RADAR_L2_NEW=10` | uma busca extra só de anúncios novos — **dobra o tempo** |
| Ir mais devagar | `RADAR_BROWSER_PAUSE=4` | menos risco de esbarrar no anti-bot deles |

Exemplo, para testar antes de adotar:

```powershell
$env:RADAR_L2_LIMIT = "200"
& ".\.venv\Scripts\python.exe" -m radar run --browser
```

Para valer todo dia, coloque a linha no começo de `scripts\rodada.ps1`.

**Na página** (`docs/index.html`, no começo do JavaScript):

- `NEW_MAX_DAYS = 30` — o que conta como "novo e vendendo"
- `HIDE_RULES` — os nichos escondidos hoje (suplementos, roupas). Apague a linha
  para trazer de volta, ou use o botão "Mostrar tudo" na própria página.

**Nos pesos do score** (`radar/config.py`):

```python
WEIGHTS = {"demand": 0.35, "competition": 0.25, "growth": 0.25, "novelty": 0.15}
```

---

## Fornecedores: como funciona e como fazer os próximos lotes

A aba **Fornecedores** mostra o catálogo da Flexx Imports (custo por unidade, tamanho
da caixa, valor para fechar a caixa) e, para cada produto pesquisado, os catálogos do
Mercado Livre que vendem a mesma coisa — conferidos foto a foto.

Dentro de cada produto:

- **Quanto cobrar para ganhar 10 / 15 / 20 %** — preço de venda necessário, Clássico e
  Premium, já descontando comissão, custo fixo (ou frete grátis acima de R$ 79),
  imposto e embalagem. Clique num valor para levá-lo à calculadora.
- **Calcule o seu preço** — escolha o tipo de anúncio, digite o preço e veja o extrato
  completo e a comparação com a **média dos concorrentes iguais**. A leitura diz se há
  espaço (abaixo da média com lucro), se você está acima, ou se está no prejuízo.
- Em cada anúncio, passe o mouse em **Lucro líquido** para ver o extrato daquele preço.
  O botão **JoomPulse** abre um card com tudo que a JoomPulse trouxe do anúncio, aqui
  mesmo. Só **Mercado Livre ↗** leva para fora — para você conferir.

- **Kits** — anúncio que entrega mais de uma unidade do fornecedor ("Kit 2", "Kit 3 toucas",
  "2 varais") aparece marcado como **kit com N unidades**: o lucro usa custo × N e a média dos
  concorrentes é por unidade. A quantidade é registrada na conferência, junto com o veredito.
  **Regra quando não se sabe quantas unidades vêm na unidade do fornecedor:** o custo do
  anúncio é custo × a quantidade que o título do anúncio anuncia ("6 bombas" = 6 × custo),
  até a Flexx confirmar o conteúdo da caixa. Com a confirmação, a conta usa o conteúdo real.
- **Ranking (#)** — ordem de oportunidade dentro do catálogo. Quem tem lucro medido em
  anúncio igual vem primeiro (mesmo quando o lucro é negativo — é informação); depois
  quem só tem estimativa pela subcategoria; sem informação nenhuma fica no fim.
- **Categoria no Mercado Livre** — caminho completo da categoria, tendência (receita e
  vendas do mês contra o mês anterior), oportunidade e monopolização. Sem concorrente
  igual, mostra **o que a subcategoria está vendendo**, com o lucro calculado no preço
  deles e no seu custo.
- **Filtros** — catálogo de setembro, já pesquisados, com igual confirmado, margem boa,
  pouca concorrência, categoria em alta, anúncios novos, iniciante (pouco investimento).

As premissas de peso, reputação, imposto e embalagem são as do **Simulador de preço**:
mudou lá, tudo aqui recalcula.

### Pesquisar mais produtos (lotes de 30 do catálogo)

O que entra na fila é o **catálogo de setembro** (PDF da Flexx com os 198 produtos em
estoque, guardado em `data\catalogo_set26.json`); o que está só no site fica de fora.
A ordem é a do PDF: cada rodada pega os próximos 30 ainda não pesquisados
(`RADAR_LOTE` muda o tamanho do lote).

```powershell
# 1. busca na JoomPulse pelo nome, agrupada por catálogo (grátis, ~1 min por produto)
$env:RADAR_LOTE = "30"
& ".\.venv\Scripts\python.exe" -m radar fornecedor pesquisar

# 2. pranchas de conferência: só o que ainda não foi conferido (grátis)
& ".\.venv\Scripts\python.exe" scripts\prancha.py

# 3. (depois da conferência) a categoria de cada produto na JoomPulse: caminho completo,
#    receita e vendas do mês com variação, e quem mais vende nela (grátis, ~40 s por produto)
& ".\.venv\Scripts\python.exe" -m radar fornecedor categorias

# 4. gera o docs\fornecedores.json que a página lê; depois é só publicar (git push)
& ".\.venv\Scripts\python.exe" -m radar.fornecedor_export
```

Entre o passo 2 e o 3 me chame: eu olho as pranchas em `data\pranchas\`, registro os
vereditos com `scripts\veredito.py` (as decisões ficam em `data\decisoes_*.json`) e
publico. Custo de referência: 15 produtos com ~140 catálogos ficaram em ~100 mil tokens;
14 pranchas do catálogo, ~60 mil.

Os vereditos ficam guardados por catálogo (foto + título), então refazer a pesquisa não
apaga o que já foi conferido. A leitura de categorias também é incremental: só lê o que
ainda não tem categoria, e uma categoria lida serve para todos os produtos dela.

---

## O que este radar ainda não faz

Vale saber, para você não procurar o que não existe:

- **Importação JoomPro está vazia.** O pareamento com fornecedores chineses fica
  numa tela separada do site, que a coleta ainda não percorre. A aba avisa isso e
  manda o link direto.
- **Shopee** é uma aba planejada, sem conteúdo.
- **Tempo de anúncio:** anúncio próprio tem o tempo dele mesmo; anúncio de catálogo
  mostra o tempo do catálogo, igual para todos os vendedores — é assim que o site
  informa.

---

## Se um dia a JoomPulse liberar acesso de programa

Hoje eles recusam clientes próprios (o `client_id` responde `invalid_client` e o
endpoint MCP devolve `401`), por isso a coleta é feita pelo navegador. Se um dia
fornecerem um `client_id`, o caminho antigo continua no código:

1. `RADAR_CLIENT_ID=<o que eles derem>`
2. religar o `schedule` em `.github/workflows/refresh.yml`
3. `python -m radar login` e `python -m radar run`

Aí a coleta volta a rodar na nuvem, sem depender do seu PC ligado.
