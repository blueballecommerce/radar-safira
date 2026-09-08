# Publica o Radar Safira nos dois lugares em que ele mora:
#   1. GitHub (remote "origin")     -> pagina publica https://blueballecommerce.github.io/radar-safira/
#   2. Predator (remote "predator") -> repositorio central C:\Repos\radar-safira.git e a copia de
#      trabalho C:\Projeto - Radar Safira, que serve a pagina da tailnet
#      https://dojoo.tailce25ed.ts.net:8444/
#
# Nao faz commit: commite antes (a rodada das 5h commita sozinha). Uso:
#   .\scripts\publicar.ps1              # GitHub + Predator
#   .\scripts\publicar.ps1 -SoPredator  # so o Predator (a rodada usa este)
#   .\scripts\publicar.ps1 -Dados       # tambem manda os arquivos que ficam fora do git
#                                       # (pranchas, decisoes, fornecedor*.json, catalogo)
#
# Regra da casa (a mesma do Nexo): antes de mexer em arquivo, olhe o estado do Predator.
# Este script mostra o commit que esta la antes e depois, e so avanca com fast-forward:
# se a copia do Predator tiver commit proprio, ele para e avisa, em vez de misturar.

param([switch]$SoPredator, [switch]$Dados)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$copia = "/c/Projeto - Radar Safira"
$ssh = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "predator")

function Falhar($msg) { Write-Output "ERRO: $msg"; exit 1 }

$pendentes = git status --porcelain
if ($pendentes) {
    Write-Output "Aviso: ha mudancas sem commit, e elas NAO sobem:"
    $pendentes | ForEach-Object { Write-Output "   $_" }
}
Write-Output "Notebook:  $(git log --oneline -1)"

if (-not $SoPredator) {
    git push -q origin main
    if ($LASTEXITCODE -ne 0) { Falhar "git push origin main falhou (internet? GitHub?)" }
    Write-Output "GitHub:    enviado (a pagina publica atualiza em 1-2 min)"
}

$antes = ssh @ssh "git -C '$copia' log --oneline -1"
if ($LASTEXITCODE -ne 0) { Falhar "nao consegui falar com o Predator (ligado? Tailscale conectado?)" }
Write-Output "Predator:  $antes  (antes)"

$sujo = ssh @ssh "git -C '$copia' status --porcelain"
if ($sujo) {
    Write-Output "Aviso: a copia do Predator tem arquivos mexidos fora do git:"
    $sujo | ForEach-Object { Write-Output "   $_" }
}

git push -q predator main
if ($LASTEXITCODE -ne 0) { Falhar "git push predator main falhou" }

$depois = ssh @ssh "cd '$copia' && git pull -q --ff-only central main && git log --oneline -1"
if ($LASTEXITCODE -ne 0) {
    Falhar "o Predator nao aceitou fast-forward: ha commit la que o notebook nao tem. Traga primeiro: git pull --ff-only predator main"
}
Write-Output "Predator:  $depois  (depois)"

if ($Dados) {
    # Os arquivos fora do git vao num .tgz pelo proprio ssh (scp e SMB nao funcionam com o Predator).
    $lista = @("data/pranchas", "data/fornecedor.json", "data/fornecedor_busca.json",
               "data/fornecedor_categorias.json", "data/fornecedor_veredito.json",
               "data/pares.json", "data/catalogo_set26.json") +
             @(Get-ChildItem "data/decisoes_*.json" | ForEach-Object { "data/" + $_.Name })
    $lista = @($lista | Where-Object { Test-Path $_ })
    $tgz = Join-Path $env:TEMP "radar-dados.tgz"
    tar czf $tgz @lista
    if ($LASTEXITCODE -ne 0) { Falhar "nao consegui empacotar os dados" }
    cmd /c "ssh -o BatchMode=yes predator ""cat > '$copia/dados.tgz'"" < ""$tgz"""
    if ($LASTEXITCODE -ne 0) { Falhar "nao consegui mandar os dados para o Predator" }
    ssh @ssh "cd '$copia' && tar xzf dados.tgz && rm dados.tgz && du -sh data/pranchas"
    if ($LASTEXITCODE -ne 0) { Falhar "o Predator nao conseguiu abrir o pacote de dados" }
    Remove-Item $tgz -ErrorAction SilentlyContinue
    Write-Output "Dados:     pranchas, decisoes e fornecedor*.json copiados"
}

Write-Output "Pagina da tailnet: https://dojoo.tailce25ed.ts.net:8444/"
