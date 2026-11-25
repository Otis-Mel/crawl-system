import sys, json, os
import requests

sys.stdout.reconfigure(encoding="utf-8")

_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(_DIR, "cookies.json")

BASE_URL   = "https://ntd.vieclam24h.vn"
SEARCH_URL = BASE_URL + "/tim-kiem-ung-vien-nhanh"
API_URL    = "https://apiv2.vieclam24h.vn/seeker/fe/api/v1/search/ai-resume"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Referer": SEARCH_URL,
    "Origin": BASE_URL,
}


def get_session() -> requests.Session:
    session = requests.Session()

    if not os.path.exists(COOKIE_FILE):
        print()
        print("  LỖI: Không tìm thấy vieclam24h/cookies.json")
        print("  Chạy trước: py vieclam24h/setup_cookies_vl24h.py")
        sys.exit(1)

    with open(COOKIE_FILE, encoding="utf-8") as f:
        cookies = json.load(f)

    session.cookies.update(cookies)

    token = cookies.get("re_access_token", "")
    headers = dict(_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session.headers.update(headers)

    # Verify — gọi API trực tiếp (page là CSR, raw HTML không có count)
    try:
        resp = session.get(API_URL, params={"per_page": 1, "action": "loadmore"}, timeout=20)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        data = resp.json()
        if data.get("code") not in (1, 200):
            raise ValueError(f"API trả lỗi: {data.get('msg')} — cookie/token hết hạn")
        count = data["data"]["total_items"]
        auth_mode = "Bearer token" if token else "session cookies"
        print(f"[vl24h/auth] OK ({auth_mode}) — toàn quốc: {count:,} ứng viên")
    except Exception as e:
        print()
        print(f"  CẢNH BÁO: Vieclam24h auth lỗi: {e}")
        print("  Chạy lại: py vieclam24h/setup_cookies_vl24h.py")
        sys.exit(1)

    return session
