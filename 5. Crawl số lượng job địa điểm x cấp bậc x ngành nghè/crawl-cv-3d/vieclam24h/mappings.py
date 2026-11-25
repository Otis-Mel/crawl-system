"""
Reference data cho Vieclam24h resume search.

URL search:
  https://ntd.vieclam24h.vn/tim-kiem-ung-vien-nhanh
    ?occupation_ids[]=<industry_id>     # Ngành nghề (53)
    &province_ids[]=<province_id>       # Tỉnh/thành (63)
    &experience[]=<value>               # Kinh nghiệm (1..8)

Verified counts:
  Marketing only:                170,617
  Kế toán only:                  356,050
  Kế toán × Hà Nội:              112,536
  Kế toán × Hà Nội × 1 năm KN:    13,147

Tất cả 3 taxonomy được extract sẵn bằng cách inspect React fiber state
trên ntd.vieclam24h.vn/tim-kiem-ung-vien-nhanh (xem README để chi tiết).
"""
import sys, os, json

sys.stdout.reconfigure(encoding="utf-8")

_DIR = os.path.dirname(os.path.abspath(__file__))
NGANH_NGHE_FILE  = os.path.join(_DIR, "nganh_nghe.json")
DIA_DIEM_FILE    = os.path.join(_DIR, "dia_diem.json")
KINH_NGHIEM_FILE = os.path.join(_DIR, "kinh_nghiem.json")


def fetch_nganh_nghe() -> list[dict]:
    """
    53 ngành nghề. Mỗi item: {"id": int, "name": str}
    URL param: occupation_ids[]=<id>
    """
    with open(NGANH_NGHE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    result = [{"id": x["id"], "name": x["name"]} for x in data["industries"]]
    print(f"[vl24h/mappings] Ngành nghề: {len(result)}")
    return result


def fetch_dia_diem() -> list[dict]:
    """
    63 tỉnh/thành. Mỗi item: {"id": int, "name": str}
    URL param: province_ids[]=<id>
    """
    with open(DIA_DIEM_FILE, encoding="utf-8") as f:
        data = json.load(f)
    result = [{"id": x["id"], "name": x["name"]} for x in data["provinces"]]
    print(f"[vl24h/mappings] Địa điểm: {len(result)}")
    return result


def get_kinh_nghiem() -> list[dict]:
    """
    8 mức Kinh nghiệm (dùng làm chiều thứ 2 thay cho 'Cấp bậc').
    Mỗi item: {"value": str, "name": str}
    URL param: experience[]=<value>
    """
    with open(KINH_NGHIEM_FILE, encoding="utf-8") as f:
        data = json.load(f)
    result = data["experience_levels"]
    print(f"[vl24h/mappings] Kinh nghiệm: {len(result)} mức")
    return result
