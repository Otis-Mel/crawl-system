"""
FB DAILY CHECK - chạy 18:05 mỗi ngày (task FB-Scraper-DailyCheck): kiểm tra đủ 4 lượt, còn tiến trình nào chưa dừng không,
rồi gửi tổng kết ngày qua fb_notify.py.
"""

import csv
import subprocess
from datetime import datetime
from pathlib import Path

import fb_notify

WORK_DIR = Path(__file__).parent
LEADS_DIR = WORK_DIR.parent.parent / "2. Output" / "fb_leads"
MASTER_FILE = WORK_DIR.parent.parent / "2. Output" / "fb_master" / "fb_master.csv"
NOTIFY_LOG = WORK_DIR / "logs" / "notify_log.txt"
EXPECTED_PASSES = 3


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    lines = NOTIFY_LOG.read_text(encoding="utf-8").splitlines() if NOTIFY_LOG.exists() else []
    started = [l for l in lines if l.startswith(today) and "bắt đầu" in l]
    finished = [l for l in lines if l.startswith(today) and "xong lúc" in l and "phần" not in l]
    new = bo_sung = 0
    for f in LEADS_DIR.glob(f"fb_leads_{datetime.now():%Y%m%d}_*.csv"):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                kind = r.get("Loại dòng", "")
                new += kind == "Lead mới"
                bo_sung += kind == "Bổ sung"
    verified = total = 0
    if MASTER_FILE.exists():
        with open(MASTER_FILE, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                total += 1
                verified += r["Trạng thái"].startswith("Verified")
    running = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'fb_scraper_no_login_v2' }).Count"],
                             capture_output=True, text=True).stdout.strip()
    problems = []
    if len(started) < EXPECTED_PASSES:
        problems.append(f"chỉ {len(started)}/{EXPECTED_PASSES} lượt đã bắt đầu")
    if len(finished) < len(started):
        problems.append(f"{len(started) - len(finished)} lượt không báo hoàn thành")
    if running not in ("", "0"):
        problems.append(f"còn {running} tiến trình đang chạy sau 18:00")
    msg = (f"Tổng kết {today}: {len(started)}/{EXPECTED_PASSES} lượt chạy, {new} lead mới + {bo_sung} bổ sung. "
           f"Kho: {total} cụm, {verified} verified." + (" VẤN ĐỀ: " + "; ".join(problems) + "." if problems else ""))
    fb_notify.notify(msg, "error" if problems else "ok")


if __name__ == "__main__":
    main()
