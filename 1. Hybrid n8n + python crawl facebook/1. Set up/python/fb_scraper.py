"""
FB GROUP SCRAPER - Script cào bài đăng tuyển dụng từ Facebook Group
===================================================================
Chạy: python fb_scraper.py          (cào bài post)
       python fb_scraper.py --login  (đăng nhập Facebook lần đầu)

Output: Upload file JSON lên Google Drive để n8n Cloud đọc.
"""

import asyncio
import json
import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ========================================
# CẤU HÌNH
# ========================================

# Thư mục làm việc
WORK_DIR = Path(__file__).parent
COOKIE_FILE = WORK_DIR / "fb_cookies.json"
GROUPS_FILE = WORK_DIR / "groups.json"
OUTPUT_FILE = WORK_DIR / "fb_posts.json"
LOG_DIR = WORK_DIR / "logs"
CREDENTIALS_FILE = WORK_DIR / "credentials.json"
TOKEN_FILE = WORK_DIR / "token.json"

# Google Drive
GDRIVE_FOLDER_NAME = "fb_scraper_data"  # Tên folder trên Google Drive

# Cấu hình cào
MAX_POSTS_PER_GROUP = 50       # Số bài tối đa mỗi group
SCROLL_DELAY = 5               # Giây chờ giữa mỗi lần scroll (an toàn)
MAX_SCROLL_ATTEMPTS = 15       # Số lần scroll tối đa mỗi group
HOURS_LOOKBACK = 24            # Chỉ lấy bài trong X giờ gần nhất

# ========================================
# SETUP LOGGING
# ========================================

LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================================
# TẠO FILE groups.json MẪU (NẾU CHƯA CÓ)
# ========================================

DEFAULT_GROUPS = [
    {
        "url": "https://www.facebook.com/groups/URL_GROUP_1",
        "name": "Tên group 1 - Thay bằng group thật"
    },
    {
        "url": "https://www.facebook.com/groups/URL_GROUP_2",
        "name": "Tên group 2 - Thay bằng group thật"
    },
    {
        "url": "https://www.facebook.com/groups/URL_GROUP_3",
        "name": "Tên group 3 - Thay bằng group thật"
    },
    {
        "url": "https://www.facebook.com/groups/URL_GROUP_4",
        "name": "Tên group 4 - Thay bằng group thật"
    },
    {
        "url": "https://www.facebook.com/groups/URL_GROUP_5",
        "name": "Tên group 5 - Thay bằng group thật"
    }
]


def create_default_groups_file():
    """Tạo file groups.json mẫu nếu chưa tồn tại"""
    if not GROUPS_FILE.exists():
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_GROUPS, f, ensure_ascii=False, indent=2)
        logger.info(f"Đã tạo file {GROUPS_FILE}")
        logger.info(">>> MỞ FILE groups.json VÀ THAY URL_GROUP BẰNG LINK GROUP THẬT <<<")
        return False
    return True


def load_groups():
    """Đọc danh sách group từ file"""
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        groups = json.load(f)
    
    # Kiểm tra xem đã cấu hình chưa
    for g in groups:
        if "URL_GROUP" in g["url"]:
            logger.error("Bạn chưa cấu hình groups.json!")
            logger.error("Mở file C:\\fb_scraper\\groups.json và thay URL group thật vào.")
            sys.exit(1)
    
    return groups


# ========================================
# ĐĂNG NHẬP FACEBOOK
# ========================================

async def login_facebook():
    """Mở Chrome để đăng nhập Facebook, lưu cookie"""
    from playwright.async_api import async_playwright

    logger.info("=== ĐĂNG NHẬP FACEBOOK ===")
    logger.info("Chrome sẽ mở ra → Đăng nhập Facebook bằng tay")
    logger.info("Sau khi vào được trang chủ Facebook → Quay lại đây nhấn Enter")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Mở Chrome có giao diện
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Mở Facebook
        await page.goto("https://www.facebook.com/")
        
        # Chờ người dùng đăng nhập
        input("\n>>> Đã đăng nhập Facebook xong? Nhấn ENTER để lưu cookie... ")
        
        # Lưu cookie
        cookies = await context.cookies()
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Đã lưu {len(cookies)} cookies vào {COOKIE_FILE}")
        logger.info("Bạn có thể đóng Chrome rồi.")
        
        await browser.close()


