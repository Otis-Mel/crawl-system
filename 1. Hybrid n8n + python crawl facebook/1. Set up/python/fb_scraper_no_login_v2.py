"""
FB GROUP SCRAPER (NO LOGIN) - Chạy liên tục mỗi 30 phút
================================================================================
Chạy: python fb_scraper_no_login_v2.py
      python fb_scraper_no_login_v2.py --once      (chạy 1 lượt rồi dừng, dùng cho Task Scheduler)
      python fb_scraper_no_login_v2.py --out-dir D:\thu_muc_test   (đổi thư mục xuất CSV)
Dừng: Ctrl+C

- Mỗi 30 phút chạy 1 lần, tạo file mới theo giờ
- Chỉ lấy bài tuyển dụng có email
- Dedup email (nạp từ CSV cũ) và dedup link khi xuất CSV
- Xuất CSV vào "..\2. Output\fb_leads" (thư mục OneDrive), không cần Google Drive/n8n
  (muốn vẫn đẩy JSON lên Drive: thêm --upload-drive)

Khác bản gốc (fb_scraper_no_login.py):
- Mỗi group mở trình duyệt/tab mới: crash hoặc trang rỗng ở group này không lan sang group khác
- Group thấy 0 bài hoặc lỗi thì thử lại tối đa MAX_GROUP_ATTEMPTS lần
- Mỗi bài tối đa POST_TIMEOUT giây, mỗi group tối đa GROUP_TIMEOUT giây (tránh treo cả lượt chạy)
- Mặc định dùng Chrome cài sẵn (BROWSER_CHANNEL = "chrome"); đặt None để dùng Chromium của Playwright
"""

import asyncio
import json
import re
import sys
import time
import logging
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import fb_transform

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

# Trình duyệt: "chrome" = Chrome cài sẵn trên máy (không cần profile; đo 29/10/2026: group 5 mất ~3 phút,
# còn Chromium ~13 phút). None = Chromium của Playwright (python -m playwright install chromium).
BROWSER_CHANNEL = "chrome"
HEADLESS = True

# Thử lại khi group lỗi hoặc thấy 0 bài
MAX_GROUP_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 60

# Giới hạn thời gian (giây) để một bài/một group không làm treo cả lượt chạy
POST_TIMEOUT = 90
GROUP_TIMEOUT = 900

# Thư mục xuất CSV (OneDrive). Excel dùng Power Query "From Folder" để gộp các file fb_leads_*.csv.
OUTPUT_DIR = WORK_DIR.parent.parent / "2. Output" / "fb_leads"

# Tham số dòng lệnh
ONCE = "--once" in sys.argv                    # chạy 1 lượt rồi dừng (dùng với Task Scheduler)
UPLOAD_DRIVE = "--upload-drive" in sys.argv    # chỉ khi vẫn cần đẩy JSON lên Google Drive cho n8n
if "--out-dir" in sys.argv:                    # đổi thư mục CSV (dùng khi test)
    OUTPUT_DIR = Path(sys.argv[sys.argv.index("--out-dir") + 1])
if "--groups" in sys.argv:                     # dùng file group khác groups.json (thử group mới)
    GROUPS_FILE = Path(sys.argv[sys.argv.index("--groups") + 1])
ACCEPT_NO_CONTACT = "--accept-no-contact" in sys.argv   # nhận cả bài tuyển dụng không có email/SĐT
FB_PROFILE = None                             # profile Chrome đã đăng nhập Facebook (xem fb_login_setup.py)
if "--profile" in sys.argv:
    FB_PROFILE = Path(sys.argv[sys.argv.index("--profile") + 1])
if "--scrolls" in sys.argv:                    # số lần cuộn mỗi group (mặc định MAX_SCROLL_ATTEMPTS)
    MAX_SCROLL_ATTEMPTS = int(sys.argv[sys.argv.index("--scrolls") + 1])
