# Prompt de ativação — cole no Claude Code (no seu computador)

> Este arquivo é o passo a passo completo para colocar o Radar Safira no ar. Ele foi escrito para ser
> executado por um Claude Code rodando na sua máquina (onde há rede e navegador), com você acompanhando.
> Copie tudo abaixo da linha e cole como primeira mensagem.

---

Você está ativando o **Radar Safira**, um projeto Python já pronto e testado (pasta `radar-safira`, que o usuário
vai indicar). Leia `README.md` antes de qualquer coisa. Seu trabalho é fazer as verificações externas que só podem
ser feitas daqui (rede + navegador), publicar o repositório e ligar o agendamento. Não reescreva o código; se algo
falhar, diagnostique, ajuste o mínimo e registre o que mudou. Fale em português. Confirme com o usuário antes de
cada ação que cria coisas fora da máquina (repositório, secrets, Pages).

## 0. Pré-requisitos (verifique e informe o que falta)
- Python 3.11+ (`python --version`), `git`, `gh` (GitHub CLI) autenticado (`gh auth status`).
- Conta JoomPulse ativa do usuário (ele vai fazer login no navegador na etapa 3).
- Um nome de repositório no GitHub (sugestão: `radar-safira`, privado). Anote `OWNER/REPO`.

## 1. Instalar e provar que o código funciona offline
```bash
cd radar-safira
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -q            # esperado: 6 passed
python -m radar run --fixtures tests/fixtures   # rodada com os dados de 05/09/2026, sem rede
```
Confira que `docs/data.json` foi gerado (~2 MB) e abra `docs/index.html` via um servidor local
(`python -m http.server 8080 --directory docs`) para ver a página funcionando.

## 2. Criar o repositório e o GitHub Pages
```bash
git init && git add -A && git commit -m "Radar Safira"
gh repo create OWNER/REPO --private --source=. --push
gh api -X POST repos/OWNER/REPO/pages -f 'source[branch]=main' -f 'source[path]=/docs'
```
Se o comando do Pages falhar, faça pela interface: Settings → Pages → Deploy from branch → `main` / `/docs`.
A URL final será `https://OWNER.github.io/REPO/`. Espere o primeiro deploy (1–2 min) e confira que
`https://OWNER.github.io/REPO/index.html` abre.

## 3. Documento OAuth do cliente (o ponto crítico — verifique de verdade)
A JoomPulse aceita clientes OAuth identificados por uma URL de metadados (`client_id_metadata_document_supported: true`
em `https://joompulse.com/.well-known/oauth-authorization-server`). Gere o documento apontando para o Pages:
```bash
export RADAR_CLIENT_METADATA_URL="https://OWNER.github.io/REPO/oauth-client.json"
python scripts/make_client_metadata.py
git add docs/oauth-client.json && git commit -m "oauth client metadata" && git push
```
Verifique com `curl -sI https://OWNER.github.io/REPO/oauth-client.json` que responde `200` e
`content-type: application/json`. Só siga quando isso estiver certo.

Agora o login (abre o navegador; o usuário entra na JoomPulse e autoriza):
```bash
python -m radar login
python -m radar check
```
Resultados possíveis:
- **Autorizou e `check` listou `query_cubejs_meli` e `query_cubejs_joompro`** → perfeito, siga para a etapa 4.
- **A JoomPulse recusou o client_id (erro tipo `invalid_client` / página de erro no navegador)** → a JoomPulse pode
  estar restringindo hosts de metadata ou o redirect `http://localhost:8765/callback`. Tente: (a) `RADAR_OAUTH_PORT=8765`
  já é o padrão, teste `RADAR_OAUTH_PORT=3000`; (b) confira se a página de erro cita `redirect_uri` ou `client_id`;
  (c) se persistir, PARE e relate ao usuário o erro exato — o caminho então é pedir à JoomPulse (suporte) um client_id
  para uso próprio e colocá-lo em `RADAR_CLIENT_ID` (o código já suporta), ou usar o Claude como coletor (plano B).
- **Autorizou mas `check` deu 401/403 nas ferramentas** → o plano da conta pode não incluir MCP; relate ao usuário.

## 4. Primeira rodada real
```bash
python -m radar run
```
Esperado: JSON final com `products` ≈ 1500–2200, `queries` ≈ 70, `month` = mês corrente ou anterior. Tempo: 2–6 min.
Se der erro de rate limit (429) ou timeout, rode de novo uma vez; se persistir, reduza `DISCOVERY_MAIN_LIMIT` para 30
em `radar/config.py` e relate.
Abra a página local de novo e confira que os dados são de hoje (cabeçalho mostra a rodada e a hora).

## 5. Segredos e agendamento
```bash
export RADAR_TOKEN_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
echo "Guarde esta senha no seu gerenciador: $RADAR_TOKEN_KEY"
python -m radar token encrypt                      # cria data/token.enc
gh secret set RADAR_TOKEN_KEY --body "$RADAR_TOKEN_KEY"
gh variable set RADAR_CLIENT_METADATA_URL --body "$RADAR_CLIENT_METADATA_URL"
git add data/token.enc data/radar.db docs/data.json && git commit -m "primeira rodada" && git push
gh workflow run "Radar Safira — coleta" && sleep 60 && gh run list --limit 1
```
Acompanhe com `gh run watch`. A rodada no Actions deve terminar em verde e fazer um commit "radar: rodada …".
Depois disso o cron cuida: 8h e 15h (Brasília). Para mudar a frequência, edite `.github/workflows/refresh.yml`.

## 6. Entregar ao usuário
Escreva um resumo com: URL da página, se o OAuth com metadata funcionou (ou qual plano B foi usado), quantos
produtos a primeira rodada trouxe, tempo da rodada, e o link do último run do Actions. Lembre o usuário de que
`.secrets/token.json` fica só na máquina dele e que `RADAR_TOKEN_KEY` precisa ser guardada.

## Se precisar mexer em algo
- Pesos do score, tamanhos de consulta, retenção: `radar/config.py`.
- Fórmula: `radar/engine.py` (`Scorer.score`). Teste com `python -m pytest -q` e `python -m radar run --fixtures tests/fixtures`.
- Página: `docs/index.html` (lê `data.json`; sem build).
