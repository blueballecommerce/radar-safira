# Radar Safira — guia de uso

Este é o manual do dia a dia. Se algo parar de funcionar, a resposta provavelmente
está aqui.

**A página:** https://blueballecommerce.github.io/radar-safira/

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
Junta os anúncios repetidos do mesmo catálogo (fica o que mais vende), dá nota de
0 a 100 para cada produto e ordena tudo.

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

## O que este radar ainda não faz

Vale saber, para você não procurar o que não existe:

- **Importação JoomPro está vazia.** O pareamento com fornecedores chineses fica
  numa tela separada do site, que a coleta ainda não percorre. A aba avisa isso e
  manda o link direto.
- **Shopee e Fornecedores** são abas planejadas, sem conteúdo.
- **O tempo de anúncio é o do catálogo**, não o do anúncio individual — é o que o
  site informa.

---

## Se um dia a JoomPulse liberar acesso de programa

Hoje eles recusam clientes próprios (o `client_id` responde `invalid_client` e o
endpoint MCP devolve `401`), por isso a coleta é feita pelo navegador. Se um dia
fornecerem um `client_id`, o caminho antigo continua no código:

1. `RADAR_CLIENT_ID=<o que eles derem>`
2. religar o `schedule` em `.github/workflows/refresh.yml`
3. `python -m radar login` e `python -m radar run`

Aí a coleta volta a rodar na nuvem, sem depender do seu PC ligado.
