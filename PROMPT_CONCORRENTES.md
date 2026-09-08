# Prompt: aba "Concorrentes" no Radar Safira

> Cole este texto inteiro numa sessão nova do Claude Code aberta na pasta do projeto
> (`C:\Users\joaoj\OneDrive\Área de Trabalho\radar-safira`), com o modelo que quiser
> (Opus 5 é suficiente). Escrito em 08/09/2026 pelo Claude da sessão anterior, depois de
> medir o que os dados atuais permitem. Trabalhe em português.

---

## 0. Antes de tudo

1. Leia `BRIEFING_ASSISTENTE.md` inteiro (onde o projeto mora, regras, como testar e
   publicar) e a seção "Onde o projeto mora" do `GUIA.md`. Este prompt não repete nada disso.
2. Regras que não se negociam, para lembrar: rotina diária com **zero tokens**; **uma coleta
   por vez** na JoomPulse (a sessão é única e o código de login vai para o telefone do sócio);
   ritmo de **2,5 s entre páginas**; **nunca inventar dado** (sem dado = "não coletado");
   nunca `run --fixtures` na pasta real; commit e `.\scripts\publicar.ps1` para publicar;
   toda mudança de comportamento registrada no `GUIA.md` em linguagem simples.
3. O João **não é programador**: explique cada passo em uma linha, mostre a tela antes de
   fazer coleta longa e avise antes de qualquer coisa que gaste tokens ou horas.

---

## 1. O que o João pediu (em suas palavras, organizado)

Ele quer avaliar se um produto "é bom de verdade" olhando **quem vende**:

a. **Na página do produto** (aba Oportunidades ML, função `mlProduto` em `docs/index.html`):
   - **"Outras variações do mesmo vendedor"**: se o vendedor tem outros anúncios do mesmo
     produto (cor, tamanho, kit), listar cada um com vendas por semana e preço, e responder
     "vendem tão bem quanto?". Para cada um, a leitura de margem provável já existente
     (`custoMaximo`: até quanto ele pode estar pagando para ganhar 20% e 10% no preço dele).
   - **"Outros vendedores / concorrentes" do mesmo produto, inclusive os que NÃO vendem**
     (zero vendas), para ele ver quantos tentam e quantos conseguem.

b. **Uma aba nova, "Concorrentes"**, que funcione como um **banco de dados de lojas**:
   - lista de lojas com: nome, **medalha** (MercadoLíder, Gold, Platinum, sem medalha),
     reputação, se usa Full, quantos anúncios, vendas e receita somadas, quantos produtos
     "bons" (semáforo verde) ela vende, link para a loja no Mercado Livre;
   - clicar na loja abre a **página da loja**: todos os anúncios dela que o radar conhece,
     como cada um performa (vendas, preço, score, semáforo), se o mesmo produto tem outros
     anúncios (variações) e como eles vendem, e um botão para abrir a página do produto.

Ele resumiu: "quero clicar lá e conseguir ver todos os produtos que aquele cara está
vendendo e como cada um está performando".

---

## 2. O que já existe e o que falta (medido em 08/09/2026, `docs/data.json`)

**Existe:**
- 2.225 produtos na rodada, **1.796 vendedores distintos**; 259 vendedores com 2+ anúncios
  no radar, 18 com 5+. Campo do vendedor no produto: só o **nome** (`s`). Não há id nem link
  da loja; o nome é o apelido do ML (ex.: `DARU20240421093708`), que funciona na URL pública
  `https://www.mercadolivre.com.br/perfil/<APELIDO>`.
- **297 anúncios têm "variação" do mesmo vendedor detectável por título** (mesmo vendedor,
  título parecido, mesma subcategoria), usando a função `parecidos(p, q)` já na página
  (ex.: MERCADOKIDS com kits de 4, 6 e 10 peças, vendas 150 / 160 / 1.237 por semana).
- Na página já estão prontos e podem ser reaproveitados: `mlProduto` (página do produto),
  `radarRow` (linha de anúncio com "paga até 20%/10%" e margem com o custo digitado),
  `parecidos` e `foraDoCatalogo` (títulos parecidos), `oportunidade`/`oppBadge` (semáforo),
  `custoMaximo`, `extrato`/`extratoHTML`, `showTab`, o padrão de seção/tabela/filtros das
  outras abas (`.row`, `.an`, `.fhead`, `.kv`, `.tile`, `.chips`, `csvOf`).

