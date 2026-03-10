param(
    [switch]$RecreateVenv
)

$scriptPath = Join-Path $PSScriptRoot "scripts\build_release.ps1"
& $scriptPath -RecreateVenv:$RecreateVenv
