# Cria (ou atualiza) a Tarefa Agendada do Windows que roda o radar todo dia às 8h.
# Rode uma vez:  .\scripts\agendar.ps1
# Para remover:  Unregister-ScheduledTask -TaskName "Radar Safira" -Confirm:$false

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$script = Join-Path $raiz "scripts\rodada.ps1"
$nome = "Radar Safira"

$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $raiz

$gatilho = New-ScheduledTaskTrigger -Daily -At 8am

# StartWhenAvailable: se o PC estiver desligado às 8h, roda assim que ligar.
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho `
    -Settings $config -Description "Coleta diária do Radar Safira na JoomPulse" -Force | Out-Null

Write-Output "Tarefa '$nome' agendada para todo dia as 8h."
Write-Output "Se o PC estiver desligado no horario, ela roda assim que voce ligar."
Write-Output ""
Write-Output "Testar agora:  Start-ScheduledTask -TaskName '$nome'"
Write-Output "Ver o log:     Get-Content data\rodada.log -Tail 20"
