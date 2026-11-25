import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

from careerviet.auth import get_session
from careerviet.mappings import fetch_industries, fetch_locations, fetch_levels
from careerviet.crawler import crawl_all


def main():
    start = datetime.now()
    print()
    print("=" * 60)
    print(f"  CareerViet CV Crawler — {start.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n[1/3] Kiểm tra session...")
    session = get_session()

    print("\n[2/3] Lấy danh sách ngành nghề, địa điểm, cấp bậc...")
    levels     = fetch_levels(session)
    industries = fetch_industries(session)
    locations  = fetch_locations(session)
    level_names = [lv["name"] for lv in levels]
    print(f"      {len(industries)} ngành — {len(locations)} địa điểm — {len(levels)} cấp bậc")

    total_pairs   = len(industries) * len(locations)
    probe_req     = total_pairs
    detail_req    = total_pairs * len(levels) // 2  # ~50% non-zero
    est_minutes   = int((probe_req + detail_req) * 0.4 / 60)
    print(f"      ~{total_pairs} cặp (Ngành × ĐĐ), ước tính ~{est_minutes} phút")

    print("\n[3/3] Bắt đầu crawl (checkpoint mỗi 200 hàng)...\n")
    crawl_all(session, industries, locations, levels)

    elapsed = (datetime.now() - start).seconds // 60
    print(f"\n  Hoàn thành trong {elapsed} phút.")
    print("=" * 60)
    print()


def run_vietnamworks():
    from vietnamworks.auth import get_session as vnw_session
    from vietnamworks.mappings import (
        get_cap_bac,
        fetch_linh_vuc,
        fetch_nganh_nghe,
        fetch_dia_diem,
    )
    from vietnamworks.crawler import crawl_all as vnw_crawl_all

    start = datetime.now()
    print()
    print("=" * 60)
    print(f"  VietnamWorks CV Crawler — {start.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    print("\n[1/3] Kiểm tra session...")
    session = vnw_session()

    print("\n[2/3] Lấy danh sách lĩnh vực, ngành, địa điểm, cấp bậc...")
    cap_bac    = get_cap_bac()
    linh_vuc   = fetch_linh_vuc(session)
    nganh_nghe = fetch_nganh_nghe(session)
    dia_diem   = fetch_dia_diem(session)
    print(
        f"      {len(linh_vuc)} lĩnh vực — {len(nganh_nghe)} ngành — "
        f"{len(dia_diem)} địa điểm — {len(cap_bac)} cấp bậc"
    )

    lv_pairs    = len(linh_vuc)   * len(dia_diem)
    nghanh_pairs = len(nganh_nghe) * len(dia_diem)
    total_pairs = lv_pairs + nghanh_pairs
    detail_req  = total_pairs * len(cap_bac) // 2
    est_minutes = int((total_pairs + detail_req) * 0.4 / 60)
    print(f"      ~{total_pairs} cặp tổng, ước tính ~{est_minutes} phút")

    print("\n[3/3] Bắt đầu crawl (checkpoint mỗi 200 hàng)...\n")
    vnw_crawl_all(session, linh_vuc, nganh_nghe, dia_diem, cap_bac)

    elapsed = (datetime.now() - start).seconds // 60
    print(f"\n  Hoàn thành trong {elapsed} phút.")
    print("=" * 60)


def run_vieclam24h(sample: bool = False):
    """
    Crawl Vieclam24h — 3D: Ngành × Địa điểm × Kinh nghiệm.
    sample=True → 10 ngành × 10 địa điểm đầu để test nhanh.
    """
    from vieclam24h.auth import get_session as vl24h_session
    from vieclam24h.mappings import (
        fetch_nganh_nghe,
        fetch_dia_diem,
        get_kinh_nghiem,
    )
    from vieclam24h.crawler import crawl_all as vl24h_crawl_all

    start = datetime.now()
    print()
    print("=" * 60)
    mode = "SAMPLE (10 đầu)" if sample else "FULL"
    print(f"  Vieclam24h CV Crawler — {start.strftime('%Y-%m-%d %H:%M')} [{mode}]")
    print("=" * 60)

    print("\n[1/3] Kiểm tra session...")
    session = vl24h_session()

    print("\n[2/3] Lấy danh sách ngành, địa điểm, kinh nghiệm...")
    nganh_nghe  = fetch_nganh_nghe()
    dia_diem    = fetch_dia_diem()
    kinh_nghiem = get_kinh_nghiem()
    print(
        f"      {len(nganh_nghe)} ngành — {len(dia_diem)} địa điểm — "
        f"{len(kinh_nghiem)} mức kinh nghiệm"
    )

    limit    = 10 if sample else None
    n_nganh  = min(len(nganh_nghe), limit) if limit else len(nganh_nghe)
    n_dd     = min(len(dia_diem),   limit) if limit else len(dia_diem)
    pairs    = n_nganh * n_dd
    detail   = pairs * len(kinh_nghiem) // 2
    est_min  = int((pairs + detail) * 0.5 / 60)
    print(f"      ~{pairs} cặp (Ngành × ĐĐ), ước tính ~{est_min} phút")

    print("\n[3/3] Bắt đầu crawl (checkpoint mỗi 200 hàng)...\n")
    vl24h_crawl_all(session, nganh_nghe, dia_diem, kinh_nghiem, limit=limit)

    elapsed = (datetime.now() - start).seconds // 60
    print(f"\n  Hoàn thành trong {elapsed} phút.")
    print("=" * 60)


if __name__ == "__main__":
    main()

    try:
        run_vietnamworks()
    except SystemExit:
        print("\n[VNW] Bỏ qua — chưa thiết lập cookie.")
        print("      Chạy: py vietnamworks/setup_cookies_vnw.py")

    try:
        run_vieclam24h(sample=False)
    except SystemExit:
        print("\n[VL24H] Bỏ qua — chưa thiết lập cookie.")
        print("        Chạy: py vieclam24h/setup_cookies_vl24h.py")
