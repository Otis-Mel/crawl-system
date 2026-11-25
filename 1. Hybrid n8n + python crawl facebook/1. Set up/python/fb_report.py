"""
FB REPORT - báo cáo Excel sau mỗi lượt crawl

Chạy: python fb_report.py <run> <số lượt>      vd: python fb_report.py 20261104_0901 1
(run_fb_parallel.ps1 gọi sau khi gom cụm xong; in ra đường dẫn file và một dòng tóm tắt)

Ghi nhớ tóm tắt từng lượt trong logs\\pass_summary_YYYYMMDD.json rồi dựng lại file
2. Output\\bao_cao\\BaoCao_FB_Crawl_YYYYMMDD.xlsx (mỗi lượt xong cập nhật thêm một dòng):
  - Theo lượt          : mỗi lượt một dòng (dòng ghi, lead mới, bổ sung, trùng bỏ, group lỗi...), có dòng tổng
  - Chất lượng kho     : số cụm Verified / Cần check tại thời điểm lượt cuối
  - Group lỗi          : group nào lỗi ở lượt nào
  - Nhà tuyển dụng mới : các cụm xuất hiện lần đầu trong ngày (tên, email, SĐT, trạng thái, group, link)
"""

import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

WORK_DIR = Path(__file__).parent
LOG_DIR = WORK_DIR / "logs"
REPORT_DIR = WORK_DIR.parent.parent / "2. Output" / "bao_cao"
MASTER_FILE = WORK_DIR.parent.parent / "2. Output" / "fb_master" / "fb_master.csv"

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
TOTAL_FILL = PatternFill("solid", fgColor="F2F2F2")
_thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
WRAP = Alignment(wrap_text=True, vertical="top")


def pass_summary(run, number):
    """Gộp các file trạng thái của các phần (part) thuộc một lượt."""
    parts = []
    for f in sorted(LOG_DIR.glob(f"status_{run}_part_*.json")):
        try:
            parts.append(json.loads(f.read_text(encoding="utf-8-sig")))
        except Exception:
            parts.append({"state": "failed"})
    s = {"luot": number, "bat_dau": f"{run[:4]}-{run[4:6]}-{run[6:8]} {run[9:11]}:{run[11:13]}",
         "ket_thuc": datetime.now().strftime("%H:%M"), "so_phan": len(parts),
         "phan_hong": sum(1 for p in parts if p.get("state") == "failed"),
         "group_tong": sum(p.get("groups_total", 0) for p in parts), "group_xong": sum(p.get("groups_done", 0) for p in parts),
         "group_loi": [(i + 1, n) for i, p in enumerate(parts) for n in p.get("groups_failed", [])],
         "bo_qua_gio": sum(p.get("groups_skipped_deadline", 0) for p in parts),
         "dong_ghi": sum(p.get("rows", 0) for p in parts), "lead_moi": sum(p.get("lead_moi", 0) for p in parts),
         "bo_sung": sum(p.get("bo_sung", 0) for p in parts), "trung_bo": sum(p.get("trung", 0) for p in parts)}
    return s


def load_master():
    if not MASTER_FILE.exists():
        return []
    with open(MASTER_FILE, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _head(ws, row, headers):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        cell.border = BORDER


def _rows(ws, top, rows):
    for r, row in enumerate(rows, top):
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name=FONT, size=10)
            cell.alignment = WRAP
            cell.border = BORDER


