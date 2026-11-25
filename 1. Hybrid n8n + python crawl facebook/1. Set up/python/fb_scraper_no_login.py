"""
FB GROUP SCRAPER (NO LOGIN) - Chạy liên tục mỗi 30 phút
================================================================================
Chạy: python fb_scraper_no_login.py
Dừng: Ctrl+C

- Mỗi 30 phút chạy 1 lần, tạo file mới theo giờ
- Chỉ lấy bài tuyển dụng có email
- Dedup email xuyên suốt (email đã lấy sẽ không lấy lại)
- Upload từng file lên Google Drive
"""

import asyncio
import json
import re
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ========================================
# CẤU HÌNH
# ========================================

WORK_DIR = Path(__file__).parent
GROUPS_FILE = WORK_DIR / "groups.json"
LOG_DIR = WORK_DIR / "logs"
CREDENTIALS_FILE = WORK_DIR / "credentials.json"
TOKEN_FILE = WORK_DIR / "token.json"

GDRIVE_FOLDER_NAME = "fb_scraper_data"

# Cấu hình cào
MAX_POSTS_PER_GROUP = 50
MAX_SCROLL_ATTEMPTS = 5
POST_PAGE_DELAY = 2
SMART_WAIT_MAX = 8
SMART_WAIT_CHECK = 1

# Thời gian chờ giữa các lần chạy (giây)
INTERVAL_MINUTES = 30
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

# Từ khóa lọc sơ bộ
RECRUITMENT_KEYWORDS = [
    'tuyển dụng', 'tuyen dung',
    'cần tuyển', 'can tuyen',
    'đang tuyển', 'dang tuyen',
    'tuyển gấp', 'tuyen gap',
    'tuyển nhân viên',
    'tuyển kế toán', 'tuyển kỹ sư',
    'tuyển lập trình', 'tuyển sale',
    'tuyển sales', 'tuyển thực tập',
    'tuyển cộng tác viên', 'tuyển ctv',
    'cần người', 'cần gấp',
    'job', 'hiring', 'we are hiring',
    'recruiter', 'recruitment',
    'ứng tuyển', 'nộp hồ sơ',
    'liên hệ hr',
    'tuyển',
]

# Regex
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(r'(?:0|\+84|84)[\s.\-]?(\d{2,3})[\s.\-]?(\d{3})[\s.\-]?(\d{3,4})')

# ========================================
# SETUP LOGGING
# ========================================

LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"

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
# GROUPS.JSON
# ========================================

DEFAULT_GROUPS = [
    {"url": "https://www.facebook.com/groups/URL_GROUP_1", "name": "Thay bằng tên group 1"},
    {"url": "https://www.facebook.com/groups/URL_GROUP_2", "name": "Thay bằng tên group 2"},
    {"url": "https://www.facebook.com/groups/URL_GROUP_3", "name": "Thay bằng tên group 3"},
    {"url": "https://www.facebook.com/groups/URL_GROUP_4", "name": "Thay bằng tên group 4"},
    {"url": "https://www.facebook.com/groups/URL_GROUP_5", "name": "Thay bằng tên group 5"}
]


def create_default_groups_file():
    if not GROUPS_FILE.exists():
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_GROUPS, f, ensure_ascii=False, indent=2)
        logger.info(f"Đã tạo file {GROUPS_FILE}")
        logger.info(">>> MỞ FILE groups.json VÀ THAY URL BẰNG LINK GROUP THẬT <<<")
        return False
    return True


def load_groups():
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        groups = json.load(f)
    for g in groups:
        if "URL_GROUP" in g["url"]:
            logger.error("Bạn chưa cấu hình groups.json!")
            sys.exit(1)
    return groups


# ========================================
# TIỆN ÍCH
# ========================================

def normalize_post_url(url):
    if not url:
        return url
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        return f"https://www.facebook.com{path}"
    except:
        return url


def is_recruitment_post(text):
    if not text:
        return False
    text_lower = text.lower()
    for keyword in RECRUITMENT_KEYWORDS:
        if keyword in text_lower:
            return True
    return False


def extract_emails(text):
    if not text:
        return []
    return list(set(EMAIL_REGEX.findall(text)))


def extract_phones(text):
    if not text:
        return []
    phones = []
    for m in PHONE_REGEX.finditer(text):
        phone = re.sub(r'[\s.\-]', '', m.group(0))
        phones.append(phone)
    return list(set(phones))


def get_output_filepath():
    """Tạo tên file theo ngày và giờ hiện tại"""
    now = datetime.now()
    filename = f"fb_posts_{now.strftime('%Y%m%d_%H%M')}.json"
    return WORK_DIR / filename, filename


# ========================================
# PLAYWRIGHT HELPERS
# ========================================

async def smart_wait_for_new_posts(page, current_count):
    waited = 0
    while waited < SMART_WAIT_MAX:
        await asyncio.sleep(SMART_WAIT_CHECK)
        waited += SMART_WAIT_CHECK
        try:
            new_elements = await page.query_selector_all('[role="article"]')
            if len(new_elements) > current_count:
                logger.info(f"  ⚡ Load xong sau {waited}s")
                return True
        except:
            pass
    return False


