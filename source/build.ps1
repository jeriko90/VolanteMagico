# Compila Volante.exe (onefile, portátil) con PyInstaller y regenera update.json.
# Uso:  powershell -ExecutionPolicy Bypass -File source\build.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root "dist\Volante.exe"

Write-Host "[1/4] Instalando dependencias..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r "$PSScriptRoot\requirements.txt"

Write-Host "[2/4] Compilando Volante.exe..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm --distpath "$root\dist" --workpath "$PSScriptRoot\build" "$PSScriptRoot\Volante.spec"

Write-Host "[3/4] Generando update.json..." -ForegroundColor Cyan
$match = Select-String -Path "$PSScriptRoot\version.py" -Pattern '__version__\s*=\s*"([^"]+)"'
$version = $match.Matches[0].Groups[1].Value
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLower()
$manifest = [ordered]@{
  version = $version
  url     = "https://raw.githubusercontent.com/jeriko90/VolanteMagico/main/dist/Volante.exe"
  sha256  = $hash
  notes   = "Volante $version"
}
$json = $manifest | ConvertTo-Json
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $root "update.json"), $json, $utf8)
Write-Host ("  version = " + $version)
Write-Host ("  sha256  = " + $hash)

Write-Host "[4/4] Listo." -ForegroundColor Green
Write-Host "Ejecutable: $exe"
Write-Host "Manifiesto: $(Join-Path $root 'update.json')"
Write-Host "Compártelo: el otro usuario solo ejecuta el .exe (1 UAC la primera vez)."