def build_workbook(day, passes, master):
    wb = Workbook()
    ws = wb.active
    ws.title = "Theo lượt"
    ws["A1"] = f"Báo cáo crawl Facebook ngày {day[6:8]}/{day[4:6]}/{day[:4]}"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F4E78")
    ws["A2"] = "Lead mới = nhà tuyển dụng chưa có trong kho; Bổ sung = nhà tuyển dụng cũ được thêm email/SĐT/tên công ty; Trùng bỏ = bài không thêm thông tin nào."
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="595959")
    heads = ["Lượt", "Bắt đầu", "Kết thúc", "Group xong", "Group tổng", "Group lỗi", "Bỏ vì hết giờ", "Phần hỏng",
             "Dòng ghi", "Lead mới", "Bổ sung", "Trùng bỏ"]
    _head(ws, 4, heads)
    rows = [(p["luot"], p["bat_dau"][11:], p["ket_thuc"], p["group_xong"], p["group_tong"], len(p["group_loi"]), p["bo_qua_gio"],
             p["phan_hong"], p["dong_ghi"], p["lead_moi"], p["bo_sung"], p["trung_bo"]) for p in passes]
    _rows(ws, 5, rows)
    last = 4 + len(rows)
    tot = last + 1
    ws.cell(row=tot, column=1, value="Tổng ngày")
    for c in range(4, 13):
        col = get_column_letter(c)
        ws.cell(row=tot, column=c, value=f"=SUM({col}5:{col}{last})")
    for c in range(1, 13):
        cell = ws.cell(row=tot, column=c)
        cell.font = Font(name=FONT, size=10, bold=True)
        cell.fill = TOTAL_FILL
        cell.border = BORDER
    for i, w in enumerate([8, 10, 10, 11, 11, 10, 13, 11, 10, 10, 10, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws = wb.create_sheet("Chất lượng kho")
    cnt = Counter(m["Trạng thái"] for m in master)
    _head(ws, 1, ["Trạng thái", "Số cụm", "Tỉ lệ"])
    states = ["Verified đủ 3/3", "Verified 2/3", "Cần check"]
    _rows(ws, 2, [(s, cnt.get(s, 0), None) for s in states])
    ws.cell(row=5, column=1, value="Tổng cụm")
    ws.cell(row=5, column=2, value="=SUM(B2:B4)")
    for r in range(2, 6):
        ws.cell(row=r, column=3, value=f"=IF($B$5=0,0,B{r}/$B$5)").number_format = "0.0%"
    for c in range(1, 4):
        ws.cell(row=5, column=c).font = Font(name=FONT, size=10, bold=True)
        ws.cell(row=5, column=c).fill = TOTAL_FILL
        ws.cell(row=5, column=c).border = BORDER
    src = Counter(m["Độ tin tên công ty"] for m in master if m["Độ tin tên công ty"])
    _head(ws, 7, ["Nguồn tên công ty", "Số cụm"])
    _rows(ws, 8, sorted(src.items(), key=lambda x: -x[1]))
    for i, w in enumerate([44, 12, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws = wb.create_sheet("Group lỗi")
    _head(ws, 1, ["Lượt", "Phần", "Group"])
    errs = [(p["luot"], ph, n) for p in passes for ph, n in p["group_loi"]]
    _rows(ws, 2, errs or [("—", "—", "Không có group lỗi")])
    for i, w in enumerate([8, 8, 70], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws = wb.create_sheet("Nhà tuyển dụng mới")
    today = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
    new = [m for m in master if m["Lần đầu thấy"].startswith(today)]
    _head(ws, 1, ["Trạng thái", "Tên công ty", "Độ tin tên", "Email", "SĐT", "Cần bổ sung", "Vị trí tuyển", "Tỉnh/Thành", "Group", "Link bài đầu"])
    _rows(ws, 2, [(m["Trạng thái"], m["Tên công ty"], m["Độ tin tên công ty"], m["Email"], m["SĐT"], m["Cần bổ sung"],
                   m["Vị trí tuyển"], m["Tỉnh/Thành"], m["Group"], m["Link bài đầu"]) for m in new])
    for i, w in enumerate([16, 34, 20, 34, 24, 26, 30, 18, 28, 50], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:J{max(2, len(new) + 1)}"

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = False
    wb.calculation.fullCalcOnLoad = True
    return wb, len(new)


def main(run, number, full=False):
    day = run[:8]
    summ_file = LOG_DIR / f"pass_summary_{day}.json"
    passes = json.loads(summ_file.read_text(encoding="utf-8")) if summ_file.exists() else []
    passes = [p for p in passes if p["luot"] != number] + [pass_summary(run, number)]
    passes.sort(key=lambda p: p["luot"])
    summ_file.write_text(json.dumps(passes, ensure_ascii=False, indent=1), encoding="utf-8")
    master = load_master()
    cnt = Counter(m["Trạng thái"] for m in master)
    p = passes[[x["luot"] for x in passes].index(number)]
    short = (f"Lượt {number}: {p['lead_moi']} lead mới, {p['bo_sung']} bổ sung, {p['group_xong']}/{p['group_tong']} group"
             f" ({len(p['group_loi'])} lỗi). Kho {len(master)} cụm, verified {cnt.get('Verified đủ 3/3', 0) + cnt.get('Verified 2/3', 0)}.")
    if not full:
        print("|" + short)
        return
    wb, n_new = build_workbook(day, passes, master)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"BaoCao_FB_Crawl_{day}.xlsx"
    wb.save(path)
    total = sum(x["lead_moi"] for x in passes)
    print(f"{path}|{short} Cả ngày: {total} lead mới, {sum(x['bo_sung'] for x in passes)} bổ sung qua {len(passes)} lượt.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], int(sys.argv[2]), "--full" in sys.argv)