**Falta (e por quê):**
- **Medalha e reputação vêm vazias** em todos os 2.225 produtos (`md` e `rep` = null). O
  coletor do site lê a coluna 13 da tabela da JoomPulse (`vend_detalhe`, em
  `radar/browser.py`, lista `COLS` ~linha 115 e a extração ~linha 163) mas fixa
  `sellerMedal: None` e `sellerReputation: None` (~linha 316). **Primeiro passo prático:
  descobrir o que `vend_detalhe` traz** (rode uma coleta curta com `RADAR_L2_LIMIT=1`
  e `RADAR_ROOT` apontando para uma pasta temporária, ou `RADAR_BROWSER_HEADED=1` para olhar
  a tabela) e, se for a medalha/reputação, mapear para `sellerMedal`/`sellerReputation`
  (valores que a página já entende: `platinum`, `gold`, `silver`; ver `MEDAL` no JS).
- **Concorrentes sem venda não existem no banco**: `radar/engine.py` (`product_from_row`)
  descarta linhas sem `orderCount1w`, e a coleta pega só os **25 mais vendidos** de cada
  subcategoria. Consequência: 788 produtos de catálogo têm `bb > 1` (o site diz que há
  outros vendedores) mas os outros vendedores não foram coletados individualmente, e
  `riv` (outros anúncios do mesmo catálogo) está vazio em toda a rodada.
- Não há nada sobre a loja além do que aparece em cada anúncio (nome, Full, tipo).

**Fontes possíveis para o que falta** (decidir com o João, seção 5):
1. **JoomPulse, pelo navegador do coletor** (`radar/browser.py`; sessão única; 2,5 s):
   a busca por nome no modo "desagrupado" mostra um anúncio por vendedor do mesmo catálogo —
   `python -m radar fornecedor pesquisar` já faz isso para o catálogo da Flexx e guarda
   `outros` (ver `radar/fornecedor.py`). A página do produto na JoomPulse é
   `https://joompulse.com/dashboard/beginner-products/<MLB>`; confira o que ela mostra sobre
   vendedores antes de contar com ela.
2. **Mercado Livre público, sem login**: perfil do vendedor
   `https://www.mercadolivre.com.br/perfil/<APELIDO>` (medalha, reputação, vendas concluídas,
   tempo de loja) e página do catálogo `https://www.mercadolivre.com.br/p/<MLB do catálogo>`
   (todos os vendedores do catálogo, com preço, inclusive quem não vende). É HTML público, mas
   o ML bloqueia raspagem apressada: ritmo lento, poucos por dia, e parar ao primeiro 403/429.
3. **API do Mercado Livre com token de aplicativo** (client_credentials): `/products/{id}/items`
   (vendedores de um catálogo) e `/users/{id}` (medalha e reputação) são públicos;
   `/users/{id}/items/search` de terceiros responde 403. O projeto Nexo Seller do João já tem
   um aplicativo do ML com esse token — **pergunte ao João antes de reaproveitar a credencial**,
   e nunca a copie para o repositório (fica em `.secrets/`, fora do git).

---

## 3. Plano em duas fases (entregue a fase 1 inteira antes de começar a 2)

### Fase 1: só com o que já existe (página + uma mudança pequena no coletor)

1. **Aba "Concorrentes"** (botão em `nav.tabs`, `section#tab-conc`, mesma estrutura das
   outras abas). Em `computeAll`, monte `S.lojas`: agrupe `S.products` por vendedor (`s`),
   ignorando os produtos sintéticos do fornecedor (`i` começa com `forn:`). Para cada loja:
   nome, link do perfil, medalha e reputação (quando existirem), Full (quantos anúncios),
   tipos de anúncio, nº de anúncios, vendas/semana e /mês somadas, receita/mês somada, melhor
   score, contagem verde/amarelo/vermelho, categorias L1 em que vende, quantos anúncios são de
   catálogo e quantos "vendem fora do catálogo".
   Lista: busca por nome, ordenação (vendas, receita, nº de anúncios, verdes), filtros
   (medalha, só com 2+ anúncios, categoria L1), "Mostrar mais 50", CSV.
2. **Página da loja** (`lojaPagina(nome)`, no mesmo esquema `#conc-home` / `#conc-detail` que a
   aba ML usa com `#ml-home` / `#ml-detail`; Esc e "← Concorrentes" voltam mantendo a
   rolagem): cabeçalho (medalha, reputação, Full, link do perfil ML), tiles (anúncios, vendas,
   receita, verdes), e a lista de anúncios da loja com semáforo, preço, vendas, "paga até 20%"
   (`radarRow` serve), **agrupando variações**: quando dois ou mais anúncios da loja são
   `parecidos`, mostrar juntos com o texto "N anúncios deste produto em variações: vendem
   X, Y e Z por semana". Botão "Ver produto" abre `openProduct`.
3. **Na página do produto** (`mlProduto`): nova seção **"Do mesmo vendedor"** com (a) as
   variações (mesmo vendedor + `parecidos`) e a resposta "vendem tão bem quanto?" comparando
   vendas/semana com o anúncio aberto, cada uma com "paga até 20%/10%" no preço dela, e
   (b) os outros anúncios da loja no radar (só contagem e os 5 maiores, com link para a página
   da loja). Na seção "Mesmo produto no Mercado Livre", quando `p.c && p.bb > 1 && !p.riv.length`,
   deixar explícito: "o site diz que há N vendedores neste catálogo; os outros ainda não foram
   coletados (fase 2)".
