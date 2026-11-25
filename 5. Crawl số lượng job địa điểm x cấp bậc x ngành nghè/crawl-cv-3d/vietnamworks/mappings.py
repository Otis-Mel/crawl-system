"""
Reference data cho VietnamWorks resume search.

Filter syntax đã verify (Lucene, qua intercept browser):
  Lĩnh vực (UI 'Lĩnh vực'):   expectedIndustryV3Ids:(X)        — 49 IDs từ dropdown
  Ngành nghề (UI 'Ngành nghề'): expectedjobFunctionV3Id:(X)     — 159 IDs từ /api/choices/job-functions
  Địa điểm:                     expectedWorkingLocation.cityId:(X)
  Cấp bậc:                      jobLevelId:X
  Kết hợp:                      <filter1> AND <filter2>
"""
import sys, os, json
import requests

sys.stdout.reconfigure(encoding="utf-8")

_DIR          = os.path.dirname(os.path.abspath(__file__))
LINH_VUC_FILE = os.path.join(_DIR, "linh_vuc.json")

EMPLOYER_BASE = "https://employer.vietnamworks.com"
JOB_FUNC_URL  = EMPLOYER_BASE + "/api/choices/job-functions"
CITIES_URL    = EMPLOYER_BASE + "/api/lead-cities/1"   # /1 = tiếng Việt, /2 = tiếng Anh

# Cấp bậc — từ filter dropdown VietnamWorks
CAP_BAC = [
    {"id": 1, "name": "Mới tốt nghiệp"},
    {"id": 5, "name": "Nhân viên"},
    {"id": 7, "name": "Trưởng phòng"},
    {"id": 3, "name": "Giám đốc và cấp cao hơn"},
]


def get_cap_bac() -> list[dict]:
    return CAP_BAC


def fetch_linh_vuc(session: requests.Session) -> list[dict]:
    """
    49 lĩnh vực (industry V3), tên tiếng Việt.
    Đã extract qua Playwright (xem _map_lv_v3.py + _map_lv_missing.py).
    Mỗi item: {"id": int, "name": str}
    Filter: expectedIndustryV3Ids:(id)
    """
    with open(LINH_VUC_FILE, encoding="utf-8") as f:
        data = json.load(f)
    result = sorted(
        [{"id": v, "name": k} for k, v in data.items()],
        key=lambda x: x["id"],
    )
    print(f"[vnw/mappings] Lĩnh vực: {len(result)} industries (V3)")
    return result


def fetch_nganh_nghe(session: requests.Session) -> list[dict]:
    """
    159 ngành nghề (jobFunction V3), tên tiếng Việt từ /api/choices/job-functions?lang=1.
    Mỗi item: {"id": int, "name": str, "group": str}
    Filter: expectedjobFunctionV3Id:(id)
    """
    resp = session.get(JOB_FUNC_URL, params={"lang": 1}, timeout=10)
    data = resp.json().get("data", {})
    result = []
    for group_name, subs in data.items():
        if isinstance(subs, dict):
            for sub_name, sub_id in subs.items():
                result.append({"id": sub_id, "name": sub_name, "group": group_name})
        else:
            result.append({"id": subs, "name": group_name, "group": group_name})
    result.sort(key=lambda x: x["id"])
    print(f"[vnw/mappings] Ngành nghề: {len(result)} job-functions (V3)")
    return result


def fetch_dia_diem(session: requests.Session) -> list[dict]:
    """
    66 tỉnh/thành phố Việt Nam, tên tiếng Việt (có dấu).
    Mỗi item: {"id": int, "name": str}
    Filter: expectedWorkingLocation.cityId:(id)
    """
    resp = session.get(CITIES_URL, timeout=10)
    data = resp.json().get("data", {})
    result = sorted(
        [{"id": int(k), "name": v} for k, v in data.items()],
        key=lambda x: x["id"],
    )
    print(f"[vnw/mappings] Địa điểm: {len(result)} cities")
    return result
