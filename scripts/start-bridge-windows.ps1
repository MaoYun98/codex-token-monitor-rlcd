$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Bridge = Join-Path $Root 'bridge'
$EnvFile = Join-Path $Bridge '.env'

if (Test-Path $EnvFile) {
    foreach ($Line in Get-Content -LiteralPath $EnvFile) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith('#') -or -not $Trimmed.Contains('=')) { continue }
        $Name, $Value = $Trimmed.Split('=', 2)
        [Environment]::SetEnvironmentVariable($Name.Trim(), $Value.Trim(), 'Process')
    }
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Push-Location $Bridge
    try {
        uv sync
        uv run python bridge.py
    }
    finally {
        Pop-Location
    }
    exit
}

$Venv = Join-Path $Bridge '.venv'
if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
    py -3 -m venv $Venv
}
$Python = Join-Path $Venv 'Scripts\python.exe'
& $Python -m pip install -e $Bridge
& $Python (Join-Path $Bridge 'bridge.py')
