$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logsDir = Join-Path $repoRoot "data\logs"
$stdoutLog = Join-Path $logsDir "media-maxing-8000.out.log"
$stderrLog = Join-Path $logsDir "media-maxing-8000.err.log"
$healthUrl = "http://127.0.0.1:8000/api/health"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

function Test-LocalCompanion {
    try {
        return Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3
    } catch {
        return $null
    }
}

$existingHealth = Test-LocalCompanion
if ($existingHealth -and $existingHealth.ok) {
    Write-Output "Media Maxing local companion is already running."
    Write-Output "Health: $healthUrl"
    Write-Output "Use your Vercel URL with: ?localApiOrigin=http://127.0.0.1:8000#home"
    exit 0
}

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    Write-Output "Port 8000 is already in use by process $($listener.OwningProcess), but Media Maxing did not answer health checks."
    Write-Output "Close that process or restart your computer, then run this launcher again."
    exit 1
}

Remove-Item -LiteralPath $stdoutLog, $stderrLog -ErrorAction SilentlyContinue

$arguments = @(
    "-m",
    "scripts.local_beta_launcher",
    "--database",
    "data/app.sqlite",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
    "--no-browser"
)

$process = Start-Process `
    -FilePath "python" `
    -WorkingDirectory $repoRoot `
    -ArgumentList $arguments `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

for ($attempt = 1; $attempt -le 15; $attempt++) {
    Start-Sleep -Seconds 1
    $health = Test-LocalCompanion
    if ($health -and $health.ok) {
        Write-Output "Media Maxing local companion is running in the background."
        Write-Output "Process ID: $($process.Id)"
        Write-Output "Health: $healthUrl"
        Write-Output "Logs:"
        Write-Output "  $stdoutLog"
        Write-Output "  $stderrLog"
        Write-Output ""
        Write-Output "Open your Vercel app with:"
        Write-Output "  https://media-maxing.vercel.app/?localApiOrigin=http://127.0.0.1:8000#home"
        exit 0
    }
    if ($process.HasExited) {
        Write-Output "Media Maxing local companion exited before it became ready."
        Write-Output "Check logs:"
        Write-Output "  $stdoutLog"
        Write-Output "  $stderrLog"
        exit 1
    }
}

Write-Output "Media Maxing local companion started, but health did not answer in time."
Write-Output "Process ID: $($process.Id)"
Write-Output "Check health manually: $healthUrl"
Write-Output "Check logs:"
Write-Output "  $stdoutLog"
Write-Output "  $stderrLog"
exit 1
