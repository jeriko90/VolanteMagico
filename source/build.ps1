# Compila Volante.exe (onefile, portátil) con PyInstaller.
# Uso:  powershell -ExecutionPolicy Bypass -File source\build.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Write-Host "[1/3] Instalando dependencias..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r "$PSScriptRoot\requirements.txt"

Write-Host "[2/3] Compilando Volante.exe..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm --distpath "$root\dist" --workpath "$PSScriptRoot\build" "$PSScriptRoot\Volante.spec"

Write-Host "[3/3] Listo." -ForegroundColor Green
Write-Host "Ejecutable: $root\dist\Volante.exe"
Write-Host "Compártelo: el otro usuario solo ejecuta el .exe (acepta 1 UAC para el driver)."
