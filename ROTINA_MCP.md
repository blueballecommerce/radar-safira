# Rotina do Radar pelo MCP — o que a sessão agendada faz

Este arquivo é lido pela sessão do Claude Code que roda sozinha **às 5h** (modo `novos`: traz
produtos novos e reordena o ranking) e **às 15h** (modo `atualiza`: relê tudo que já está no
radar — vendas, dias no ar, vendedores no catálogo, categoria — e reordena). Ele existe para a
sessão não precisar pensar: é seguir os passos. Quem quiser entender o desenho lê `GUIA.md`
(seção "O que acontece sozinho") e `radar/mcp.py`.

## Regras

- Trabalhe **sempre** em `C:\Projeto - Radar Safira`. O atalho `~/.claude/radar-mcp.cmd` já
  entra nessa pasta e chama `python -m radar mcp …` com o Python certo (o `.venv`).
- Não peça confirmação, não pare para perguntar, não edite código nem a página. Se uma
  consulta falhar, tente de novo **uma** vez; se falhar de novo, siga para a próxima e cite no
  resumo final. Nunca rode `run --fixtures` na mão, nunca `tailscale serve reset`.
- A ferramenta de consulta é **`query_cubejs_meli`** do conector JoomPulse (MCP). Mande a
  consulta exatamente como o `plano` imprime, trocando só o que ele manda trocar
  (`{L1}` pelo nome exato da categoria, com acentos).
- Faça as consultas em grupos de **4 a 6 por turno** (chamadas paralelas na mesma mensagem) e
  ingira o grupo inteiro com um único comando `ingerir`. Não leia o conteúdo dos arquivos de
  resposta: o script lê.

## Passo a passo

1. Abra o plano do dia:

       ~/.claude/radar-mcp.cmd plano novos --reiniciar        (5h)
       ~/.claude/radar-mcp.cmd plano atualiza --reiniciar     (15h)

   Ele imprime a lista do que falta (`top/<slug>`, `new/<slug>`, `track/<n>`, `cat/…`), o nome
   exato de cada categoria e o modelo JSON de cada tipo de consulta.

2. Para cada passo listado, chame a ferramenta. Uma resposta cheia (100 linhas, ~60 KB) **não
   entra no contexto**: a ferramenta responde algo como
   `result (61.234 characters) exceeds maximum allowed tokens. Output has been saved to C:\…\tool-results\mcp-…-query_cubejs_meli-<número>.txt`.
   Guarde esse caminho e ingira:

       ~/.claude/radar-mcp.cmd ingerir "top/agro=C:\…\mcp-…-123.txt" "new/agro=C:\…\mcp-…-124.txt"

   - Se a resposta vier **inteira no contexto** (poucas linhas), grave o JSON exatamente como
     veio, com a ferramenta Write, em `C:\Projeto - Radar Safira\data\live\inbox\<passo>.json`
     (troque a `/` do passo por `_`, ex.: `new_agro.json`) e ingira esse arquivo do mesmo jeito.
   - `OK passo: N linhas -> arquivo` é sucesso. `ERRO passo: …` quer dizer que o arquivo não
     é dessa consulta (categoria trocada, `top` no lugar de `new`): refaça a consulta certa e
     ingira de novo. Um `aviso` (poucas linhas, ids que não voltaram) é só informação.

3. Quando a descoberta terminar, rode `plano novos` de novo: agora ele imprime os lotes de
   acompanhamento (`track/1`, `track/2`, …) **com a consulta já pronta**, ids incluídos. Faça e
   ingira igual. Em `atualiza` não há descoberta: o primeiro `plano` já traz os lotes.

4. Feche a rodada:

       ~/.claude/radar-mcp.cmd fechar novos        (ou  fechar atualiza)

   Ele confere se nada ficou faltando, roda o ranking (score, dedupe, histórico), gera
   `docs/data.json`, faz commit de `data/radar.db` + `docs/data.json` e publica no GitHub
   Pages (`origin`) e no repositório central (`central`). A página da tailnet
   (https://dojoo.tailce25ed.ts.net:8444/) lê o disco e já está atualizada. A saída é o resumo.

5. Termine respondendo em português, curto (no máximo 10 linhas): o resumo que o `fechar`
   imprimiu (rodada, quantos no ranking, quantos entraram, top 5, novos com maior score, quem
   mais subiu), a linha de publicação, e as consultas que falharam, se alguma.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| `sem rodada aberta` | rode `plano <modo>` primeiro |
| `fechar` diz que faltam consultas | rode `plano <modo>` (sem `--reiniciar`) e complete o que ele lista |
| a consulta devolve erro da JoomPulse (`not found for path`, `too large`) | tente uma vez mais; se persistir, pule o passo e cite no resumo — não invente colunas nem reduza o `limit` |
| `AVISO: push … falhou` | a página da tailnet já está no ar; o GitHub sai no próximo `scripts\publicar.ps1`. Cite no resumo |
| `a rodada … já foi fechada` | a rodada de hoje nesse modo já aconteceu; não repita. Diga isso no resumo e pare |

Estado da rodada: `data/live/estado.json` (`~/.claude/radar-mcp.cmd status` resume). Log:
`data/rodada_mcp.log`.
