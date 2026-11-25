"""
Tạo customers_index.csv (tên công ty đã chuẩn hóa -> ID CRM) từ "10. All Sources.xlsx". Chỉ đọc file gốc.

Chạy : py build_customer_index.py
       py build_customer_index.py --src "D:\\duong_dan\\10. All Sources.xlsx" --out "D:\\...\\customers_index.csv"
Khuyến nghị chạy trên một bản sao của file Excel nếu file gốc đang mở (bị khóa).
"""

import sys
from pathlib import Path

import pandas as pd

import fb_customers

WORK_DIR = Path(__file__).parent
SRC = Path(r"D:\OneDrive - Kariera Group\handover - MinhCao\02. Follow Client\10. All Sources.xlsx")
OUT = WORK_DIR.parent.parent / "3. Reference" / "customers_index.csv"
if "--src" in sys.argv:
    SRC = Path(sys.argv[sys.argv.index("--src") + 1])
if "--out" in sys.argv:
    OUT = Path(sys.argv[sys.argv.index("--out") + 1])


def main():
    df = pd.read_excel(SRC, sheet_name=0, dtype=str, usecols=["Company Name", "ID CRM"])
    df = df.dropna(subset=["Company Name", "ID CRM"])
    df["ID CRM"] = df["ID CRM"].str.strip()
    df = df[df["ID CRM"] != ""]
    df["norm_name"] = df["Company Name"].map(fb_customers.normalize)
    df = df[df["norm_name"] != ""]

    # mỗi tên chuẩn hóa -> ID CRM xuất hiện nhiều nhất, kèm một tên gốc làm mẫu
    best = (df.groupby(["norm_name", "ID CRM"]).size().reset_index(name="n")
              .sort_values(["norm_name", "n"], ascending=[True, False]).drop_duplicates("norm_name"))
    sample = df.drop_duplicates("norm_name").set_index("norm_name")["Company Name"]
    out = pd.DataFrame({"norm_name": best["norm_name"], "crm_id": best["ID CRM"],
                        "sample_name": best["norm_name"].map(sample)})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Đã tạo {OUT}: {len(out)} tên chuẩn hóa từ {len(df)} dòng nguồn ({df['ID CRM'].nunique()} ID CRM)")


if __name__ == "__main__":
    main()
