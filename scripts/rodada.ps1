# Rodada do Radar Safira: coleta pelo navegador, atualiza a página e publica.
# Feito para a Tarefa Agendada do Windows (o GitHub Actions não serve aqui,
# porque a coleta depende da sessão da JoomPulse guardada nesta máquina).
#
# Instalar o agendamento:  .\scripts\agendar.ps1
# Rodar na mão:            .\scripts\rodada.ps1

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$py  = Join-Path $raiz ".venv\Scripts\python.exe"
$log = Join-Path $raiz "data\rodada.log"
$env:PYTHONIOENCODING = "utf-8"

function Registrar($msg) {
    $linha = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -Path $log -Value $linha -Encoding utf8
    Write-Output $linha
}

Registrar "=== rodada iniciada ==="

# A sessão do navegador expira de tempos em tempos; sem ela não há o que fazer,
# e é melhor avisar no log do que gravar uma rodada vazia por cima da boa.
& $py -m radar check-browser
if ($LASTEXITCODE -ne 0) {
    Registrar "SESSAO EXPIRADA - rode: .venv\Scripts\python.exe -m radar login-browser"
    exit 1
}

$saida = & $py -m radar run --browser 2>&1
$saida | Add-Content -Path $log -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Registrar "FALHA na coleta (exit $LASTEXITCODE)"
    exit 1
}
Registrar "coleta concluida"

# Publica (GitHub Pages e Predator). Só commita se algo mudou de fato.
git add data/radar.db docs/data.json
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git -c user.name="radar-bot" -c user.email="radar-bot@users.noreply.github.com" `
        commit -q -m "radar: rodada $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $remotos = @(git remote)
    if ($remotos -contains "origin") {
        git push -q origin main
        Registrar "publicado no GitHub Pages"
    }
    if ($remotos -contains "predator") {
        # Notebook: o mesmo commit vai para o Predator (repositorio central + pagina da tailnet).
        # Se o Predator estiver desligado, a rodada nao falha: fica no log e o proximo
        # .\scripts\publicar.ps1 poe em dia.
        powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $raiz "scripts\publicar.ps1") -SoPredator |
            Add-Content -Path $log -Encoding utf8
        if ($LASTEXITCODE -eq 0) { Registrar "publicado no Predator" }
        else { Registrar "AVISO: Predator nao atualizado - rode scripts\publicar.ps1" }
    } elseif ($remotos -contains "central") {
        # Predator: a copia de trabalho e a propria producao; falta so guardar no repositorio central.
        git push -q central main
        Registrar "publicado no repositorio central do Predator"
    }
} else {
    Registrar "nada mudou, sem publicar"
}

Registrar "=== rodada concluida ==="
