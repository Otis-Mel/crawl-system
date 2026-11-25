"""Crawl doanh nghiệp mới thành lập từ doanhnghiep.biz -> Excel (OneDrive ổ D).

Thay cho workflow n8n + Google Sheet. Chạy lặp lại được: MST đã có trong file sẽ bị bỏ qua,
và dừng sớm khi gặp trang mà toàn bộ MST đã có (danh sách sắp theo mới nhất trước).

Dùng:
    python crawl_dn_moi.py                 # chạy bình thường (tối đa 300 trang)
    python crawl_dn_moi.py --max-pages 3   # chạy thử
"""
import argparse
import html as htmllib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests
from openpyxl import Workbook, load_workbook

BASE = "https://doanhnghiep.biz"
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "2. Output" / "Doanh nghiep moi thanh lap.xlsx"
HEADERS = ["STT", "MST", "Tên công ty", "Người đại diện", "Địa chỉ", "Ngành nghề",
           "Ngày cấp", "SĐT", "Email", "Ngày crawl", "Link masothue"]
NA = "Chua cap nhat"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

session = requests.Session()
session.headers.update(UA)


def get(url, retries=3):
    for i in range(retries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 * (i + 1))
    return ""


def norm_mst(v):
    s = re.sub(r"\s+", "", str(v or "")).strip('"')
    return s.zfill(10) if s.isdigit() and len(s) < 10 else s


def list_page_msts(page):
    """Trả về MST (theo thứ tự xuất hiện, không trùng) của 1 trang danh sách."""
    url = BASE + "/" if page == 1 else f"{BASE}/?p={page}"
    for attempt in range(3):  # site thỉnh thoảng trả trang rỗng khi bị gọi dồn
        t = get(url)
        seen = []
        for m in re.finditer(r'href=["\']/(\d{10,13})-[^"\']+', t):
            if m.group(1) not in seen:
                seen.append(m.group(1))
        if seen:
            return seen
        time.sleep(5 * (attempt + 1))
    return []


def strip_tags(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def decode_cf(enc):
    key = int(enc[:2], 16)
    return "".join(chr(int(enc[i:i + 2], 16) ^ key) for i in range(2, len(enc), 2))


def field(t, prop):
    m = re.search(rf'itemprop="{prop}"[^>]*>(.*?)</td>', t, re.S)
    if not m:
        return NA
    cf = re.search(r'data-cfemail="([0-9a-f]+)"', m.group(1))
    v = decode_cf(cf.group(1)) if cf else strip_tags(m.group(1))
    return v if v and v not in ("null", "undefined") else NA


def parse_date(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except ValueError:
        return s


def fetch_detail(mst):
    t = get(f"{BASE}/{mst}")
    if not t:
        return None
    title = re.search(r"<title>([^<]+)</title>", t)
    parts = re.split(r"\s+-\s+", htmllib.unescape(title.group(1))) if title else []
    ten = " - ".join(parts[1:-1]).strip() if len(parts) >= 3 else NA
    ndd = re.search(r'<span itemprop="Owner">\s*<a[^>]*>([^<]+)</a>', t)
    ngay = field(t, "IncorporatedDate")
    return {
        "mst": mst,
        "ten": ten,
        "ndd": ndd.group(1).strip() if ndd else NA,
        "diachi": field(t, "address"),
        "nganh": NA,  # trang chi tiết không hiển thị ngành nghề
        "ngaycap": parse_date(ngay) if ngay != NA else NA,
        "sdt": field(t, "Phone"),
        "email": field(t, "Email"),
    }


def load_existing():
    if not OUTPUT.exists():
        return [], set()
    ws = load_workbook(OUTPUT).active
    rows = [list(r) for r in ws.iter_rows(min_row=2, values_only=True) if r[1]]
    return rows, {norm_mst(r[1]) for r in rows}


def save(rows):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HEADERS)
    for i, r in enumerate(rows, 1):
        r = list(r)
        r[0] = i
        ws.append(r)
    for row in ws.iter_rows(min_row=2):
        row[1].number_format = "@"  # MST dạng text, giữ số 0 đầu
        row[6].number_format = "dd/mm/yyyy"
        row[9].number_format = "dd/mm/yyyy"
    for col, w in zip("ABCDEFGHIJK", [6, 14, 50, 24, 60, 18, 12, 14, 30, 12, 38]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    tmp = OUTPUT.with_suffix(".tmp.xlsx")
    wb.save(tmp)
    tmp.replace(OUTPUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--full", action="store_true", help="quét hết các trang, không dừng sớm")
    args = ap.parse_args()

    rows, known = load_existing()
    print(f"File hiện có {len(rows)} dòng")
    today = datetime.combine(datetime.now().date(), datetime.min.time())
    added = 0

    for page in range(1, args.max_pages + 1):
        msts = list_page_msts(page)
        if not msts:
            print(f"Trang {page}: không có dữ liệu, dừng")
            break
        new = [m for m in msts if m not in known]
        print(f"Trang {page}: {len(msts)} DN, {len(new)} mới")
        if not new:
            if args.full:
                continue
            print("Toàn bộ đã có trong file -> dừng sớm")
            break
        with ThreadPoolExecutor(args.workers) as ex:
            for d in ex.map(fetch_detail, new):
                if not d:
                    continue
                known.add(d["mst"])
                rows.append([None, d["mst"], d["ten"], d["ndd"], d["diachi"], d["nganh"],
                             d["ngaycap"], d["sdt"], d["email"], today, f"{BASE}/{d['mst']}"])
                added += 1
        if page % 5 == 0:
            save(rows)
        time.sleep(1)

    save(rows)
    print(f"Xong: thêm {added} DN, tổng {len(rows)} -> {OUTPUT}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
