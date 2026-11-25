$TaskName   = "CareerViet CV Crawler"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatFile    = Join-Path $ProjectDir "run.bat"

# Kiểm tra run.bat tồn tại
if (-not (Test-Path $BatFile)) {
    Write-Host "Không tìm thấy run.bat tại: $BatFile" -ForegroundColor Red
    exit 1
}

# Xóa task cũ nếu có
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Đã xóa task cũ." -ForegroundColor Yellow
}

# Action: chạy run.bat
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`"" `
    -WorkingDirectory $ProjectDir

# Settings — không giới hạn thời gian (crawl ~10h)
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Placeholder trigger (monthly không hỗ trợ trong PS 5.1 → set qua COM bên dưới)
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"

# Đăng ký task (chạy dưới user hiện tại)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Force | Out-Null

# Đổi trigger sang mùng 5 hàng tháng qua COM (PS 5.1 không có -Monthly)
$Scheduler = New-Object -ComObject "Schedule.Service"
$Scheduler.Connect()
$TaskObj = $Scheduler.GetFolder("\").GetTask($TaskName)
$TaskDef = $TaskObj.Definition
$TaskDef.Triggers.Clear()
$MonthlyTrigger = $TaskDef.Triggers.Create(4)   # 4 = TASK_TRIGGER_MONTHLY
$MonthlyTrigger.DaysOfMonth  = [int][Math]::Pow(2, 4)  # ngày 5 = bit index 4
$MonthlyTrigger.MonthsOfYear = 4095                      # tất cả 12 tháng
$MonthlyTrigger.StartBoundary = "2026-01-05T09:00:00"
$MonthlyTrigger.Enabled = $true
$Scheduler.GetFolder("\").RegisterTaskDefinition($TaskName, $TaskDef, 4, $null, $null, 3) | Out-Null

$NextRun = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "  Task da duoc dang ky thanh cong!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Ten task : $TaskName"
Write-Host "  Chay luc : Mung 5 hang thang luc 09:00 sang"
Write-Host "  Next run : $NextRun"
Write-Host "  File bat : $BatFile"
Write-Host "  Log      : $ProjectDir\logs\YYYY-MM-DD.txt"
Write-Host ""
Write-Host "Kiem tra trong Task Scheduler:" -ForegroundColor Cyan
Write-Host "  taskschd.msc -> Task Scheduler Library -> '$TaskName'"
Write-Host ""