# ========================================
# CÀO BÀI POST TỪ FACEBOOK GROUP
# ========================================

async def scrape_groups():
    """Cào bài post từ tất cả group trong danh sách"""
    from playwright.async_api import async_playwright

    # Kiểm tra cookie
    if not COOKIE_FILE.exists():
        logger.error("Chưa có cookie! Chạy: python fb_scraper.py --login")
        sys.exit(1)

    # Đọc cookie
    with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    # Đọc danh sách group
    groups = load_groups()
    logger.info(f"Sẽ cào {len(groups)} groups")

    all_posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True  # Chạy ẩn, không mở Chrome
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Load cookie
        await context.add_cookies(cookies)
        page = await context.new_page()

        # Kiểm tra đăng nhập
        await page.goto("https://www.facebook.com/", wait_until="networkidle")
        await asyncio.sleep(3)

        # Kiểm tra xem có bị redirect về trang login không
        if "login" in page.url.lower():
            logger.error("Cookie hết hạn! Chạy lại: python fb_scraper.py --login")
            await browser.close()
            sys.exit(1)

        logger.info("Đăng nhập Facebook thành công")

        # Cào từng group
        for group in groups:
            try:
                group_posts = await scrape_single_group(page, group)
                all_posts.extend(group_posts)
                logger.info(f"  → Lấy được {len(group_posts)} bài từ {group['name']}")
                
                # Delay giữa các group
                await asyncio.sleep(SCROLL_DELAY)
            except Exception as e:
                logger.error(f"Lỗi khi cào group {group['name']}: {str(e)}")
                continue

        await browser.close()

    # Lưu kết quả
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)

    logger.info(f"\n=== KẾT QUẢ ===")
    logger.info(f"Tổng: {len(all_posts)} bài post từ {len(groups)} groups")
    logger.info(f"File: {OUTPUT_FILE}")

    return all_posts


async def scrape_single_group(page, group):
    """Cào bài post từ 1 group"""
    logger.info(f"\nĐang cào: {group['name']}")
    logger.info(f"URL: {group['url']}")

    posts = []
    seen_post_ids = set()

    # Vào group
    await page.goto(group['url'], wait_until="networkidle")
    await asyncio.sleep(5)

    # Scroll và thu thập bài post
    for scroll_num in range(MAX_SCROLL_ATTEMPTS):
        if len(posts) >= MAX_POSTS_PER_GROUP:
            logger.info(f"  Đã đủ {MAX_POSTS_PER_GROUP} bài")
            break

        # Lấy tất cả bài post hiện tại trên trang
        post_elements = await page.query_selector_all('[role="article"]')

        for element in post_elements:
            try:
                # Lấy text của bài post
                text_content = await element.inner_text()
                
                if not text_content or len(text_content.strip()) < 20:
                    continue

                # Tạo ID duy nhất cho bài post (tránh trùng)
                post_id = hash(text_content[:100])
                if post_id in seen_post_ids:
                    continue
                seen_post_ids.add(post_id)

                # Lấy URL bài post (nếu có)
                post_url = ""
                try:
                    link_elements = await element.query_selector_all('a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"]')
                    if link_elements:
                        post_url = await link_elements[0].get_attribute('href')
                        if post_url and not post_url.startswith('http'):
                            post_url = f"https://www.facebook.com{post_url}"
                except:
                    pass

                # Lấy thời gian bài post (nếu có)
                post_time = ""
                try:
                    time_elements = await element.query_selector_all('a[href*="/posts/"] span, abbr[data-utime], span[id*="jsc_"]')
                    if time_elements:
                        post_time = await time_elements[0].inner_text()
                except:
                    pass

                posts.append({
                    "postId": str(abs(post_id)),
                    "postUrl": post_url,
                    "groupName": group['name'],
                    "groupUrl": group['url'],
                    "text": text_content.strip(),
                    "postTime": post_time,
                    "scrapedAt": datetime.now().isoformat(),
                })

                if len(posts) >= MAX_POSTS_PER_GROUP:
                    break

            except Exception as e:
                continue

        # Scroll xuống
        await page.evaluate("window.scrollBy(0, 1500)")
        await asyncio.sleep(SCROLL_DELAY)
        logger.info(f"  Scroll {scroll_num + 1}/{MAX_SCROLL_ATTEMPTS} - Đã lấy {len(posts)} bài")

    return posts


