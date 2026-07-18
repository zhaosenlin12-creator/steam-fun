param(
    [Parameter(Mandatory = $true)][string]$TeacherUsername,
    [Parameter(Mandatory = $true)][string]$TeacherPassword,
    [Parameter(Mandatory = $true)][string]$StudentUsername,
    [Parameter(Mandatory = $true)][string]$StudentPassword,
    [int]$RouteLimit = 0,
    [switch]$Visible
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

$args = @(
    "-m", "steamfun_mirror",
    "--root", $root,
    "capture",
    "--teacher-username", $TeacherUsername,
    "--teacher-password", $TeacherPassword,
    "--student-username", $StudentUsername,
    "--student-password", $StudentPassword
)

if ($RouteLimit -gt 0) {
    $args += @("--route-limit", $RouteLimit)
}

if ($Visible) {
    $args += "--visible"
}

& $python @args
