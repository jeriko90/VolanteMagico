# Compila Volante.exe (onefile, portatil) con PyInstaller y regenera update.json.
# Uso (desde cualquier carpeta):  powershell -ExecutionPolicy Bypass -File source\build.ps1
# Tambien puedes ejecutar build.cmd en la raiz (doble clic).

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$source = $PSScriptRoot
$root = Split-Path -Parent $source
$exe = Join-Path $root "dist\Volante.exe"

function Fail($msg) {
  Write-Host ""
  Write-Host "ERROR: $msg" -ForegroundColor Red
  exit 1
}

function Test-Locked($path) {
  if (-not (Test-Path -LiteralPath $path)) { return $false }
  try {
    $s = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $s.Close(); $s.Dispose()
    return $false
  } catch { return $true }
}

# [0/4] Cerrar Volante si esta abierto: bloquea dist\Volante.exe y hace fallar la copia.
Write-Host "[0/4] Cerrando instancias de Volante..." -ForegroundColor Cyan
$running = @(Get-Process Volante -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
  Write-Host ("  cerrando " + $running.Count + " proceso(s) Volante.exe")
  $running | Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}
for ($i = 0; $i -lt 10; $i++) {
  if (-not (Test-Locked $exe)) { break }
  Write-Host "  esperando a que se libere dist\Volante.exe..." -ForegroundColor Yellow
  Start-Sleep -Seconds 1
}
if (Test-Locked $exe) {
  Fail "dist\Volante.exe sigue en uso. Cierra TODAS las ventanas de Volante (incluida una posible consola/UAC elevada) y vuelve a intentarlo."
}

# Python disponible?
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Fail "No se encontro 'python'. Instala Python 3.11+ desde python.org y marca 'Add python.exe to PATH'."
}

Write-Host "[1/4] Instalando dependencias..." -ForegroundColor Cyan
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Fail "Fallo 'python -m pip install --upgrade pip'." }
python -m pip install -r "$source\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "Fallo la instalacion de dependencias (revisa tu conexion a Internet)." }

Write-Host "[2/4] Compilando Volante.exe (tarda ~1 min)..." -ForegroundColor Cyan
python -m PyInstaller --clean --noconfirm --distpath "$root\dist" --workpath "$source\build" "$source\Volante.spec"
if ($LASTEXITCODE -ne 0) { Fail "Fallo PyInstaller. Si el mensaje dice 'Acceso denegado', cierra Volante.exe y reintenta." }
if (-not (Test-Path -LiteralPath $exe)) { Fail "No se genero $exe." }

Write-Host "[3/4] Generando update.json..." -ForegroundColor Cyan
$match = Select-String -Path "$source\version.py" -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $match) { Fail "No se pudo leer __version__ de source\version.py" }
$version = $match.Matches[0].Groups[1].Value

# Copia con nombre de version: cada version tiene su propia URL, asi GitHub
# nunca sirve una copia cacheada de otra version al actualizar.
$versioned = Join-Path $root "dist\Volante-$version.exe"
Copy-Item -LiteralPath $exe -Destination $versioned -Force

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $versioned).Hash.ToLower()
$manifest = [ordered]@{
  version = $version
  url     = "https://raw.githubusercontent.com/jeriko90/VolanteMagico/main/dist/Volante-$version.exe"
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
Write-Host "Versionado: $versioned"
Write-Host "Manifiesto: $(Join-Path $root 'update.json')"
Write-Host "Compártelo: el otro usuario solo ejecuta el .exe (1 UAC la primera vez)."
