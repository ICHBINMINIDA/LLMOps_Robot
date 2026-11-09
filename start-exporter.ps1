# Runs the GPU exporter on the Windows host (SSH to the server works here, not inside Docker).
# Usage:  powershell -ExecutionPolicy Bypass -File start-exporter.ps1
# Requires: the SSH tunnel on port 18080 and key login to SSH_TARGET (set in .env).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Load KEY=VALUE pairs from .env
Get-Content .env | Where-Object { $_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$' } | ForEach-Object {
    Set-Item -Path "env:$($Matches[1])" -Value $Matches[2].Trim()
}

$env:GPU_MODE = "ssh"
# Inside Docker the tunnel is host.docker.internal; on the host itself it is localhost
$env:OLLAMA_API_BASE = $env:OLLAMA_API_BASE -replace 'host\.docker\.internal', 'localhost'

python -u gpu-exporter\exporter.py