DEADLINE = None                               # --deadline HH:MM: quá giờ này thì dừng gọn (đã ghi CSV tới group cuối), không bắt đầu group mới
if "--deadline" in sys.argv:
    _h, _m = sys.argv[sys.argv.index("--deadline") + 1].split(":")
    DEADLINE = datetime.now().replace(hour=int(_h), minute=int(_m), second=0, microsecond=0)
STATUS_FILE = None                            # --status-file FILE: ghi tiến độ (JSON) sau mỗi group để run_fb_parallel.ps1 báo cáo
if "--status-file" in sys.argv:
    STATUS_FILE = Path(sys.argv[sys.argv.index("--status-file") + 1])
# Facebook đã đăng nhập luôn có request nền nên không bao giờ "networkidle"
WAIT_UNTIL = "domcontentloaded" if FB_PROFILE else "networkidle"

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


# SĐT chặt hơn PHONE_REGEX, dùng để nhận lead không có email: không dính số tiền (1.000.000.000),
# đầu số 02/03/05/07/08/09, trả về dạng 0xxxxxxxxx.
VALID_PHONE_REGEX = re.compile(r'(?<![\d.,])(?:\+?84|0)((?:[\s.\-]?\d){9})(?!\d|[.,]\d)')


def extract_valid_phones(text):
    if not text:
        return []
    phones = []
    for m in VALID_PHONE_REGEX.finditer(text):
        digits = re.sub(r'[\s.\-]', '', m.group(1))
        if digits[0] in "235789":
            phones.append("0" + digits)
    return list(dict.fromkeys(phones))


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
        await page.goto(post_url, wait_until=WAIT_UNTIL, timeout=20000)
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
    csv_name = filename.replace("fb_posts_", "fb_leads_").replace(".json", ".csv")
    stats = {"lead_moi": 0, "bo_sung": 0, "trung": 0}
    status = {"state": "running", "started": datetime.now().isoformat(timespec="seconds"), "groups_total": len(groups),
              "groups_done": 0, "groups_failed": [], "groups_skipped_deadline": 0, "rows": 0, **stats}

    def save_status(state=None):
        status.update(stats, state=state or status["state"], updated=datetime.now().isoformat(timespec="seconds"))
        if STATUS_FILE:
            STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")

    async def scrape_and_save(p, group, attempts):
        """Cào một group rồi GHI CSV NGAY (nếu lượt bị dừng giữa chừng thì các group đã xong vẫn còn)."""
        group_posts, ok = await scrape_group_with_retry(p, group, seen_emails_global, attempts)
        all_posts.extend(group_posts)
        logger.info(f"  → {group['name']}: {len(group_posts)} bài có liên hệ")
        if group_posts:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_posts, f, ensure_ascii=False, indent=2)
            part = {}
            csv_path, n_rows = fb_transform.write_csv(group_posts, OUTPUT_DIR, csv_name, mst_lookup="--no-mst" not in sys.argv,
                                                      append=True, stats=part)
            for k in stats:
                stats[k] += part.get(k, 0)
            status["rows"] += n_rows
            logger.info(f"  Đã ghi {n_rows} dòng (lead mới {part.get('lead_moi', 0)}, bổ sung {part.get('bo_sung', 0)}, "
                        f"trùng hoàn toàn bỏ {part.get('trung', 0)}) → {csv_name}")
        return ok

    async with async_playwright() as p:
        failed = []
        for group in groups:
            if past_deadline():
                status["groups_skipped_deadline"] += 1
                continue
            ok = await scrape_and_save(p, group, attempts=1)
            if ok:
                status["groups_done"] += 1
            else:
                failed.append(group)
            save_status()
            await asyncio.sleep(random.uniform(5, 15))       # nghỉ ngẫu nhiên giữa các group để giảm bị Facebook giới hạn

        # Group lỗi/thấy 0 bài: để nguội rồi mới thử lại một lần ở cuối lượt (thử dồn dập ngay làm bị giới hạn nặng hơn)
        if failed and not past_deadline():
            logger.info(f"Thử lại {len(failed)} group lỗi sau {RETRY_COOLDOWN_SECONDS}s")
            await asyncio.sleep(RETRY_COOLDOWN_SECONDS)
            for group in failed:
                if past_deadline():
                    status["groups_skipped_deadline"] += 1
                    continue
                if await scrape_and_save(p, group, attempts=2):
                    status["groups_done"] += 1
                else:
                    status["groups_failed"].append(group["name"])
                save_status()
                await asyncio.sleep(random.uniform(5, 15))
        else:
            status["groups_failed"] += [g["name"] for g in failed]

    save_status("deadline" if status["groups_skipped_deadline"] else "done")
    logger.info(f"Đã lưu {len(all_posts)} bài → {filename}")
    if UPLOAD_DRIVE and all_posts:
        logger.info("Đang upload Google Drive...")
        upload_to_gdrive(output_file, filename)
    if status["groups_skipped_deadline"]:
        logger.warning(f"HẾT GIỜ ({DEADLINE:%H:%M}): bỏ {status['groups_skipped_deadline']} group chưa kịp cào")
    return all_posts


