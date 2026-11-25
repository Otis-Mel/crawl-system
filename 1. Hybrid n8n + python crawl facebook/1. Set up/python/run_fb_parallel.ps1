# Chạy 1 lượt scraper Facebook song song: chia groups.json thành N phần, mỗi phần 1 tiến trình python (ẩn).
#
# Lịch 3 lượt/ngày (Task Scheduler gọi file này): 09:00, 12:00, 15:00. Mỗi lượt có GIỜ DỪNG = 5 phút trước lượt kế
# (lượt cuối dừng lúc 17:40), nên toàn bộ tiến trình kết thúc trước 18:00. Quá giờ dừng: tiến trình tự dừng gọn (CSV đã ghi
# tới group cuối); nếu vẫn còn tiến trình sau 3 phút thì bị tắt cưỡng bức.
# Các tiến trình khởi động cách nhau 61 giây để tên file fb_leads_YYYYMMDD_HHMM.csv không trùng nhau.
# Thông báo (fb_notify.py): xong từng phần, tổng kết lượt, và LỖI khi có phần hỏng / lượt bị cắt giờ / không có lead.
param([int]$Procs = 4, [string]$GroupsFile = "groups.json")

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir
New-Item -ItemType Directory -Force logs, groups_parts | Out-Null
$utf8 = New-Object Text.UTF8Encoding($false)
$env:PYTHONIOENCODING = "utf-8"; [Console]::OutputEncoding = $utf8

$slots = @("09:00", "12:00", "15:00")
$now = Get-Date
$idx = 0
for ($i = 0; $i -lt $slots.Count; $i++) { if ($now -ge [datetime]::Parse($slots[$i]).AddMinutes(-20)) { $idx = $i } }
$deadline = if ($idx -lt $slots.Count - 1) { [datetime]::Parse($slots[$idx + 1]).AddMinutes(-5) } else { [datetime]::Parse("17:40") }
$hardKill = $deadline.AddMinutes(3)
$run = $now.ToString("yyyyMMdd_HHmm")

function Notify([string]$text, [string]$level = "info") {
    $f = "$dir\logs\notify_msg.txt"
    [IO.File]::WriteAllText($f, $text, $utf8)
    & py "$dir\fb_notify.py" --file $f --level $level | Out-Null
}

$groups = @(Get-Content (Join-Path $dir $GroupsFile) -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object { $_ })
$Procs = [Math]::Min($Procs, $groups.Count)
# Xoay vòng danh sách theo lượt để nếu một lượt bị cắt giờ thì các lượt khác cào phần đầu khác nhau
$shift = ($idx * [Math]::Ceiling($groups.Count / $slots.Count)) % $groups.Count
$groups = @($groups[$shift..($groups.Count - 1)]) + @(if ($shift -gt 0) { $groups[0..($shift - 1)] })

Notify "Lượt $($idx + 1)/3 bắt đầu $($now.ToString('HH:mm')): $($groups.Count) group, $Procs tiến trình, dừng lúc $($deadline.ToString('HH:mm'))"
$jobs = @(); $status = @(); $reported = @{}
for ($p = 0; $p -lt $Procs; $p++) {
    $part = @(for ($i = $p; $i -lt $groups.Count; $i += $Procs) { $groups[$i] })
    $file = "$dir\groups_parts\part_$p.json"
    [IO.File]::WriteAllText($file, (ConvertTo-Json -InputObject $part -Depth 3), $utf8)
    $sf = "$dir\logs\status_${run}_part_$p.json"
    $status += $sf
    if ($p -gt 0) { Start-Sleep -Seconds 61 }
    $jobs += Start-Process -FilePath "py" -ArgumentList "-u", "fb_scraper_no_login_v2.py", "--once", "--groups", "`"$file`"", `
        "--deadline", $deadline.ToString("HH:mm"), "--status-file", "`"$sf`"" `
        -WorkingDirectory $dir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$dir\logs\scheduler_part_$p.txt" -RedirectStandardError "$dir\logs\scheduler_part_${p}_err.txt"
    $null = $jobs[-1].Handle        # giữ handle để đọc được ExitCode sau khi tiến trình thoát
}

function ReadStatus($sf) { if (Test-Path $sf) { try { Get-Content $sf -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $null } } else { $null } }

