[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path -LiteralPath $venvPython) {
    $pythonExecutable = $venvPython
} elseif (Test-Path -LiteralPath $codexPython) {
    $pythonExecutable = $codexPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python не найден. Сначала выполните .\setup.ps1"
    }
    $pythonExecutable = $pythonCommand.Source
}

$env:PYINSTALLER_CONFIG_DIR = Join-Path $projectRoot ".pyinstaller"
Push-Location $projectRoot
try {
    & $pythonExecutable -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Тесты завершились с ошибкой."
    }

    & $pythonExecutable -m PyInstaller --noconfirm --clean "CellSkeletDetector.spec"
    if ($LASTEXITCODE -ne 0) {
        throw "Сборка EXE завершилась с ошибкой."
    }
} finally {
    Pop-Location
}

$exePath = Join-Path $projectRoot "dist\CellSkeletDetector.exe"
Write-Host ""
Write-Host "Готово: $exePath" -ForegroundColor Green
