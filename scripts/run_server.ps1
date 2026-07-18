param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoLiveProxy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

$args = @("-m", "steamfun_mirror", "--root", $root, "serve", "--host", $BindHost, "--port", $Port)
if ($NoLiveProxy) {
    $args += "--no-live-proxy"
}

& $python @args