$problems = @()
while (@($jobs | Where-Object { -not $_.HasExited }).Count -gt 0) {
    Start-Sleep -Seconds 20
    for ($p = 0; $p -lt $Procs; $p++) {
        if ($jobs[$p].HasExited -and -not $reported[$p]) {
            $reported[$p] = $true
            $s = ReadStatus $status[$p]
            if (($null -ne $jobs[$p].ExitCode -and $jobs[$p].ExitCode -ne 0) -or ($s -and $s.state -eq "failed") -or -not $s) {
                $problems += "phần $($p + 1) hỏng (mã $($jobs[$p].ExitCode))"
                Notify "Lượt $($idx + 1)/3 - phần $($p + 1)/$Procs HỎNG (mã $($jobs[$p].ExitCode)). Xem logs\scheduler_part_${p}_err.txt" "error"
            } else {
                $msg = "Lượt $($idx + 1)/3 - phần $($p + 1)/$Procs xong: $($s.lead_moi) lead mới, $($s.bo_sung) bổ sung, $($s.groups_done)/$($s.groups_total) group"
                if ($s.groups_failed.Count -gt 0) { $msg += ", lỗi $($s.groups_failed.Count) group"; $problems += "$($s.groups_failed.Count) group lỗi (phần $($p + 1))" }
                if ($s.groups_skipped_deadline -gt 0) { $msg += ", bỏ $($s.groups_skipped_deadline) group do hết giờ"; $problems += "hết giờ, bỏ $($s.groups_skipped_deadline) group (phần $($p + 1))" }
                Notify $msg $(if ($s.groups_failed.Count -gt 0 -or $s.groups_skipped_deadline -gt 0) { "error" } else { "ok" })
            }
        }
    }
    if ((Get-Date) -ge $hardKill) {
        foreach ($j in $jobs) { if (-not $j.HasExited) { & taskkill /PID $j.Id /T /F | Out-Null } }
        $problems += "bị tắt cưỡng bức lúc $($hardKill.ToString('HH:mm'))"
        Notify "Lượt $($idx + 1)/3 bị TẮT CƯỠNG BỨC lúc $($hardKill.ToString('HH:mm')) vì quá giờ dừng" "error"
        break
    }
}
foreach ($j in $jobs) { try { $j.WaitForExit(5000) | Out-Null } catch {} }

# Gom cụm + xét verified + tra tên đăng ký (tối đa 10 phút, phần chưa tra xong sẽ tra tiếp ở lượt sau)
$clusterOut = (& py "$dir\fb_cluster.py" 2>&1 | Out-String).Trim()
$clusterOut | Out-File "$dir\logs\cluster_last_run.txt" -Encoding utf8

# Mọi lượt: tóm tắt ngắn. Chỉ lượt cuối ngày: báo cáo Excel đầy đủ cả ngày (2. Output\bao_cao)
$isLast = ($idx -eq $slots.Count - 1)
$reportOut = (& py "$dir\fb_report.py" $run ($idx + 1) $(if ($isLast) { "--full" }) 2>&1 | Out-String).Trim()
$reportOut | Out-File "$dir\logs\report_last_run.txt" -Encoding utf8
$reportPath = ($reportOut -split "\|")[0]

$tot = @($status | ForEach-Object { ReadStatus $_ } | Where-Object { $_ })
$new = ($tot | Measure-Object -Property lead_moi -Sum).Sum; $add = ($tot | Measure-Object -Property bo_sung -Sum).Sum
$level = if ($problems.Count -gt 0 -or ($new + $add) -eq 0) { "error" } else { "ok" }
if (($new + $add) -eq 0) { $problems += "không có lead nào" }
$summary = "Lượt $($idx + 1)/3 xong lúc $((Get-Date).ToString('HH:mm')): $new lead mới, $add bổ sung cho lead cũ." + $(if ($problems.Count -gt 0) { " Vấn đề: " + ($problems -join "; ") + "." } else { "" })
$shortLine = ($reportOut -split "\|", 2)[1]
Notify ($summary + "`n" + $shortLine + $(if ($isLast) { "`nBáo cáo cả ngày: " + $reportPath } else { "" })) $level
"$summary" | Out-File "$dir\logs\scheduler_last_run.txt" -Encoding utf8
exit $(if ($problems.Count -gt 0) { 1 } else { 0 })
