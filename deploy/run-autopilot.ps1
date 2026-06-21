# run-autopilot.ps1 — one unattended autopilot pass, for Windows Task Scheduler.
# Runs a single cycle (sync -> re-buy drafts -> optional reprice) and exits, so it's
# safe to fire on a schedule (e.g. hourly). Logs each run to logs\autopilot.log.
#
# One-time setup (run PowerShell as your normal user, from the repo folder):
#   cd $HOME\ebe-commerce
#   .\deploy\register-autopilot-task.ps1      # registers the hourly scheduled task
#
# Check it's working anytime:   python -m ebe status

$ErrorActionPreference = "Stop"

# repo root = the folder this script's parent lives in
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$LogDir = Join-Path $Repo "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "autopilot.log"

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $Log "[$stamp] autopilot cycle starting"

# one cycle, then exit. Re-buys land as DRAFTS (safe). Add --auto only with a trusted supplier.
python -m ebe autopilot --cycles 1 *>> $Log

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $Log "[$stamp] autopilot cycle done (exit $LASTEXITCODE)"
