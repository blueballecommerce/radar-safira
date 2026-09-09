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
link não abre (aí vale o link público do GitHub — mas veja o aviso abaixo).

> **As duas páginas não mostram a mesma coisa.** A da tailnet (`:8444`) serve a pasta
> `C:\Projeto - Radar Safira\docs` **do disco**: salvou o arquivo, mudou na hora. A pública do
> GitHub serve o **último commit enviado**. Enquanto houver trabalho sem commit, o celular (que
> normalmente abre o link público) fica vendo uma versão velha — sem nada do que foi feito depois
> do último `publicar.ps1`. Se algo "não aparece no celular", **é quase sempre isto**: confira
> `git status` antes de procurar bug.

> **A cópia do notebook (`OneDrive\Área de Trabalho\radar-safira`) pode estar suja e velha.**
> Em 08/09/2026 o `docs/index.html` dela estava 511 linhas atrás do que já estava publicado —
> faltavam 19 funções vivas (`oportunidade`, `oppBadge`, a página do produto inteira). Um `push`
> dali teria derrubado features que estavam no ar. Antes de publicar por aquela pasta, compare:
>
> ```bash
> git diff --stat origin/main -- docs/index.html   # muitas deleções = a cópia está atrás
> ```
>
> A fonte da verdade é `C:\Projeto - Radar Safira`.

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
- `OPP_*` — o **semáforo de oportunidade** de cada card (verde, amarelo, vermelho). A cor
  junta o score com a porta de entrada: produto de catálogo, quantos vendedores já dividem
  o mesmo anúncio (até 2 aberta, 3 a 5 disputada, 6 ou mais fechada); anúncio próprio, quantas
  avaliações o líder já tem (até 999 aberta, 1.000 a 9.999 disputada, 10.000 ou mais fechada).
  Entrada disputada tira 8 pontos e fechada tira 18, e **todo produto de catálogo perde 5 pontos**
  (`OPP_CATALOGO_TAXA`): no catálogo a disputa é com quem compra mais barato. Verde é 60 ou mais,
  amarelo de 45 a 59, vermelho abaixo de 45. Passe o mouse no selo para ver a conta.
- **Vende fora do catálogo?** — para cada produto de catálogo, o radar procura anúncios próprios
  parecidos (mesma subcategoria, título parecido, mesma marca quando há) entre os mais vendidos
  que ele leu. Se existem e vendem, o selo diz "Fora do catálogo: N anúncios próprios vendendo" e
  a ficha lista quais são, com link e vendas por semana; se não aparece nenhum, diz "nenhum entre
  os mais vendidos", ou seja, pelo que o radar viu só o catálogo vende aquele produto. O filtro
  "Catálogo que vende fora dele" mostra só os que têm essa prova. É uma noção, não uma certeza:
  o radar só lê os 25 mais vendidos de cada subcategoria. O CSV ganhou as colunas `oportunidade`,
  `entrada` e `fora_catalogo`.
- **Página do produto** — clique em qualquer produto de Oportunidades ML e ele abre uma página
  no mesmo desenho da ficha de fornecedor, só que invertida: como não temos custo, a referência
  é o preço do concorrente que mais vende. A tabela **Quanto posso pagar para ganhar** mostra o
  custo máximo no fornecedor para sobrar 10, 15 e 20% vendendo a esse preço, no Clássico e no
  Premium (clique num valor para levá-lo à calculadora). Em **Calcule com o seu custo**, digite
  o que o fornecedor cobra e veja o extrato completo; mude o preço para testar outra posição.
  Embaixo, **Mesmo produto** (os outros vendedores do catálogo) e **Parecidos** (título parecido
  na mesma subcategoria) mostram, para cada anúncio, até quanto dá para pagar para ganhar 20% e
  10% no preço dele e, quando você digitou um custo, a margem que sobra com o seu custo naquele
  preço. As premissas são as do Simulador de preço. Esc ou "← Oportunidades ML" volta à lista.

**Nos pesos do score** (`radar/config.py`):

```python
WEIGHTS = {"demand": 0.35, "competition": 0.25, "growth": 0.25, "novelty": 0.15}
```

---

## Fornecedores: como funciona e como fazer os próximos lotes

A aba **Fornecedores** mostra, por fornecedor, o custo por unidade, o tamanho da caixa
e o valor para fechar uma; e, para cada produto pesquisado, os catálogos do Mercado Livre
que vendem a mesma coisa — conferidos foto a foto.

Hoje há dois:

| Fornecedor | Catálogo | Regra de compra | De onde vem o preço |
|---|---|---|---|
| **Flexx Imports** | site WooCommerce, raspado | só caixa fechada | catálogo set/26 |
| **Logospan** | loja física, digitado da prateleira | aceita menos que a caixa | etiqueta da loja |

