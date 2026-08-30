# Daily 02:00 Asia/Taipei pipeline via Windows Task Scheduler
# Run: powershell -ExecutionPolicy Bypass -File install_daily_task.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source
$taskName = "PaperReviewDaily2AM"

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$root\run_once.py`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 02:00
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Registered scheduled task '$taskName' at 02:00 daily."
Write-Host "Pipeline: $python $root\run_once.py"
Write-Host "Keep this PC on (or wake) around 02:00, and keep Ollama running."
Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State
