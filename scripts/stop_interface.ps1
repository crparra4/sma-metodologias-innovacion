param([int]$Port = 8787)

$ErrorActionPreference = 'Stop'
$interfaceRecordPath = Join-Path $env:LOCALAPPDATA "RutaDIA\interface-$Port.json"
if (-not (Test-Path -LiteralPath $interfaceRecordPath)) {
    Write-Output 'No hay una interfaz registrada.'
    return
}
$record = Get-Content -LiteralPath $interfaceRecordPath -Raw | ConvertFrom-Json
$process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.started_ticks -and $process.Path -eq $record.executable) {
    Stop-Process -Id $process.Id
    Write-Output 'Interfaz detenida.'
} else {
    Write-Output 'La interfaz registrada ya estaba detenida.'
}
Remove-Item -LiteralPath $interfaceRecordPath
