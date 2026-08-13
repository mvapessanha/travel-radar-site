# Roda a busca AGORA, na hora que você quiser testar/ajustar filtros
# (origem, datas, rota, duração) — não depende de status: active/draft,
# sempre executa. Use isso enquanto ainda está decidindo o roteiro.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run_now.ps1 [tenant] [max-dates]

param(
    [string]$Tenant = "marau",
    [int]$MaxDates = 20
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

& $Python (Join-Path $ProjectDir "src\main.py") --tenant $Tenant --max-dates $MaxDates --open
