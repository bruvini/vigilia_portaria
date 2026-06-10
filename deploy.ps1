# =============================================================================
# Vigília — script de deploy para Firebase (Windows)
#
# Por que este script existe:
#   O Firebase CLI falha ao introspectar funções Python quando o caminho do
#   projeto contém caracteres acentuados (ex.: "C:\Users\USUÁRIO\..."), porque
#   o Python informa o caminho real do pacote e o CLI o corrompe ao repassá-lo.
#   A solução é fazer o deploy a partir de uma cópia em caminho 100% ASCII.
#
# O que faz:
#   1. Sincroniza o projeto para C:\vgl (staging ASCII) via robocopy.
#   2. Cria/atualiza o virtualenv das funções nesse caminho.
#   3. Roda `firebase deploy` de lá.
#
# Uso (no PowerShell, a partir da raiz do projeto):
#   ./deploy.ps1                  # deploy completo (hosting + functions + rules)
#   ./deploy.ps1 -Only functions  # só as funções
#   ./deploy.ps1 -Only hosting:vigiliasms
# =============================================================================

param(
    [string]$Only = "",
    [string]$Stage = "C:\vgl",
    [string]$Project = "pmj-sms"
)

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot

Write-Host "==> Sincronizando para staging ASCII: $Stage" -ForegroundColor Cyan
# /MIR espelha; exclui venv, .git e artefatos que não vão ao deploy.
robocopy $src $Stage /MIR `
    /XD "$src\.git" "$src\functions\venv" "$src\node_modules" "$src\.firebase" `
        "$src\dom_screenshots" "$src\__pycache__" `
    /XF "*.pyc" `
    /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou (código $LASTEXITCODE)" }

Write-Host "==> Preparando virtualenv das funções" -ForegroundColor Cyan
$venv = Join-Path $Stage "functions\venv"
if (-not (Test-Path (Join-Path $venv "Scripts\activate.bat"))) {
    python -m venv $venv
}
& (Join-Path $venv "Scripts\python.exe") -m pip install -r (Join-Path $Stage "functions\requirements.txt") --quiet

Write-Host "==> firebase deploy" -ForegroundColor Cyan
Push-Location $Stage
try {
    if ($Only) {
        firebase deploy --only $Only --project $Project
    } else {
        firebase deploy --project $Project
    }
} finally {
    Pop-Location
}

Write-Host "==> Concluído. Site: https://vigiliasms.web.app" -ForegroundColor Green
