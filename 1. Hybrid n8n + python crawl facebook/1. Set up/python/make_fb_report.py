"""
Tạo báo cáo Excel từ các file fb_leads_*.csv (bản chụp tại thời điểm chạy, chạy lại để cập nhật).

Chạy : py make_fb_report.py
       py make_fb_report.py --csv-dir D:\\thu_muc_csv --out D:\\bao_cao.xlsx
Sheet: Tổng quan (số chính + biểu đồ), Theo ngày, Theo group, Theo tỉnh, Theo ngành, Lương, Leads (toàn bộ dữ liệu)
"""

import sys
from pathlib import Path

import pandas as pd

WORK_DIR = Path(__file__).parent
CSV_DIR = WORK_DIR.parent.parent / "2. Output" / "fb_leads"
OUT = CSV_DIR.parent / "FB_Leads_Report.xlsx"
if "--csv-dir" in sys.argv:
    CSV_DIR = Path(sys.argv[sys.argv.index("--csv-dir") + 1])
if "--out" in sys.argv:
    OUT = Path(sys.argv[sys.argv.index("--out") + 1])


def load():
    files = sorted(CSV_DIR.glob("fb_leads_*.csv"))
    if not files:
        raise SystemExit(f"Không có file fb_leads_*.csv trong {CSV_DIR}")
    df = pd.concat((pd.read_csv(f, dtype=str, encoding="utf-8-sig", keep_default_na=False) for f in files),
                   ignore_index=True)
    df = df.drop_duplicates(subset=["Link bài viết"], keep="first")
    for c in ("STT", "Điểm lead", "Lương min (triệu)", "Lương max (triệu)"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Ngày crawl"] = pd.to_datetime(df["Thời gian crawl"], errors="coerce").dt.date
    return df


def count_by(df, col, empty_label="(không rõ)", top=None):
    s = df[col].replace("", empty_label).fillna(empty_label)
    t = s.value_counts().rename_axis(col).reset_index(name="Số lead")
    if top and len(t) > top:
        rest = t.iloc[top:]["Số lead"].sum()
        t = pd.concat([t.iloc[:top], pd.DataFrame({col: ["(các mục còn lại)"], "Số lead": [rest]})], ignore_index=True)
    return t


def salary_by_industry(df):
    d = df[(df["Lương min (triệu)"].notna()) | (df["Lương max (triệu)"].notna())].copy()
    d["mid"] = d[["Lương min (triệu)", "Lương max (triệu)"]].mean(axis=1)
    d = d[d["Ngành"] != ""]
    g = d.groupby("Ngành")["mid"].agg(["count", "median"]).reset_index()
    g.columns = ["Ngành", "Số bài có lương", "Lương trung vị (triệu)"]
    g["Lương trung vị (triệu)"] = g["Lương trung vị (triệu)"].round(1)
    return g.sort_values("Số bài có lương", ascending=False)


def main():
    df = load()
    n = len(df)
    has_crm = "Trạng thái CRM" in df.columns and (df["Trạng thái CRM"] != "").any()

    kpi = [
        ("Tổng số lead", n),
        ("Số ngày có dữ liệu", df["Ngày crawl"].nunique()),
        ("Lead điểm ≥ 70", int((df["Điểm lead"] >= 70).sum())),
        ("Lead có email doanh nghiệp", int((df["Loại email"] == "Doanh nghiệp").sum())),
        ("Lead có SĐT", int((df["SĐT"] != "").sum())),
        ("Lead có tên công ty", int((df["Tên công ty"] != "").sum())),
        ("Lead có mức lương", int((df["Lương"] != "").sum())),
        ("Nghi tuyển dụng hộ", int(df["Ghi chú lead"].str.contains("tuyển dụng hộ", na=False).sum())),
    ]
    if has_crm:
        kpi += [("Có trong CRM", int((df["Trạng thái CRM"] == "Có trong CRM").sum())),
                ("Nghi trùng CRM (cần kiểm tra)", int((df["Trạng thái CRM"] == "Nghi trùng CRM").sum()))]

    by_day = df.groupby("Ngày crawl").size().reset_index(name="Số lead").sort_values("Ngày crawl")
    by_group = count_by(df, "Group")
    by_prov = count_by(df, "Tỉnh/Thành", top=15)
    by_ind = count_by(df, "Ngành")
    sal = salary_by_industry(df)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="xlsxwriter", engine_kwargs={"options": {"strings_to_urls": False}}) as xw:
        wb = xw.book
        h = wb.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white", "border": 1})
        big = wb.add_format({"bold": True, "font_size": 16})
        num = wb.add_format({"num_format": "#,##0"})

        # --- Tổng quan
        ws = wb.add_worksheet("Tổng quan")
        xw.sheets["Tổng quan"] = ws
        ws.write("A1", "Báo cáo lead từ bài tuyển dụng Facebook", big)
        ws.write("A2", f"Dữ liệu từ {df['Ngày crawl'].min()} đến {df['Ngày crawl'].max()} · "
                       f"nguồn: {CSV_DIR.name} · tạo lúc {pd.Timestamp.now():%Y-%m-%d %H:%M}")
        ws.write_row("A4", ["Chỉ số", "Giá trị", "Tỷ lệ"], h)
        for i, (k, v) in enumerate(kpi):
            ws.write(4 + i, 0, k)
            ws.write(4 + i, 1, v, num)
            if i > 0 and k != "Số ngày có dữ liệu":
                ws.write(4 + i, 2, v / n, wb.add_format({"num_format": "0%"}))
        ws.set_column("A:A", 34); ws.set_column("B:C", 12)

        def table(name, frame, widths):
            frame.to_excel(xw, sheet_name=name, index=False)
            sh = xw.sheets[name]
            for j, col in enumerate(frame.columns):
                sh.write(0, j, col, h)
            for j, w in enumerate(widths):
                sh.set_column(j, j, w)
            sh.freeze_panes(1, 0)
            return sh

        table("Theo ngày", by_day, [14, 10])
        table("Theo group", by_group, [28, 10])
        table("Theo tỉnh", by_prov, [26, 10])
        table("Theo ngành", by_ind, [34, 10])
        table("Lương", sal, [34, 16, 22])

        def chart(kind, title, sheet, rows, anchor, w=520, hgt=300):
            c = wb.add_chart({"type": kind})
            c.add_series({"name": title, "categories": [sheet, 1, 0, rows, 0], "values": [sheet, 1, 1, rows, 1]})
            c.set_title({"name": title}); c.set_legend({"none": True}); c.set_size({"width": w, "height": hgt})
            if kind == "column":
                c.set_x_axis({"text_axis": True})      # chỉ hiện các ngày có dữ liệu, không chia theo lịch
            else:
                c.set_y_axis({"reverse": True})        # mục lớn nhất nằm trên cùng
            ws.insert_chart(anchor, c)

        chart("column", "Lead theo ngày crawl", "Theo ngày", len(by_day), "E3")
        chart("bar", "Lead theo tỉnh/thành", "Theo tỉnh", len(by_prov), "E19", hgt=380)
        chart("bar", "Lead theo ngành", "Theo ngành", len(by_ind), "E39", hgt=380)

        # --- Leads (toàn bộ)
        cols = [c for c in df.columns if c != "Ngày crawl"]
        df[cols].to_excel(xw, sheet_name="Leads", index=False)
        sh = xw.sheets["Leads"]
        for j, col in enumerate(cols):
            sh.write(0, j, col, h)
        sh.freeze_panes(1, 2)
        sh.autofilter(0, 0, len(df), len(cols) - 1)
        widths = {"Nội dung bài viết": 60, "Tên công ty": 32, "Địa chỉ": 34, "Link bài viết": 30, "Ghi chú lead": 36}
        for j, col in enumerate(cols):
            sh.set_column(j, j, widths.get(col, 16))
        if "Điểm lead" in cols:
            j = cols.index("Điểm lead")
            sh.conditional_format(1, j, len(df), j, {"type": "3_color_scale", "min_color": "#F8696B",
                                                     "mid_color": "#FFEB84", "max_color": "#63BE7B"})
    print(f"Đã tạo {OUT} ({n} lead)")


if __name__ == "__main__":
    main()
