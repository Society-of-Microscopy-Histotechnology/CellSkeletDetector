[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

$pythonExecutable = $null
if (Test-Path -LiteralPath $venvPython) {
    $pythonExecutable = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        $pythonExecutable = $pythonCommand.Source
    } elseif (Test-Path -LiteralPath $codexPython) {
        $pythonExecutable = $codexPython
    }
}

if ($null -eq $pythonExecutable) {
    throw "Python не найден. Установите Python 3.11+ или сначала выполните .\setup.ps1"
}

Push-Location $projectRoot
try {
    & $pythonExecutable -c "import numpy, scipy, skimage, PIL" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Не установлены зависимости. Выполните .\setup.ps1"
    }
    & $pythonExecutable "app.py"
} finally {
    Pop-Location
}