async def click_all_see_more(page):
    try:
        selectors = [
            'div[role="button"]:has-text("Xem thêm")',
            'div[role="button"]:has-text("See more")',
            'span:has-text("Xem thêm")',
            'span:has-text("See more")',
        ]
        clicked = 0
        for selector in selectors:
            try:
                buttons = await page.query_selector_all(selector)
                for btn in buttons:
                    try:
                        if await btn.is_visible():
                            await btn.scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)
                            await btn.click()
                            await asyncio.sleep(0.5)
                            clicked += 1
                    except:
                        pass
            except:
                pass
        if clicked > 0:
            logger.info(f"  Đã click {clicked} nút Xem thêm")
    except:
        pass


async def close_login_popup(page):
    try:
        for selector in ['[aria-label="Close"]', '[aria-label="Đóng"]']:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(1)
                    break
            except:
                pass
    except:
        pass


async def get_full_post_text(page, post_url):
    if not post_url:
        return None
    try:
        await page.goto(post_url, wait_until="networkidle", timeout=20000)
        await asyncio.sleep(POST_PAGE_DELAY)
        await close_login_popup(page)
        await click_all_see_more(page)

        full_text = None
        for selector in ['[role="article"]', 'div[dir="auto"]']:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    if text and len(text.strip()) > 50:
                        if full_text is None or len(text) > len(full_text):
                            full_text = text.strip()
            except:
                pass
        return full_text
    except Exception as e:
        logger.debug(f"  Lỗi lấy full text: {e}")
        return None


# ========================================
# CÀO FACEBOOK
# ========================================

async def run_once(seen_emails_global):
    """Chạy 1 lần cào tất cả group"""
    from playwright.async_api import async_playwright

    groups = load_groups()
    output_file, filename = get_output_filepath()

    logger.info(f"File output: {filename}")
    logger.info(f"Email đã lấy từ trước: {len(seen_emails_global)}")

    all_posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="vi-VN"
        )

        group_page = await context.new_page()
        post_page = await context.new_page()

        for group in groups:
            try:
                group_posts = await scrape_single_group(
                    group_page, post_page, group, seen_emails_global
                )
                all_posts.extend(group_posts)
                logger.info(f"  → {group['name']}: {len(group_posts)} bài có email mới")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Lỗi group {group['name']}: {str(e)}")
                continue

        await browser.close()

    # Lưu file theo giờ
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_posts, f, ensure_ascii=False, indent=2)

    logger.info(f"Đã lưu {len(all_posts)} bài → {filename}")

    # Upload lên Google Drive
    if all_posts:
        logger.info("Đang upload Google Drive...")
        upload_to_gdrive(output_file, filename)
    else:
        logger.info("Không có bài mới → không upload")

    return all_posts


