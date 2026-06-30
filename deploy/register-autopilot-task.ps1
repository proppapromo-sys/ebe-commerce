# register-autopilot-task.ps1 — register EBE autopilot as an hourly Windows Scheduled Task.
# Run once, from the repo folder, in normal (non-admin) PowerShell:
#   cd $HOME\ebe-commerce
#   .\deploy\register-autopilot-task.ps1
#
# After this, autopilot runs every hour in the background, even after reboot (it starts
# at next logon). Remove it with:  Unregister-ScheduledTask -TaskName "EBE Autopilot"

$ErrorActionPreference = "Stop"

$Repo   = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Repo "deploy\run-autopilot.ps1"
$TaskName = "EBE Autopilot"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`""

# every hour, indefinitely, starting a minute from now; also at logon so it survives reboots
$triggers = @(
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Hours 1)),
    (New-ScheduledTaskTrigger -AtLogOn)
)

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings -Description "EBE Command — hourly sync + re-buy autopilot" -Force

Write-Host "[OK] Registered '$TaskName' — autopilot runs hourly."
Write-Host "     See it:    Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "     Run now:   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "     Logs:      $Repo\logs\autopilot.log"
Write-Host "     Health:    python -m ebe status"
