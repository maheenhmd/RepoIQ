# Run from PowerShell. No installs, migrations or environment-file writes.
$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$logRoot = Join-Path $env:TEMP ('repoiq-' + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $logRoot | Out-Null
$processes = @()
$services = @{
    api = @('run', '--no-sync', 'python', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000')
    ingestion = @('run', '--no-sync', 'python', '-m', 'app.workers.ingestion')
    embeddings = @('run', '--no-sync', 'python', '-m', 'app.workers.embeddings', '--watch')
}
try {
    foreach ($name in $services.Keys) {
        $process = Start-Process -FilePath 'uv' -ArgumentList $services[$name] -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "$name.out.log") -RedirectStandardError (Join-Path $logRoot "$name.err.log")
        $processes += @{ Name = $name; Process = $process }
    }
    Write-Host "RepoIQ services running. Logs: $logRoot. Ctrl+C stops this local process group."
    while ($true) {
        foreach ($entry in $processes) {
            if ($entry.Process.HasExited) { throw "$($entry.Name) exited ($($entry.Process.ExitCode)); inspect $logRoot" }
        }
        Start-Sleep -Seconds 2
    }
} finally {
    # Only terminate process trees created by this invocation; never other workers.
    foreach ($entry in $processes) {
        if (-not $entry.Process.HasExited) { & taskkill.exe /PID $entry.Process.Id /T /F | Out-Null }
    }
}