async def scrape_single_group(group_page, post_page, group, seen_emails_global):
    logger.info(f"\nĐang cào: {group['name']}")

    candidate_posts = []
    seen_urls = set()
    total_seen = 0

    await group_page.goto(group['url'], wait_until="networkidle", timeout=60000)
    await asyncio.sleep(5)

    page_content = await group_page.content()
    if "This content isn't available" in page_content or "must log in" in page_content.lower():
        logger.warning(f"  Group không truy cập được. Bỏ qua.")
        return []

    await close_login_popup(group_page)

    # ── BƯỚC 1: Scroll + lọc sơ bộ ──
    logger.info(f"  Bước 1: Scroll và lọc sơ bộ...")

    for scroll_num in range(MAX_SCROLL_ATTEMPTS):
        if len(candidate_posts) >= MAX_POSTS_PER_GROUP:
            break

        current_elements = await group_page.query_selector_all('[role="article"]')
        count_before = len(current_elements)

        for element in current_elements:
            try:
                post_url = ""
                try:
                    links = await element.query_selector_all(
                        'a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"]'
                    )
                    if links:
                        raw_url = await links[0].get_attribute('href')
                        if raw_url and not raw_url.startswith('http'):
                            raw_url = f"https://www.facebook.com{raw_url}"
                        post_url = normalize_post_url(raw_url)
                except:
                    pass

                if not post_url or post_url in seen_urls:
                    continue
                seen_urls.add(post_url)
                total_seen += 1

                preview_text = await element.inner_text()
                if not preview_text or len(preview_text.strip()) < 20:
                    continue

                if not is_recruitment_post(preview_text):
                    continue

                post_time = ""
                try:
                    time_elements = await element.query_selector_all('a[role="link"] span')
                    for te in time_elements:
                        t = await te.inner_text()
                        if any(x in t.lower() for x in ['giờ', 'phút', 'hour', 'min', 'ngày', 'day', 'hôm', 'vừa']):
                            post_time = t
                            break
                except:
                    pass

                candidate_posts.append({
                    "postUrl": post_url,
                    "postTime": post_time,
                    "preview_text": preview_text.strip(),
                    "groupName": group['name'],
                    "groupUrl": group['url'],
                })

                if len(candidate_posts) >= MAX_POSTS_PER_GROUP:
                    break

            except:
                continue

        await group_page.evaluate("window.scrollBy(0, 1500)")
        await smart_wait_for_new_posts(group_page, count_before)
        logger.info(f"  Scroll {scroll_num + 1}/{MAX_SCROLL_ATTEMPTS} - Thấy {total_seen} bài, tiềm năng: {len(candidate_posts)}")

    logger.info(f"  Lọc sơ bộ: {len(candidate_posts)}/{total_seen} bài có từ khóa tuyển dụng")

    # ── BƯỚC 2: Lấy full text + lọc email + dedup ──
    logger.info(f"  Bước 2: Lấy full text và lọc email...")

    posts = []
    skipped_no_email = 0
    skipped_dup = 0

    for i, post_data in enumerate(candidate_posts):
        post_url = post_data['postUrl']
        logger.info(f"  [{i+1}/{len(candidate_posts)}] Đang xử lý...")

        full_text = await get_full_post_text(post_page, post_url)
        final_text = full_text if full_text and len(full_text) > len(post_data['preview_text']) else post_data['preview_text']

        if len(final_text) < 30:
            continue

        emails = extract_emails(final_text)
        if not emails:
            skipped_no_email += 1
            logger.info(f"  ⏭ Bỏ qua (không có email)")
            continue

        # Dedup xuyên suốt
        new_emails = [e for e in emails if e not in seen_emails_global]
        if not new_emails:
            skipped_dup += 1
            logger.info(f"  ⏭ Bỏ qua (email đã lấy trước đó: {', '.join(emails)})")
            continue

        for e in new_emails:
            seen_emails_global.add(e)

        phones = extract_phones(final_text)

        posts.append({
            "postId": str(abs(hash(post_url))),
            "postUrl": post_url,
            "groupName": post_data['groupName'],
            "groupUrl": post_data['groupUrl'],
            "text": final_text,
            "emails": emails,
            "phones": phones,
            "postTime": post_data['postTime'],
            "scrapedAt": datetime.now().isoformat()
        })

        logger.info(f"  ✅ Email mới: {', '.join(new_emails)}")
        await asyncio.sleep(0.5)

    logger.info(f"  Bỏ qua: {skipped_no_email} không có email, {skipped_dup} email trùng")
    return posts


# ========================================
# UPLOAD GOOGLE DRIVE
# ========================================

def upload_to_gdrive(filepath, filename):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.warning("Chưa cài thư viện Google Drive.")
        return None

    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                logger.warning(f"Không tìm thấy {CREDENTIALS_FILE}")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)

        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    folder_id = find_or_create_folder(service, GDRIVE_FOLDER_NAME)

    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaFileUpload(str(filepath), mimetype='application/json')

    file = service.files().create(
        body=file_metadata, media_body=media, fields='id, name, webViewLink'
    ).execute()

    logger.info(f"Đã upload: {file.get('name')}")
    logger.info(f"Link: {file.get('webViewLink')}")
    return file.get('id')


def find_or_create_folder(service, folder_name):
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)"
    ).execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']

    folder = service.files().create(
        body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
        fields='id'
    ).execute()
    logger.info(f"Đã tạo folder '{folder_name}'")
    return folder.get('id')


# ========================================
# MAIN - CHẠY LIÊN TỤC MỖI 30 PHÚT
# ========================================

async def main():
    logger.info("=" * 60)
    logger.info("FB GROUP SCRAPER - Chạy liên tục mỗi 30 phút")
    logger.info("Nhấn Ctrl+C để dừng")
    logger.info("=" * 60)

    if not create_default_groups_file():
        return

    # Dedup email xuyên suốt tất cả các lần chạy
    seen_emails_global = set()
    run_count = 0

    while True:
        run_count += 1
        now = datetime.now().strftime('%H:%M')
        logger.info(f"\n{'='*60}")
        logger.info(f"LẦN CHẠY #{run_count} | {now}")
        logger.info(f"{'='*60}")

        start_time = time.time()
        try:
            posts = await run_once(seen_emails_global)
            elapsed = time.time() - start_time
            logger.info(f"Xong lần #{run_count}: {len(posts)} bài mới | {elapsed:.0f}s ({elapsed/60:.1f} phút)")
        except Exception as e:
            logger.error(f"Lỗi lần #{run_count}: {e}")

        # Chờ 30 phút trước lần chạy tiếp theo
        next_run = datetime.fromtimestamp(time.time() + INTERVAL_SECONDS).strftime('%H:%M')
        logger.info(f"\nChờ {INTERVAL_MINUTES} phút... Lần tiếp theo lúc {next_run}")
        logger.info(f"(Ctrl+C để dừng)")

        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n=== ĐÃ DỪNG SCRIPT ===")