Em cada anúncio de catálogo aparece a tabela **de todos os vendedores que disputam
aquele anúncio**: quem está com a Compra Ganha, preço, reputação, tipo de anúncio, envio
e vendas no mês. Vale ler com atenção — num catálogo do Mercado Livre **só quem tem a
Compra Ganha vende**; os outros ficam zerados mesmo estando mais baratos. Por isso a
"média dos concorrentes" é calculada só com quem tem a Compra Ganha, e o mínimo e o
máximo mostram a faixa do catálogo inteiro.

Dentro de cada produto:

- **Quanto cobrar para ganhar 10 / 15 / 20 %** — preço de venda necessário, Clássico e
  Premium, já descontando comissão, custo fixo (ou frete grátis acima de R$ 79),
  imposto e embalagem. Clique num valor para levá-lo à calculadora.
- **Calcule o seu preço** — escolha o tipo de anúncio, digite o preço e veja o extrato
  completo e a comparação com a **média dos concorrentes iguais**. A leitura diz se há
  espaço (abaixo da média com lucro), se você está acima, ou se está no prejuízo.
- **Ver a foto da prateleira e conferir** — abre a foto original em tela cheia, com
  zoom (roda do mouse, botões + / −, duplo clique, ou pinça no celular) e arrasto.
  Embaixo da foto ficam os **traços de conferência**: a lista do que eu olhei para
  decidir se um anúncio é o mesmo produto (cor, formato, o que vem na caixa, idade).
  É o que torna o veredito auditável — você confere item a item em vez de acreditar.
  Só existe para fornecedor com foto de prateleira; na Flexx o botão abre a foto do
  catálogo deles.
- Em cada concorrente, o motivo do veredito vem rotulado: **Bate:**, **Diferença:**
  ou **Descartei porque:**.
- Em cada anúncio, passe o mouse em **Lucro líquido** para ver o extrato daquele preço.
  O botão **JoomPulse** abre um card com tudo que a JoomPulse trouxe do anúncio, aqui
  mesmo. Só **Mercado Livre ↗** leva para fora — para você conferir.

- **Kits** — anúncio que entrega mais de uma unidade do fornecedor ("Kit 2", "Kit 3 toucas",
  "2 varais") aparece marcado como **kit com N unidades**: o lucro usa custo × N e a média dos
  concorrentes é por unidade. A quantidade é registrada na conferência, junto com o veredito.
  **Regra quando não se sabe quantas unidades vêm na unidade do fornecedor:** o custo do
  anúncio é custo × a quantidade que o título do anúncio anuncia ("6 bombas" = 6 × custo),
  até a Flexx confirmar o conteúdo da caixa. Com a confirmação, a conta usa o conteúdo real.
- **Os produtos do fornecedor aparecem também na aba Oportunidades ML**, na mesma lista dos
  2.225 do radar, marcados com o selo **Fornecedor** e com custo e margem ao lado. Eles entram
  pelo mesmo score de 0 a 100 do radar (demanda, concorrência, categoria, novidade), calculado
  sobre o anúncio igual que mais vende — ninguém sai da lista para abrir vaga e nenhum sobe por
  ter fornecedor. O semáforo desconta margem baixa: abaixo de 20% perde pontos, no prejuízo
  perde 25. O filtro **Já tenho fornecedor** isola só eles.
