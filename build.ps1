$ErrorActionPreference = "Stop"

Write-Host "=== StakeMap Build Script ===" -ForegroundColor Cyan

# Install dependencies
Write-Host "[1/3] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# Install PyInstaller
Write-Host "[2/3] Installing PyInstaller..." -ForegroundColor Yellow
pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed" }

# Build executable
Write-Host "[3/3] Building executable..." -ForegroundColor Yellow
pyinstaller `
    --onefile `
    --windowed `
    --name StakeMap `
    --add-data "i18n;./i18n" `
    --clean `
    --noconfirm `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "=== Build complete! ===" -ForegroundColor Green
Write-Host "Executable: .\dist\StakeMap.exe" -ForegroundColor Green