RETRY_COOLDOWN_SECONDS = 300


def past_deadline():
    return DEADLINE is not None and datetime.now() >= DEADLINE


async def scrape_group_with_retry(p, group, seen_emails_global, attempts=MAX_GROUP_ATTEMPTS):
    """Mỗi lần thử mở trình duyệt mới (phiên + tab mới) để crash/trang rỗng không lan sang group khác.
    Link chỉ được ghi vào seen_emails_global khi lần thử thành công (thấy > 0 bài).
    Trả về (posts, ok): ok=False nghĩa là group lỗi/thấy 0 bài (khác với group xem được nhưng không có bài nào có liên hệ)."""
    for attempt in range(1, attempts + 1):
        browser = None
        seen_try = set(seen_emails_global)
        try:
            if FB_PROFILE:
                # Đã đăng nhập: dùng profile riêng (persistent context), close() của context đóng luôn trình duyệt
                browser = context = await p.chromium.launch_persistent_context(
                    str(FB_PROFILE),
                    channel=BROWSER_CHANNEL,
                    headless=HEADLESS,
                    viewport={"width": 1280, "height": 900},
                    locale="vi-VN",
                    ignore_default_args=["--enable-automation"],
                    args=['--disable-blink-features=AutomationControlled'],
                )
            else:
                browser = await p.chromium.launch(
                    channel=BROWSER_CHANNEL,
                    headless=HEADLESS,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    locale="vi-VN",
                )
            group_page = await context.new_page()
            post_page = await context.new_page()
            posts, total_seen = await asyncio.wait_for(
                scrape_single_group(group_page, post_page, group, seen_try),
                timeout=GROUP_TIMEOUT,
            )
            if total_seen > 0:
                seen_emails_global.update(seen_try)
                return posts, True
            logger.warning(f"  {group['name']}: thấy 0 bài (lần {attempt}/{attempts})")
        except asyncio.TimeoutError:
            logger.error(f"Group {group['name']} quá {GROUP_TIMEOUT}s (lần {attempt}/{attempts})")
        except Exception as e:
            logger.error(f"Lỗi group {group['name']} (lần {attempt}/{attempts}): {str(e)[:200]}")
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
        if attempt < attempts:
            await asyncio.sleep(RETRY_WAIT_SECONDS)

    logger.error(f"Bỏ qua {group['name']} sau {attempts} lần thử")
    return [], False


