$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Pause-And-Exit([int]$Code) {
    Write-Host ""
    Read-Host "Presione ENTER para cerrar"
    exit $Code
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host "  NEGROSKY LOYALTY - INICIO COMPLETO" -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host ""

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    $parentFolder = Split-Path $PSScriptRoot -Parent
    $previous = Get-ChildItem $parentFolder -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne $PSScriptRoot -and (Test-Path (Join-Path $_.FullName "venv\Scripts\python.exe")) } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($previous) {
        Write-Host "Reutilizando componentes instalados de $($previous.Name)..." -ForegroundColor Cyan
        Copy-Item (Join-Path $previous.FullName "venv") ".\venv" -Recurse
        $previousDb = Join-Path $previous.FullName "data\negrosky_v2.db"
        if ((-not (Test-Path ".\data\negrosky_v2.db")) -and (Test-Path $previousDb)) {
            Copy-Item $previousDb ".\data\negrosky_v2.db" -Force
            Write-Host "Datos y campanas recuperados automaticamente." -ForegroundColor Green
        } elseif (Test-Path ".\data\negrosky_v2.db") {
            Write-Host "Se conserva la base de datos incluida en esta BUILD." -ForegroundColor Green
        }
        $previousBackups = Join-Path $previous.FullName "backups"
        if (Test-Path $previousBackups) {
            New-Item -ItemType Directory -Force -Path ".\backups" | Out-Null
            Copy-Item (Join-Path $previousBackups "*") ".\backups" -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "Respaldos anteriores recuperados automaticamente." -ForegroundColor Green
        }
    }
}

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "Primera ejecucion: preparando el sistema..." -ForegroundColor Yellow
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Host "[ERROR] Debe instalar Python 3 para Windows." -ForegroundColor Red
        Pause-And-Exit 1
    }
    & py -m venv venv
    if ($LASTEXITCODE -ne 0) { Pause-And-Exit 1 }
    & ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Pause-And-Exit 1 }
}

$existing = Get-NetTCPConnection -LocalPort 8030 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $negroskyStopped = $false
    $ownerIds = $existing | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($ownerId in $ownerIds) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerId" -ErrorAction SilentlyContinue
        $commandLine = [string]$owner.CommandLine
        $isNegroskyServer = $commandLine -match '(?i)uvicorn' -and $commandLine -match '(?i)(core[\\.]backend[\\.]api[\\.]main|app[\\.]main):app'
        if ($isNegroskyServer) {
            Write-Host "[OK] Se encontro un servidor NEGROSKY anterior en el puerto 8030. Cerrandolo..." -ForegroundColor Yellow
            Stop-Process -Id $ownerId -Force -ErrorAction SilentlyContinue
            $negroskyStopped = $true
        }
    }
    if ($negroskyStopped) {
        Start-Sleep -Milliseconds 800
        $existing = Get-NetTCPConnection -LocalPort 8030 -State Listen -ErrorAction SilentlyContinue
    }
    if ($existing) {
        Write-Host "[AVISO] El puerto 8030 esta ocupado por otro programa." -ForegroundColor Yellow
        Write-Host "Cierre ese programa y vuelva a iniciar NEGROSKY."
        Pause-And-Exit 1
    }
}

$addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -ne "127.0.0.1" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.InterfaceAlias -notmatch "Loopback|Virtual|WSL|Hyper-V|Bluetooth"
    } |
    Sort-Object InterfaceMetric |
    Select-Object -ExpandProperty IPAddress -Unique

$python = (Resolve-Path ".\venv\Scripts\python.exe").Path
$arguments = @("-m", "uvicorn", "core.backend.api.main:app", "--host", "0.0.0.0", "--port", "8030")
$server = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -RedirectStandardOutput ".\servidor_salida.log" -RedirectStandardError ".\servidor_error.log" -WindowStyle Hidden -PassThru
$server.Id | Set-Content ".negrosky-server.pid"

$online = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:8030/api/health" -UseBasicParsing -TimeoutSec 1
        if ($health.StatusCode -eq 200) { $online = $true; break }
    } catch { }
}

if (-not $online) {
    Write-Host "[ERROR] El servidor no pudo iniciar." -ForegroundColor Red
    if (Test-Path ".\servidor_error.log") { Get-Content ".\servidor_error.log" -Tail 20 }
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Remove-Item ".negrosky-server.pid" -ErrorAction SilentlyContinue
    Pause-And-Exit 1
}

Write-Host "[OK] NEGROSKY esta funcionando." -ForegroundColor Green
Write-Host ""
Write-Host "EN ESTE COMPUTADOR" -ForegroundColor Cyan
Write-Host "  Administrador: http://127.0.0.1:8030"
Write-Host "  Trabajador:    http://127.0.0.1:8030/worker"
Write-Host "  Clientes:     consulte todas las URL por negocio en el panel"

if ($addresses) {
    Write-Host ""
    Write-Host "EN EL CELULAR (misma red Wi-Fi)" -ForegroundColor Cyan
    foreach ($address in $addresses) {
        Write-Host "  Trabajador: http://${address}:8030/worker" -ForegroundColor Yellow
        Write-Host "  Clientes:   consulte todas las URL por negocio en el panel" -ForegroundColor Yellow
    }
} else {
    Write-Host "No se pudo detectar la direccion Wi-Fi. Ejecute ipconfig para consultarla." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "No cierre esta ventana mientras use el sistema." -ForegroundColor White
Write-Host "Para apagarlo tambien puede usar DETENER_NEGROSKY.bat."
Start-Process "http://127.0.0.1:8030/?v=3.0.55"

try {
    Wait-Process -Id $server.Id
} finally {
    Remove-Item ".negrosky-server.pid" -ErrorAction SilentlyContinue
}
