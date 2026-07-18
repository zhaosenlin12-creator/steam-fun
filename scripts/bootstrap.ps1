Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = Join-Path $root ".venv\Scripts\python.exe"

& $python -m pip install --upgrade pip setuptools wheel
& $python -m pip install -e "..\Scrapling[fetchers]"
& $python -m pip install -e ".[dev]"