- **Ranking (#)** — ordem de oportunidade dentro do catálogo. Quem tem lucro medido em
  anúncio igual vem primeiro (mesmo quando o lucro é negativo — é informação); depois
  quem só tem estimativa pela subcategoria; sem informação nenhuma fica no fim.
  Dentro de cada grupo a ordem é por pontos: **60 de margem + 40 de demanda** (margem cheia em
  35%, demanda cheia em 800 vendas/mês), para não pôr no topo produto de margem alta que
  ninguém compra. Passe o mouse no número da posição para ver a conta.
- **Categoria no Mercado Livre** — caminho completo da categoria, tendência (receita e
  vendas do mês contra o mês anterior), oportunidade e monopolização. Sem concorrente
  igual, mostra **o que a subcategoria está vendendo**, com o lucro calculado no preço
  deles e no seu custo.
- **Filtros** — catálogo de setembro, já pesquisados, com igual confirmado, margem boa,
  pouca concorrência, categoria em alta, anúncios novos, iniciante (pouco investimento).

As premissas de peso, reputação, imposto e embalagem são as do **Simulador de preço**:
mudou lá, tudo aqui recalcula.

### No celular

A página inteira cabe numa tela de celular, sem rolar para o lado. Quatro mudanças de
comportamento que valem saber:

- **Os números não somem mais.** Em tela pequena as linhas quebram para uma segunda
  faixa, embaixo do nome, em vez de esconder custo, caixa, preço, vendas e lucro.
  Antes eles sumiam abaixo de 980 px — justamente onde você olha o radar na frente
  da prateleira.
- **O cabeçalho é uma faixa fina.** Ele é fixo no topo; com as 7 abas quebrando em
  quatro linhas, chegava a 343 px numa tela de 812 — quase metade da tela grudada,
  com o conteúdo deslizando por baixo. Agora tem 117 px: as **abas rolam de lado**,
  numa linha só.
- **Os filtros também rolam de lado.** Os 11 chips empilhavam em 11 linhas (472 px de
  filtro antes do primeiro produto). Agora é uma tira de uma linha; arraste para ver
  os outros.
- **Os dados do produto ficam em uma coluna**, para o valor não quebrar no meio
  (`R$ 3.237,84` virava `R$ 3.237,` / `84`).

Para ver o extrato de um anúncio no celular, **toque na linha**: abre a ficha completa
da JoomPulse, com o extrato, os outros vendedores e o link para o Mercado Livre. O
balão que aparece ao passar o mouse é só do computador.

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

### Fornecedor sem site, como a Logospan

A Logospan é loja física: não há página para raspar. O catálogo é digitado a partir da
foto da etiqueta verde da prateleira — código, nome e preço — em
`data\fornecedor_logospan.json`, e a pesquisa do ML fica em
`data\fornecedor_logospan_busca.json`. Três diferenças em relação à Flexx:

- **A `url` é sintética**, no formato `logospan:<código>`. Ela continua sendo a chave do
  produto (é assim que o veredito acha o item), e a página troca o link "abrir no site"
  por "cód. 24689".
- **O campo `etiqueta`** guarda, em texto, o que estava escrito no papel. É a única fonte
  de verdade de um catálogo digitado à mão, então ele aparece na ficha do produto para
  você conferir contra a foto.
- **A categoria do ML vem dentro do próprio arquivo de busca**, não do
  `fornecedor_categorias.json`.

A foto do produto sai da própria foto de prateleira. Guarde a original em
`docs\img\logospan\originais\`, meça o recorte uma vez em `ITENS`, dentro de
`scripts\etiqueta.py`, e rode:

```powershell
python scripts\etiqueta.py prova     # folha de prova, para conferir os recortes
python scripts\etiqueta.py cartoes   # grava docs\img\logospan\<código>.jpg
```

Sai a miniatura (só o produto) e, em `cartoes\`, o cartão com a etiqueta verde recortada
ao lado dos dados. A caixa da etiqueta só precisa ser aproximada: o verde fluorescente é
o único da cena, então o script fecha o enquadramento sozinho e endireita a etiqueta
quando você informa o giro.

Para acrescentar outro fornecedor, basta um bloco novo em `FORNECEDORES`, dentro de
`radar\fornecedor_export.py`, apontando para os arquivos dele. Os vereditos de todos
moram no mesmo arquivo, sem risco de colisão: a chave começa pela `url`, que já carrega
o fornecedor.

---

## Pedir pesquisa pelo celular (aba "Pedir pesquisa")

Você está na loja, vê um produto e quer saber se vale. Tira a foto pela aba, escreve o que é
e quanto custa, e envia. O pedido entra na fila e a busca dos anúncios iguais no Mercado Livre
começa em seguida.

**Funciona sem sinal.** O pedido é gravado primeiro no próprio celular (no navegador) e só
depois entregue ao PC. Dá para fotografar a loja inteira no subsolo sem rede e, quando você
voltar para o alcance, tudo sobe sozinho — é só abrir a aba de novo.

### Ligar o coletor

O radar é um site estático: um formulário estático não tem para onde enviar. Quem recebe é o
`scripts\coletor.py`, um servidor pequeno que fica no PC:

```powershell
& ".\.venv\Scripts\python.exe" scripts\coletor.py
```

Ele escuta só em `127.0.0.1` — de fora ninguém chega nele direto. Quem publica na tailnet é o
Tailscale, e o coletor precisa ficar no **mesmo endereço da página**, no caminho `/api`
(uma vez só; depois disso fica valendo):

```powershell
tailscale serve --bg --https=8444 --set-path=/api http://127.0.0.1:8445
```

Mesmo endereço não é capricho: a página é `https`, e nenhum navegador deixa uma página `https`
falar com um servidor `http`. Pendurado em `/api`, os dois viram a mesma origem e o problema
some. É também por isso que **pela página pública do GitHub o envio nunca chega** — de lá o
pedido fica guardado no celular até você abrir pelo endereço da tailnet.

Para desfazer: `tailscale serve --https=8444 --set-path=/api off`.

### Onde o pedido cai

Cada pedido vira uma pasta em `data\pedidos\<id>\` (fora do git — tem foto e custo, não vai
para o site público):

| Arquivo | O que é |
|---|---|
| `pedido.json` | o que você preencheu, mais o estado |
| `foto-1.jpg`… | as fotos, já encolhidas pelo navegador para ~400 KB |
| `resultado.json` | os catálogos encontrados, no mesmo formato do `fornecedor_busca.json` |

O estado aparece na tela e também na linha de comando:

```powershell
& ".\.venv\Scripts\python.exe" -m radar pedidos fila        # o que já foi pedido
& ".\.venv\Scripts\python.exe" -m radar pedidos pesquisar   # roda a busca da fila agora
```

`na_fila` → `buscando` → `pronto` (ou `erro`, com o motivo no próprio pedido).

### O que a busca faz e o que ela não faz

Ela faz o mesmo que `radar fornecedor pesquisar` faz com o catálogo da Flexx: pergunta o nome à
JoomPulse e agrupa os anúncios por catálogo do Mercado Livre. **Ela não decide se o anúncio é o
mesmo produto** — isso é conferência foto a foto, e continua sendo feita olhando, com a lupa da
ficha. O que a fila entrega é a lista de candidatos, pronta para conferir.

Por isso o nome que você escreve importa: escreva como o **anúncio** seria ("arma lança dardos
com mira laser"), não como está na etiqueta da loja ("SUPER SHOT 24689").

### Se a busca não começa

O aviso amarelo no alto da aba diz o motivo. O mais comum é a sessão da JoomPulse ter expirado —
ela vale algumas semanas. O pedido não se perde: fica na fila e roda quando você resolver.

```powershell
& ".\.venv\Scripts\python.exe" -m radar login-browser
```

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


## Concorrentes — pesquisa inicial de 08/09/2026

A aba **Concorrentes**, ao lado de Fornecedores, começa com COMERCIALBRINKANDO e MERCADOKIDS,
encontrados respectivamente nos produtos de bolhas de sabão e conjuntos infantis do Radar.
Abra um vendedor para buscar seus produtos, filtrar categorias e ordenar por vendas, faturamento
ou preço do anúncio principal. Abra a ficha para ver características, variações e anúncios vinculados.
O link **Ver loja no Mercado Livre**, no alto de cada cartão, abre a loja real em outra aba.
Os endereços de COMERCIALBRINKANDO e MercadoKids foram conferidos em 08/09/2026.
Cada produto mostra a criação do anúncio principal e quantos dias decorreram até a consulta
(calendário de São Paulo). A ficha separa o principal dos demais anúncios, com a data de cada um.
A criação vem de `adPublishDate` da JoomPulse; `daysInAd` mede tempo ativo e não substitui a data.
Opções sem anúncio próprio identificado ficam sem data atribuída. O principal continua sendo
o de maior estimativa mensal de vendas, com desempate pelo indicador público acumulado.

Foram coletados todos os 208 anúncios ativos disponíveis na JoomPulse para esses vendedores
(147 + 61), com referência de 07/09/2026. Isso não garante a cobertura de toda a loja no Mercado Livre.
A contagem de produtos é diferente da contagem de anúncios: inclui variações identificadas e agrupa
anúncios com identidade comprovada. Título parecido sozinho não elimina um anúncio.
O principal é o de maior estimativa mensal; em empate, usa o indicador público acumulado e o ID.
Cores, tamanhos e quantidades diferentes ficam separados. Uma opção sem anúncio correspondente
na fonte fica sem preço/vendas confirmados; a venda do anúncio vizinho não é atribuída a ela.

As vendas e receitas mensais/semanais são **estimativas**, não totais oficiais nem janelas móveis.
As vendas concluídas em 365 dias no perfil vêm do dado de transações do Mercado Livre.
A fonte não informa vendas por variação nem a data da primeira venda. Tempo e avaliações de catálogo
podem ser compartilhados. O custo e a margem do concorrente não são públicos.

A pesquisa é uma fotografia desta data; esta aba não foi incluída na rotina automática das 5h.
Os registros originais e as características observadas ficam em **data/concorrentes/**.
Para reconstruir a tela a partir deles: `python -m radar.concorrentes`.
O resultado é **docs/concorrentes.json**; a interface está em **docs/concorrentes.js** e **docs/concorrentes.css**.
A integração no índice preserva as outras abas. O teste específico é
`python -m unittest discover -s tests -p test_concorrentes.py`.

