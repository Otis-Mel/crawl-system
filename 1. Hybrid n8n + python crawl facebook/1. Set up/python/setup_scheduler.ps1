# Đăng ký (hoặc gỡ) tác vụ Task Scheduler chạy scraper Facebook định kỳ.
#   Đăng ký : powershell -ExecutionPolicy Bypass -File .\setup_scheduler.ps1 -EveryHours 3
#   Gỡ      : powershell -ExecutionPolicy Bypass -File .\setup_scheduler.ps1 -Unregister
# Không dùng RunLevel Highest (cần quyền admin). Máy phải bật và đã đăng nhập Windows khi đến giờ chạy.
param(
    [int]$EveryHours = 3,
    [string]$StartAt = "09:00",
    [string]$EndAt = "18:00",
    [switch]$Unregister
)

$taskName = "FB-Scraper-Leads"

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Đã gỡ tác vụ $taskName"
    return
}

$bat = Join-Path $PSScriptRoot "run_fb_scraper.bat"
if (-not (Test-Path $bat)) { throw "Không thấy $bat" }

$action   = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $PSScriptRoot
# Mỗi ngày, các mốc StartAt, StartAt+EveryHours, ... đến hết EndAt (mặc định 09:00, 12:00, 15:00, 18:00)
$times = @()
$t = [datetime]::ParseExact($StartAt, "HH:mm", $null)
$end = [datetime]::ParseExact($EndAt, "HH:mm", $null)
while ($t -le $end) { $times += $t.ToString("HH:mm"); $t = $t.AddHours($EveryHours) }
$trigger = @($times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ })
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Cào bài tuyển dụng Facebook, xuất CSV vào 2. Output\fb_leads" -Force | Out-Null

Write-Host "Đã đăng ký ${taskName}: mỗi ngày lúc $($times -join ', ')."
Write-Host "Chạy thử ngay : Start-ScheduledTask -TaskName $taskName"
Write-Host "Xem kết quả   : Get-ScheduledTaskInfo -TaskName $taskName ; log ở logs\scheduler_last_run.txt"
