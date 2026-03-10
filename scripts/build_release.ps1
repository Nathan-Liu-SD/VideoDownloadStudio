param(
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$venv = Join-Path $root ".venv"
if ($RecreateVenv -and (Test-Path $venv)) {
    Remove-Item -Recurse -Force $venv
}

if (-not (Test-Path $venv)) {
    python -m venv .venv
}

$py = Join-Path $venv "Scripts\python.exe"
$pi = Join-Path $venv "Scripts\pyinstaller.exe"
$icon = Join-Path $root "assets\video_download_studio.ico"

if (-not (Test-Path $pi)) {
    & $py -m pip install --disable-pip-version-check pyinstaller
}

$depsCheck = & $py -c "import requests, yt_dlp, PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $py -m pip install --disable-pip-version-check -r requirements.txt
}

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

$commonArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--paths", "src",
    "--icon", $icon,
    "--add-data", "assets;assets",
    "--collect-all", "yt_dlp"
)

# Full release: bundled ffmpeg fallback (larger size, best compatibility)
& $pi @commonArgs --name VideoDownloadStudio_v3_Full --collect-all imageio_ffmpeg app.py
Copy-Item "dist\VideoDownloadStudio_v3_Full.exe" "dist\VideoDownloadStudio_v3.exe" -Force

# Lite release: no bundled imageio-ffmpeg (smaller size, requires system ffmpeg)
& $pi @commonArgs --name VideoDownloadStudio_v3_Lite --exclude-module imageio_ffmpeg app.py

# Keep workspace clean
Get-ChildItem -Filter "*.spec" | Remove-Item -Force
if (Test-Path build) { Remove-Item -Recurse -Force build }

Get-ChildItem dist\*.exe | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host "Build complete. Output: $root\dist"
