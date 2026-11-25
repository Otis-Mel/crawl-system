import sys, json, os, requests

sys.stdout.reconfigure(encoding="utf-8")

_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(_DIR, "cookies.json")

GQL_URL = "https://ms.vietnamworks.com/resume-search-api/graphql"

_BASE_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://employer.vietnamworks.com",
    "Referer": "https://employer.vietnamworks.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_VERIFY_Q = '{ searchES(algoliaFilter: {filters:"", page:0, hitsPerPage:1, restrictSearchableAttributes:""}, locale:"vn") { nbHits } }'


def get_session() -> requests.Session:
    session = requests.Session()

    if not os.path.exists(COOKIE_FILE):
        print()
        print("  LỖI: Không tìm thấy vietnamworks/cookies.json")
        print("  Chạy trước: py vietnamworks/setup_cookies_vnw.py")
        sys.exit(1)

    with open(COOKIE_FILE, encoding="utf-8") as f:
        cookies = json.load(f)

    session.cookies.update(cookies)

    # ONB_JWT cần gửi cả là cookie lẫn Authorization header
    jwt = cookies.get("ONB_JWT", "")
    headers = dict(_BASE_HEADERS)
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    session.headers.update(headers)

    # Verify
    try:
        resp = session.post(GQL_URL, json={"query": _VERIFY_Q}, timeout=15)
        data = resp.json()
        if data.get("errors"):
            raise ValueError(data["errors"][0].get("message", "unknown"))
    except Exception as e:
        print()
        print(f"  CẢNH BÁO: VietnamWorks auth lỗi: {e}")
        print("  Chạy lại: py vietnamworks/setup_cookies_vnw.py")
        sys.exit(1)

    print("[vnw/auth] Cookie hợp lệ.")
    return session
