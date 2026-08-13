# Registra uma tarefa HORÁRIA no Windows Task Scheduler para o Travel Radar.
# Roda 100% em segundo plano, sem NUNCA abrir janela/console (usa pythonw.exe,
# não python.exe) - não interfere no que você estiver fazendo no PC. Log vai
# pra data/run.log em vez de aparecer na tela.
# Essa execução automática só faz alguma coisa quando o roteiro está
# "status: active" no yaml (ver src/main.py --scheduled) - enquanto for
# "draft" ela roda e sai na hora, sem gastar cota de API.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\scripts\register_task.ps1

$ProjectDir = Split-Path -Parent $PSScriptRoot
$PythonW = Join-Path $ProjectDir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $PythonW)) { $PythonW = (Get-Command pythonw).Source }
$MainScript = Join-Path $ProjectDir "src\main.py"

$Action = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$MainScript`" --tenant marau --max-dates 20 --scheduled" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden

Register-ScheduledTask -TaskName "TravelRadar-Marau" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Roda de hora em hora em segundo plano (sem janela); só busca preço de verdade quando o roteiro estiver status: active." -Force -ErrorAction Stop

Write-Host "Tarefa 'TravelRadar-Marau' registrada. Roda de hora em hora, 100% invisível (pythonw.exe, sem console)."
Write-Host "Log de cada execução: data\run.log"
Write-Host "Pra rodar manualmente agora (sem depender de status): .\scripts\run_now.ps1"
Write-Host "Pra remover: Unregister-ScheduledTask -TaskName 'TravelRadar-Marau' -Confirm:`$false"
