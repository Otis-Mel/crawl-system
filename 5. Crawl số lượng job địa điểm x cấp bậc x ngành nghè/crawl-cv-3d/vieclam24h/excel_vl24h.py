"""
Ghi dữ liệu Vieclam24h vào file Excel CHUNG (CV_Count_Tracker.xlsx).
1 sheet 3D:
  - VL24h (Ngành nghề × Địa điểm × Kinh nghiệm)
"""
import os
import sys
from datetime import date

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

sys.stdout.reconfigure(encoding="utf-8")

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_FILE = os.environ.get("CV_EXCEL_FILE") or os.path.join(_DIR, "CV_Count_Tracker.xlsx")

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF")
DATE_FILL   = PatternFill("solid", fgColor="D6E4F0")

SHEET_NAME = "VL24h"


def _ensure_sheet(wb: openpyxl.Workbook, kn_names: list[str]):
    if SHEET_NAME in wb.sheetnames:
        return wb[SHEET_NAME]

    ws = wb.create_sheet(SHEET_NAME)
    header = ["Date", "Ngành", "Địa điểm"] + kn_names
    ws.append(header)

    for cell in ws[1]:
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 24
    for col in range(4, 4 + len(kn_names)):
        ws.column_dimensions[
            openpyxl.utils.get_column_letter(col)
        ].width = 14

    return ws


def _write_rows(ws, today: str, rows: list[dict], kn_names: list[str]):
    for row_data in rows:
        counts = row_data["counts"]
        row = [today, row_data["industry"], row_data["location"]] + [
            counts.get(kn, 0) for kn in kn_names
        ]
        ws.append(row)
        date_cell = ws.cell(ws.max_row, 1)
        date_cell.fill      = DATE_FILL
        date_cell.alignment = Alignment(horizontal="center")
        for col in range(4, 4 + len(kn_names)):
            ws.cell(ws.max_row, col).alignment = Alignment(horizontal="center")


def has_today_data() -> bool:
    if not os.path.exists(EXCEL_FILE):
        return False
    wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True)
    if SHEET_NAME not in wb.sheetnames:
        return False
    today = date.today().strftime("%Y-%m-%d")
    ws = wb[SHEET_NAME]
    for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
        if row[0] == today:
            return True
    return False


def get_today_done_pairs() -> set[tuple[str, str]]:
    """Trả về set (Ngành, Địa điểm) đã ghi — nhận cả hôm nay lẫn hôm qua để resume qua đêm."""
    done: set[tuple[str, str]] = set()
    if not os.path.exists(EXCEL_FILE):
        return done
    wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True)
    if SHEET_NAME not in wb.sheetnames:
        return done
    from datetime import timedelta
    resume_dates = {
        date.today().strftime("%Y-%m-%d"),
        (date.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
    }
    ws = wb[SHEET_NAME]
    for row in ws.iter_rows(min_row=2, max_col=3, values_only=True):
        if row[0] in resume_dates:
            done.add((row[1], row[2]))
    return done


def append_rows(rows: list[dict], kn_names: list[str]) -> None:
    """Checkpoint: append rows vào Excel (không kiểm tra duplicate)."""
    today = date.today().strftime("%Y-%m-%d")

    if os.path.exists(EXCEL_FILE):
        wb = openpyxl.load_workbook(EXCEL_FILE)
    else:
        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

    ws = _ensure_sheet(wb, kn_names)
    _write_rows(ws, today, rows, kn_names)
    wb.save(EXCEL_FILE)
    print(f"[vl24h/excel] checkpoint: +{len(rows)} dòng", flush=True)


def save_dimension(rows: list[dict], kn_names: list[str]) -> None:
    """Lưu toàn bộ rows sau khi crawl xong — bỏ qua nếu today đã có."""
    today = date.today().strftime("%Y-%m-%d")

    if os.path.exists(EXCEL_FILE):
        wb = openpyxl.load_workbook(EXCEL_FILE)
    else:
        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

    ws = _ensure_sheet(wb, kn_names)

    for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
        if row[0] == today:
            print(f"[vl24h/excel] {SHEET_NAME}: {today} đã có — skip")
            return

    _write_rows(ws, today, rows, kn_names)
    wb.save(EXCEL_FILE)
    print(f"[vl24h/excel] {SHEET_NAME}: +{len(rows)} dòng ({today})")
