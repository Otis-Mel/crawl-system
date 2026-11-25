import os

EMAIL    = os.environ.get("CV_EMAIL", "")
PASSWORD = os.environ.get("CV_PASSWORD", "")

DELAY_SECONDS = 0.4     # delay giữa mỗi request
REQUEST_TIMEOUT = 15    # timeout mỗi request (giây)
MAX_RETRIES = 3         # retry nếu request fail

# Đường dẫn tuyệt đối — luôn lưu cùng thư mục với script
_DIR = os.path.dirname(os.path.abspath(__file__))

COOKIE_FILE = os.path.join(_DIR, "careerviet", "cookies.json")
EXCEL_FILE  = os.environ.get("CV_EXCEL_FILE") or os.path.join(_DIR, "CV_Count_Tracker.xlsx")

BASE_URL = "https://careerviet.vn/vi/tim-ung-vien"
