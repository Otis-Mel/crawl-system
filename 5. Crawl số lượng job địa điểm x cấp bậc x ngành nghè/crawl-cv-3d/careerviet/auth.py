import requests
import json
import os
import sys
from config import COOKIE_FILE, REQUEST_TIMEOUT

VERIFY_URL = "https://careerviet.vn/vi/tim-ung-vien.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://careerviet.vn",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def get_session() -> requests.Session:
    """
    Load cookie từ file, verify còn sống không.
    Nếu hết hạn hoặc chưa có cookie → hướng dẫn user và thoát.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    if not os.path.exists(COOKIE_FILE):
        _notify_missing_cookie()
        sys.exit(1)

    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    session.cookies.update(cookies)

    if not _verify(session):
        _notify_expired_cookie()
        sys.exit(1)

    print("[auth] Cookie hợp lệ, bắt đầu crawl...")
    return session


def _verify(session: requests.Session) -> bool:
    """Trả về True nếu session còn sống (không bị redirect về trang login)."""
    try:
        resp = session.get(VERIFY_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        # Nếu bị redirect về trang login → cookie hết hạn
        if "login" in resp.url or "dang-nhap" in resp.url:
            return False
        # Kiểm tra nội dung trang có chứa dấu hiệu đã login
        if "tim-ung-vien" in resp.url or resp.status_code == 200:
            return True
        return False
    except Exception as e:
        print(f"[auth] Lỗi khi verify session: {e}")
        return False


def _notify_missing_cookie():
    print()
    print("=" * 60)
    print("  LỖI: Không tìm thấy file cookies.json")
    print("=" * 60)
    print()
    print("Làm theo các bước sau để lấy cookie:")
    print()
    print("  Chạy: py careerviet/setup_cookies.py")
    print()
    print("=" * 60)


def _notify_expired_cookie():
    print()
    print("=" * 60)
    print("  CẢNH BÁO: Cookie đã hết hạn hoặc không hợp lệ")
    print("=" * 60)
    print()
    print("Cookie CareerViet của bạn đã expire.")
    print("Làm theo các bước sau để cập nhật:")
    print()
    print("  Chạy: py careerviet/setup_cookies.py")
    print()
    print("=" * 60)