4. **Coletor**: se `vend_detalhe` trouxer medalha/reputação, preencha `sellerMedal` e
   `sellerReputation` em `radar/browser.py`. Teste em pasta temporária, nunca no banco real.
   Só com a próxima rodada das 5h os campos passam a vir preenchidos; avise o João disso.
5. Testes: `python -m pytest -q` (6 verdes); página local com `python -m http.server 8090
   --directory docs` e um roteiro Playwright headless (Chromium limpo, nunca o perfil da
   JoomPulse) que abre a aba, uma loja e um produto e confere **zero erros de console**.
   Depois commit, `.\scripts\publicar.ps1`, seção nova no `GUIA.md` e uma linha no
   `BRIEFING_ASSISTENTE.md` (mapa de arquivos).

### Fase 2: coleta nova, com cautela

Objetivo: para os produtos que interessam (semáforo verde, e depois os amarelos), conhecer
**todos os vendedores do catálogo, inclusive os que não vendem**, e a **ficha de cada loja**
(medalha, reputação, vendas concluídas, tempo de loja, nº de anúncios, quando a fonte der).

1. Decidir a fonte com o João (seção 5). Comece pela mais barata e menos arriscada.
2. Guardar em `data/radar.db`, tabelas novas (`sellers`, `catalog_sellers`, com data da
   leitura), sem mexer nas tabelas existentes; exportar `docs/concorrentes.json` (novo
   arquivo, para não inchar `data.json`); a página lê os dois.
3. A coleta é **incremental e retomável** (lê o que falta, guarda a cada item, para e continua
   no dia seguinte), com **teto de tempo por dia** e roda **depois** da rodada das 5h, na
   mesma tarefa agendada (`scripts/rodada.ps1`), nunca em paralelo com ela.
4. Cada dado na tela diz de onde veio e quando foi lido; o que não foi lido aparece como
   "não coletado", nunca como zero.
5. Se a fonte for o site do ML: ritmo lento, poucos vendedores por dia, parar no primeiro
   bloqueio e avisar. Se for a API: token só em `.secrets/`, nunca no git.

---

## 4. Critérios de aceite da fase 1

- [ ] Aba "Concorrentes" com todas as lojas do radar, busca, ordenação, filtros e CSV.
- [ ] Página da loja com medalha/reputação (ou "não coletado"), tiles, anúncios com
      semáforo, variações agrupadas e botão para o produto; Esc volta.
- [ ] Página do produto com a seção "Do mesmo vendedor" (variações + outros da loja) e o aviso
      dos vendedores não coletados no catálogo.
- [ ] Coletor lendo medalha/reputação de `vend_detalhe`, se a coluna trouxer isso.
- [ ] Testes verdes, zero erros de console, publicado nos dois lugares, GUIA e briefing atualizados.

---

## 5. Perguntas para fazer ao João antes da fase 2 (uma de cada vez)

1. Fonte: JoomPulse pelo navegador (mesma sessão, mais lento) ou Mercado Livre público / API
   com token de aplicativo (mais completo, com risco de bloqueio ou de precisar de credencial)?
2. Pode reaproveitar a credencial de aplicativo do Nexo Seller, ou prefere criar uma só do radar?
3. Quantos produtos por dia entram na coleta de concorrentes (sugestão: os 50 verdes mais bem
   colocados, depois os amarelos)?
4. Aceita que os dados de loja tenham data de leitura e fiquem alguns dias desatualizados?

---

## 6. Legenda dos campos de `docs/data.json` (para não adivinhar)

`i` id do anúncio (MLB) · `p` id do catálogo (null em anúncio próprio) · `c` é de catálogo ·
`n` título · `img` foto · `s` vendedor (apelido) · `b` marca · `l1/l2/l3` categoria ·
`l2id` id da subcategoria · `md` medalha · `rep` reputação · `full` · `fs` frete grátis ·
`lt` tipo (`gold_pro` = Premium, `free`/`gold_special` = Clássico) · `pr` preço ·
`w` vendas/semana · `m` vendas/mês · `g` receita/mês · `rc` avaliações · `rr` nota ·
`d` dias no ar · `bb` vendedores no catálogo · `score` e `sd/sc/sg/sn` (componentes) ·
`rank/prev/best` · `status` · `first` · `runs` · `hist` · `riv` (outros anúncios do catálogo).
Na página, `computeAll` acrescenta `flags`, `opp` (semáforo), `fora` (anúncios próprios
parecidos), `_tk` (tokens do título) e `_cat` (categoria).
