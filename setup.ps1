[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        $launcherCommand = Get-Command py -ErrorAction SilentlyContinue
        if ($null -eq $launcherCommand) {
            throw "Установите Python 3.11 или новее с сайта python.org."
        }
        & $launcherCommand.Source -3 -m venv (Join-Path $projectRoot ".venv")
    } else {
        & $pythonCommand.Source -m venv (Join-Path $projectRoot ".venv")
    }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot "requirements-dev.txt")

Write-Host ""
Write-Host "Готово. Запуск: .\run.ps1" -ForegroundColor Green
