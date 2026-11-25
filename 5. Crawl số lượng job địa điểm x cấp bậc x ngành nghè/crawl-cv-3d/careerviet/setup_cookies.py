"""
Chạy script này 1 lần để login CareerViet và lưu cookie.
Sau đó main.py sẽ tự dùng cookie đó mỗi ngày.

Cách dùng:
    py careerviet/setup_cookies.py
"""

import sys
import os
import json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json")

LOGIN_URL = "https://careerviet.vn/vi/employers"
VERIFY_URL = "https://careerviet.vn/vi/tim-ung-vien.html"


def main():
    print()
    print("=" * 55)
    print("  CareerViet — Lấy cookie đăng nhập (1 lần)")
    print("=" * 55)
    print()
    print("  Trình duyệt sẽ mở ra.")
    print("  Bạn đăng nhập bằng Google như bình thường.")
    print("  Script tự động lưu cookie sau khi login xong.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        page.goto(LOGIN_URL)
        print("  Đang chờ bạn đăng nhập...")

        # Chờ đến khi trang chuyển sang trang employer dashboard
        # (dấu hiệu login thành công)
        page.wait_for_url(
            lambda url: "employers" in url and "login" not in url,
            timeout=180_000   # chờ tối đa 3 phút
        )

        print("  Phát hiện đã login! Đang lưu cookie...")

        # Lấy tất cả cookie của domain careerviet.vn
        cookies = context.cookies("https://careerviet.vn")

        # Chuyển sang dict {name: value} để dùng với requests
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(cookie_dict, f, indent=2)

        print(f"  Đã lưu {len(cookie_dict)} cookies vào {COOKIE_FILE}")
        browser.close()

    print()
    print("  Xong! Bây giờ có thể chạy: py main.py")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
