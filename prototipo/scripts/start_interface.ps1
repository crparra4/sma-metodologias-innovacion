param(
    [int]$Port = 8787,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
$interfaceDirectory = Join-Path $env:LOCALAPPDATA 'RutaDIA'
$interfaceUrl = "http://127.0.0.1:$Port"
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Primero instala las dependencias: python -m uv --system-certs sync --extra dev --link-mode copy'
}

function Ensure-LocalModelFiles {
    $modelDirectory = Join-Path $env:LOCALAPPDATA 'QwenLocalTest'
    $modelPath = Join-Path $modelDirectory 'Qwen3.5-4B.Q4_K_M.gguf'
    $serverPath = Join-Path $modelDirectory 'runtime\llama-server.exe'
    if ((Test-Path -LiteralPath $modelPath) -and (Test-Path -LiteralPath $serverPath)) { return }
    Write-Output 'Falta Qwen o llama.cpp en este equipo. Descargando los archivos locales...'
    & $pythonExecutable (Join-Path $PSScriptRoot 'install_local_model.py')
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Qwen. Repite el comando para reanudar la descarga.' }
}

function Register-InterfaceProcess {
    # El redirector Python de .venv tiene un PID diferente del servidor que escucha el puerto.
    $owner = (Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen | Select-Object -First 1).OwningProcess
    $serverProcess = Get-Process -Id $owner
    New-Item -ItemType Directory -Path $interfaceDirectory -Force | Out-Null
    @{
        pid = $serverProcess.Id
        started_ticks = $serverProcess.StartTime.ToUniversalTime().Ticks.ToString()
        executable = $serverProcess.Path
        port = $Port
    } | ConvertTo-Json | Set-Content (Join-Path $interfaceDirectory "interface-$Port.json")
}

$existing = $null
try { $existing = Invoke-RestMethod "$interfaceUrl/api/status" -TimeoutSec 5 } catch { }
if ($existing -and $existing.app_id -eq 'ruta-dia-local') {
    if (-not $existing.available) {
        Ensure-LocalModelFiles
        & $pythonExecutable (Join-Path $PSScriptRoot 'local_model.py') start
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar Qwen. Revisa la configuracion local.' }
    }
    Register-InterfaceProcess
    Write-Output "La interfaz ya esta disponible: $interfaceUrl"
    if (-not $NoBrowser) { Start-Process $interfaceUrl }
    return
}

$portCheck = [System.Net.Sockets.TcpClient]::new()
try {
    $portCheck.Connect('127.0.0.1', $Port)
    throw "El puerto $Port esta ocupado por otro servicio. Usa -Port con otro numero."
} catch [System.Net.Sockets.SocketException] {
    # Sin servicio previo; el servidor puede iniciar.
} finally { $portCheck.Dispose() }

Push-Location $projectDirectory
try {
    Ensure-LocalModelFiles
    & $pythonExecutable (Join-Path $PSScriptRoot 'local_model.py') start
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar Qwen. Revisa la configuracion local.' }
    if (-not (Test-Path -LiteralPath (Join-Path $projectDirectory 'frontend\dist\index.html'))) {
        $env:NODE_USE_SYSTEM_CA = '1'
        & pnpm --dir frontend install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias frontend.' }
        & pnpm --dir frontend build
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo construir la interfaz.' }
    }
    New-Item -ItemType Directory -Path $interfaceDirectory -Force | Out-Null
    $process = Start-Process -FilePath $pythonExecutable `
        -ArgumentList @('-m', 'ruta_dia_agents', 'web', '--port', "$Port") `
        -WorkingDirectory $projectDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $interfaceDirectory "interface-$Port.out.log") `
        -RedirectStandardError (Join-Path $interfaceDirectory "interface-$Port.err.log")
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($process.HasExited) { throw "La interfaz termino al iniciar. Revisa interface-$Port.err.log en $interfaceDirectory" }
        try {
            $status = Invoke-RestMethod "$interfaceUrl/api/status" -TimeoutSec 5
            if ($status.app_id -eq 'ruta-dia-local') {
                Register-InterfaceProcess
                Write-Output "Ruta DIA lista: $interfaceUrl"
                if (-not $NoBrowser) { Start-Process $interfaceUrl }
                return
            }
        } catch { }
        Start-Sleep -Milliseconds 400
    }
    throw "La interfaz no respondio. Revisa interface-$Port.err.log en $interfaceDirectory"
} finally { Pop-Location }
