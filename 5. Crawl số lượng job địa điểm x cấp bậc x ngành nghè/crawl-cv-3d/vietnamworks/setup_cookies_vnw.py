"""
Chạy 1 lần để login VietnamWorks Employer và lưu cookie + auth headers.
    py vietnamworks/setup_cookies_vnw.py
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE  = os.path.join(_DIR, "cookies.json")
HEADERS_FILE = os.path.join(_DIR, "captured_headers.json")

LOGIN_URL       = "https://employer.vietnamworks.com/v2/login"
RESUME_URL      = "https://employer.vietnamworks.com/v2/ho-so-ung-vien"
EMPLOYER_DOMAIN = "https://employer.vietnamworks.com"
MS_DOMAIN       = "https://ms.vietnamworks.com"


def main():
    print()
    print("=" * 55)
    print("  VietnamWorks — Lấy cookie đăng nhập (1 lần)")
    print("=" * 55)
    print()
    print("  Trình duyệt sẽ mở ra.")
    print("  Đăng nhập bằng tài khoản Employer của bạn.")
    print("  Script tự động lưu cookie sau khi login xong.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        # Intercept GraphQL request để lấy headers thực tế trình duyệt gửi
        captured_headers = {}

        def on_request(request):
            if "resume-search-api/graphql" in request.url and not captured_headers:
                captured_headers.update(dict(request.headers))

        page.on("request", on_request)

        page.goto(LOGIN_URL)
        print("  Đang chờ bạn đăng nhập...")

        page.wait_for_url(
            lambda url: "employer.vietnamworks.com" in url and "login" not in url,
            timeout=180_000
        )

        print("  Phát hiện đã login! Đang tải trang resume search...")

        # Navigate đến trang tìm CV — app tự gọi GraphQL → ta intercept headers
        page.goto(RESUME_URL)
        page.wait_for_load_state("networkidle", timeout=30_000)

        print("  Đang lưu cookie và headers...")

        # Cookie từ cả 2 domain
        employer_cookies = context.cookies(EMPLOYER_DOMAIN)
        ms_cookies       = context.cookies(MS_DOMAIN)

        cookie_dict = {}
        for c in employer_cookies + ms_cookies:
            cookie_dict[c["name"]] = c["value"]

        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookie_dict, f, indent=2)

        print(f"  Đã lưu {len(cookie_dict)} cookies vào {COOKIE_FILE}")
        print(f"  (employer: {len(employer_cookies)}, ms: {len(ms_cookies)})")

        # Lưu headers để debug
        if captured_headers:
            with open(HEADERS_FILE, "w", encoding="utf-8") as f:
                json.dump(captured_headers, f, indent=2)

            auth_keys = [k for k in captured_headers
                         if "auth" in k.lower() or "token" in k.lower() or k.lower() == "authorization"]
            if auth_keys:
                print(f"  Auth headers: {auth_keys}")
            else:
                print(f"  Intercepted {len(captured_headers)} headers — không thấy Authorization riêng")
                print(f"  Xem chi tiết: {HEADERS_FILE}")
        else:
            print("  CẢNH BÁO: Không intercept được GraphQL request!")

        browser.close()

    print()
    print("  Xong! Bây giờ có thể chạy: py main.py")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