async def scrape_single_group(group_page, post_page, group, seen_emails_global):
    """Trả về (posts, total_seen). total_seen = số bài thấy trên trang, 0 nghĩa là trang rỗng/không truy cập được."""
    logger.info(f"\nĐang cào: {group['name']}")

    candidate_posts = []
    seen_urls = set()
    total_seen = 0

    await group_page.goto(group['url'], wait_until=WAIT_UNTIL, timeout=60000)
    await asyncio.sleep(5)

    page_content = await group_page.content()
    if "This content isn't available" in page_content or "must log in" in page_content.lower():
        logger.warning(f"  Group không truy cập được.")
        return [], 0

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
                if not preview_text:
                    continue

                if not is_recruitment_post(preview_text):
                    continue

                post_time = ""
                try:
                    time_elements = await element.query_selector_all('a[role="link"] span')
                    for te in time_elements:
                        t = await te.inner_text()
                        if re.match(r'\s*(\d+\s*(giờ|phút|giây|ngày|tuần|hours?|mins?|days?|h|m|d|w)\b|hôm|vừa)', t.lower()):
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

        # Đã đăng nhập Facebook gỡ bài ra khỏi DOM khi cuộn qua: bước nhỏ hơn chiều cao khung để không bỏ sót bài
        await group_page.evaluate(f"window.scrollBy(0, {800 if FB_PROFILE else 1500})")
        await smart_wait_for_new_posts(group_page, count_before)
        logger.info(f"  Scroll {scroll_num + 1}/{MAX_SCROLL_ATTEMPTS} - Thấy {total_seen} bài, tiềm năng: {len(candidate_posts)}")

    logger.info(f"  Lọc sơ bộ: {len(candidate_posts)}/{total_seen} bài có từ khóa tuyển dụng")

    # ── BƯỚC 2: Lấy full text + lọc email + dedup ──
    logger.info(f"  Bước 2: Lấy full text và lọc email...")

    posts = []
    skipped_no_email = 0
    skipped_dup = 0

    for i, post_data in enumerate(candidate_posts):
        if past_deadline():
            logger.warning(f"  HẾT GIỜ: dừng group này ở bài {i}/{len(candidate_posts)}")
            break
        post_url = post_data['postUrl']
        logger.info(f"  [{i+1}/{len(candidate_posts)}] Đang xử lý...")

        try:
            full_text = await asyncio.wait_for(get_full_post_text(post_page, post_url), timeout=POST_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(f"  ⚠ Bài quá {POST_TIMEOUT}s, dùng nội dung xem trước: {post_url}")
            full_text = None
        final_text = full_text if full_text and len(full_text) > len(post_data['preview_text']) else post_data['preview_text']

        emails = extract_emails(final_text)
        phones = extract_phones(final_text) if emails else extract_valid_phones(final_text)
        if not emails and not phones and not ACCEPT_NO_CONTACT:
            skipped_no_email += 1
            logger.info(f"  ⏭ Bỏ qua (không có email, không có SĐT)")
            continue

        # Chỉ bỏ bài có CÙNG LINK đã lấy. Bài có liên hệ đã gặp vẫn giữ lại: fb_transform.write_csv đối chiếu với kho
        # và chỉ bỏ khi bài không bổ sung thêm email/SĐT/tên công ty nào cho nhà tuyển dụng đó.
        if "url:" + post_url in seen_emails_global:
            skipped_dup += 1
            logger.info(f"  ⏭ Bỏ qua (đã lấy bài này trước đó)")
            continue
        seen_emails_global.add("url:" + post_url)

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

        logger.info(f"  ✅ Bài có liên hệ: {', '.join(emails or phones) or '(không có liên hệ)'}")
        await asyncio.sleep(0.5)

    logger.info(f"  Bỏ qua: {skipped_no_email} không có email/SĐT, {skipped_dup} trùng link")
    return posts, total_seen


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
    # Nạp email từ CSV cũ để dedup giữa các lần chạy (mỗi lần Task Scheduler gọi là một tiến trình mới)
    seen_emails_global = fb_transform.load_seen_emails(OUTPUT_DIR)
    seen_emails_global |= {"tel:" + p for p in fb_transform.load_seen_phones(OUTPUT_DIR)}
    seen_emails_global |= {"url:" + l for l in fb_transform.load_existing(OUTPUT_DIR)[0]}
    logger.info(f"Email đã có trong CSV: {len(seen_emails_global)}")
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
            if STATUS_FILE:
                STATUS_FILE.write_text(json.dumps({"state": "failed", "error": str(e)[:300],
                                                   "updated": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
            if ONCE:
                sys.exit(1)

        if ONCE:
            break

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