# ========================================
# UPLOAD LÊN GOOGLE DRIVE
# ========================================

def upload_to_gdrive(filepath):
    """Upload file JSON lên Google Drive"""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.warning("Chưa cài thư viện Google Drive. Chạy:")
        logger.warning("pip install google-auth google-auth-oauthlib google-api-python-client")
        logger.info(f"File JSON vẫn được lưu tại: {filepath}")
        return None

    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    creds = None

    # Đọc token đã lưu
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Nếu chưa có token hoặc token hết hạn
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                logger.warning(f"Không tìm thấy {CREDENTIALS_FILE}")
                logger.warning("Xem hướng dẫn setup Google Drive API trong file setup_guide.md")
                logger.info(f"File JSON vẫn được lưu tại: {filepath}")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Lưu token
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    # Kết nối Google Drive
    service = build('drive', 'v3', credentials=creds)

    # Tìm hoặc tạo folder
    folder_id = find_or_create_folder(service, GDRIVE_FOLDER_NAME)

    # Upload file
    file_metadata = {
        'name': f"fb_posts_{datetime.now().strftime('%Y%m%d')}.json",
        'parents': [folder_id]
    }
    media = MediaFileUpload(str(filepath), mimetype='application/json')

    # Xóa file cũ cùng tên (nếu có)
    results = service.files().list(
        q=f"name='{file_metadata['name']}' and '{folder_id}' in parents and trashed=false",
        fields="files(id)"
    ).execute()
    for f in results.get('files', []):
        service.files().delete(fileId=f['id']).execute()

    # Upload file mới
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink'
    ).execute()

    logger.info(f"Đã upload lên Google Drive: {file.get('name')}")
    logger.info(f"Link: {file.get('webViewLink')}")

    return file.get('id')


def find_or_create_folder(service, folder_name):
    """Tìm folder trên Google Drive, tạo mới nếu chưa có"""
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)"
    ).execute()

    folders = results.get('files', [])
    if folders:
        return folders[0]['id']

    # Tạo folder mới
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(
        body=folder_metadata,
        fields='id'
    ).execute()

    logger.info(f"Đã tạo folder '{folder_name}' trên Google Drive")
    return folder.get('id')


# ========================================
# MAIN
# ========================================

async def main():
    logger.info("=" * 60)
    logger.info("FB GROUP SCRAPER - Bắt đầu")
    logger.info(f"Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Tạo file groups.json mẫu nếu chưa có
    if not create_default_groups_file():
        logger.info("\nĐã tạo file groups.json mẫu.")
        logger.info("Mở file C:\\fb_scraper\\groups.json")
        logger.info("Thay URL_GROUP_1, URL_GROUP_2... bằng link group Facebook thật.")
        logger.info("Sau đó chạy lại script.")
        return

    # Chế độ đăng nhập
    if "--login" in sys.argv:
        await login_facebook()
        return

    # Cào bài post
    start_time = time.time()
    posts = await scrape_groups()
    elapsed = time.time() - start_time

    logger.info(f"\nThời gian cào: {elapsed:.0f} giây ({elapsed/60:.1f} phút)")

    if posts:
        # Upload lên Google Drive
        logger.info("\nĐang upload lên Google Drive...")
        file_id = upload_to_gdrive(OUTPUT_FILE)

        if not file_id:
            logger.info("Không upload được Google Drive.")
            logger.info(f"File JSON vẫn có tại: {OUTPUT_FILE}")
            logger.info("Bạn có thể upload thủ công lên Google Drive.")
    else:
        logger.info("Không tìm thấy bài post nào.")

    logger.info("\n=== HOÀN TẤT ===")


if __name__ == "__main__":
    asyncio.run(main())
