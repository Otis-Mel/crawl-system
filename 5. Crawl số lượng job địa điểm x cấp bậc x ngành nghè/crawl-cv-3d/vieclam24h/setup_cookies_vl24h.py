"""
Chạy 1 lần để login Vieclam24h Employer và lưu cookie + Bearer token.
    py vieclam24h/setup_cookies_vl24h.py

Flow:
  1. Mở trang search (page yêu cầu auth)
  2. Nếu chưa login → chờ user đăng nhập
  3. Intercept network request tới apiv2 → lấy Authorization: Bearer <token>
  4. Lưu token + cookies vào cookies.json
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(_DIR, "cookies.json")

SEARCH_URL = "https://ntd.vieclam24h.vn/tim-kiem-ung-vien-nhanh"
NTD_DOMAIN = "https://ntd.vieclam24h.vn"
API_DOMAIN = "https://apiv2.vieclam24h.vn"
API_PATH   = "/seeker/fe/api/v1/search/ai-resume"

API_TEST_URL = (
    "https://apiv2.vieclam24h.vn/seeker/fe/api/v1/search/ai-resume"
    "?per_page=1&action=loadmore"
)


def _is_jwt(val: str) -> bool:
    """JWT bắt đầu bằng eyJ (base64 của '{')."""
    return isinstance(val, str) and val.startswith("eyJ") and len(val) > 50


def main():
    print()
    print("=" * 55)
    print("  Vieclam24h — Lấy cookie đăng nhập (1 lần)")
    print("=" * 55)
    print()

    bearer_token = None

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=200)
        context = browser.new_context()
        page = context.new_page()

        # Intercept TOÀN BỘ request trong context
        def on_request(request):
            nonlocal bearer_token
            if API_PATH in request.url and not bearer_token:
                auth = request.headers.get("authorization", "")
                if auth.startswith("Bearer "):
                    bearer_token = auth[len("Bearer "):]
                    print(f"  Bearer token từ network: ...{bearer_token[-20:]}")

        context.on("request", on_request)

        # Mở thẳng trang search — nếu chưa login sẽ redirect về login page
        print("  Mở trang tìm kiếm ứng viên...")
        print("  Nếu chưa login → đăng nhập vào tài khoản Employer.")
        print("  Script tự động tiếp tục sau khi bạn login xong.\n")
        page.goto(SEARCH_URL)

        # Chờ đến khi có token (hoặc user làm gì đó)
        # Kiểm tra mỗi 2 giây trong tối đa 3 phút
        for _ in range(90):
            if bearer_token:
                break
            page.wait_for_timeout(2000)

            # Mỗi 10 giây thử gọi API để kiểm tra login status
            if _ % 5 == 4:
                try:
                    result = page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch('{API_TEST_URL}', {{credentials:'include'}});
                            const j = await r.json();
                            return j;
                        }} catch(e) {{ return {{code: 0, msg: e.message}}; }}
                    }}""")
                    if result and result.get("code") == 1:
                        total = (result.get("data") or {}).get("total_items", "?")
                        print(f"  API hoạt động! Tổng ứng viên: {total:,} — lưu session...")
                        bearer_token = "__session_only__"
                        break
                except Exception:
                    pass
        else:
            if not bearer_token:
                print("  Timeout sau 3 phút. Thử lại.")
                browser.close()
                sys.exit(1)

        # Lấy cookies sau khi đã xác nhận login
        page.wait_for_timeout(2000)
        ntd_cookies = context.cookies(NTD_DOMAIN)
        api_cookies = context.cookies(API_DOMAIN)

        cookie_dict = {}
        for c in ntd_cookies + api_cookies:
            cookie_dict[c["name"]] = c["value"]

        # Lưu Bearer token (nếu bắt được từ network)
        if bearer_token and bearer_token != "__session_only__":
            cookie_dict["re_access_token"] = bearer_token
            print(f"  Đã lưu Bearer token.")
        elif bearer_token == "__session_only__":
            print("  Lưu session cookies (không có Bearer token riêng).")

        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookie_dict, f, indent=2)

        n = len(cookie_dict)
        has_token = "re_access_token" in cookie_dict
        print(f"  Đã lưu {n} entries vào cookies.json (token: {'có' if has_token else 'không'})")

        browser.close()

    print()
    print("  Xong! Bây giờ có thể chạy: py main.py")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
