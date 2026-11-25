"""
FB TRANSFORM - bản Python của node "Lọc trường1" + "Gộp" trong workflow n8n
"FB Scraper - Tuyển Dụng → Google Sheets", để bỏ phụ thuộc Google Drive/Sheets.

Đầu vào : list bài đăng do fb_scraper_no_login*.py tạo (postId, postUrl, text, emails, phones, ...)
Đầu ra  : dòng CSV với các cột của "2. Output\\Format output.xlsx"

Port giữ nguyên hành vi của code n8n (kể cả điểm lạ) để so khớp được với bản gốc:
- \\b trong JS chỉ nhận chữ ASCII  -> dùng re.ASCII cho các pattern có \\b
- \\d trong JS chỉ là 0-9           -> dùng [0-9]
- "." trong JS không khớp \\r, \\u2028, \\u2029
- $ không có cờ m                   -> dùng \\Z
- BOLD_FIX: code n8n có bước đổi chữ in đậm Unicode (𝐀..) về chữ thường nhưng thực tế
  KHÔNG chạy được (JS tách chuỗi theo đơn vị UTF-16 nên không khớp bảng). Để mặc định False
  cho giống n8n; đặt True nếu muốn sửa.
"""

import csv
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

BOLD_FIX = False

import fb_cluster
import fb_customers
import fb_enrich
import fb_mst_lookup

# 9 cột đầu giống "2. Output\Format output.xlsx"; các cột sau là dữ liệu bổ sung (fb_enrich.py, fb_customers.py)
CSV_BASE_COLUMNS = [
    "STT", "Tên công ty", "Địa chỉ", "Nội dung bài viết", "SĐT",
    "Email", "Ngày đăng bài", "Thời gian crawl", "Link bài viết",
]
CRM_COLUMNS = ["Trạng thái CRM", "ID CRM", "Tên trong CRM"]
LOOKUP_COLUMNS = ["Link tra MST", "MST", "Ghi chú tra MST"]
CSV_COLUMNS = CSV_BASE_COLUMNS + ["Group"] + fb_enrich.EXTRA_COLUMNS + CRM_COLUMNS + LOOKUP_COLUMNS + ["Loại dòng"]

# Danh sách công ty trong CRM (tạo bằng build_customer_index.py). Chưa có file thì bỏ qua đối chiếu.
CUSTOMER_INDEX = Path(__file__).parent.parent.parent / "3. Reference" / "customers_index.csv"
_NOT_COMPANY_START = ("minh ", "chung ", "ban ", "team ", "nhan vien", "tuyen ")


def _crm_lookup(idx, name):
    """Bỏ qua tên rỗng, tên chỉ là địa danh, hoặc câu bị bóc nhầm (vd 'mình cần')."""
    if not idx or not name or fb_enrich.is_place_name(name):
        return "", "", ""
    if fb_customers.normalize(name).startswith(_NOT_COMPANY_START):
        return "", "", ""
    return idx.match(name)

# ========================================
# TIỆN ÍCH (giống JS)
# ========================================

_JS_WS = ("\t\n\x0b\x0c\r \xa0         "
          "       　﻿")
_DOT = r"[^\n\r  ]"
_I = re.I


def _trim(s):
    return s.strip(_JS_WS)


def _js_substring(s, n):
    """substring(0, n) tính theo đơn vị UTF-16 như JS."""
    return s.encode("utf-16-le")[: n * 2].decode("utf-16-le", errors="ignore")


def _split_first(pattern, s):
    return re.split(pattern, s)[0]


# ========================================
# 1. CLEAN TEXT
# ========================================

_RE_CLEAN_1 = re.compile(
    r"^[\s\S]*?·\n\s*(?:[0-9]+\s*(?:phút|giờ|ngày|tuần|tháng|giây)"
    r"|(?:[0-9]{1,2}\s+Tháng\s+[0-9]{1,2}[^\n]*))\s*\n\s*·\s*\n", _I)
_RE_CLEAN_2 = re.compile(
    r"\n?\s*(?:Tất cả cảm xúc[\s\S]*"
    r"|[0-9]+\s*(?:bình luận|lượt chia sẻ)\s*\nThích[\s\S]*"
    r"|(?:^|\n)Thích\nBình luận\nChia sẻ[\s\S]*)", _I | re.M)

_BOLD = {}
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _BOLD[chr(0x1D400 + _i)] = _c
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _BOLD[chr(0x1D41A + _i)] = _c
for _i in range(10):
    _BOLD[chr(0x1D7CE + _i)] = str(_i)


def clean_text(text):
    if not text:
        return ""
    text = _RE_CLEAN_1.sub("", text, count=1)
    text = _RE_CLEAN_2.sub("", text, count=1)
    if BOLD_FIX:
        text = "".join(_BOLD.get(c, c) for c in text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return _trim(text)


# ========================================
# 2. NGÀY ĐĂNG
# ========================================

_RE_TIME = re.compile(r"·\n([0-9]+\s*(?:phút|giờ|giây))\s*\n", _I)
_RE_DATE = re.compile(r"·\n([0-9]{1,2}\s+Tháng\s+[0-9]{1,2}(?:\s+lúc\s+[0-9:]+)?)\s*\n", _I)
_RE_DAYS = re.compile(r"·\n([0-9]+)\s*ngày\s*\n", _I)
_RE_WEEK = re.compile(r"·\n([0-9]+)\s*tuần\s*\n", _I)
_RE_REL_LOOSE = re.compile(r"(?:^|\n)\s*([0-9]+)\s*(giây|phút|giờ|ngày|tuần)(?:\s*trước)?\s*(?:\n|$)", _I)
_RE_POSTTIME_OK = re.compile(r"^\s*[0-9]+\s*(?:giây|phút|giờ|ngày|tuần)|tháng|hôm|vừa", _I)


def _scraped_date(post):
    s = post.get("scrapedAt")
    if s:
        try:
            return datetime.fromisoformat(s[:19]).date()
        except ValueError:
            pass
    return datetime.now().date()


def extract_ngay_dang(post):
    text = post.get("text") or ""
    scraped = _scraped_date(post)
    scraped_s = scraped.isoformat()

    if _RE_TIME.search(text):
        return scraped_s
    m = _RE_DATE.search(text)
    if m:
        return _trim(m.group(1))
    m = _RE_DAYS.search(text)
    if m:
        return (scraped - timedelta(days=int(m.group(1)))).isoformat()
    m = _RE_WEEK.search(text)
    if m:
        return (scraped - timedelta(days=int(m.group(1)) * 7)).isoformat()
    # Bản n8n chỉ bắt "· 24 phút ·"; Facebook còn hiện "24 phút trước" ở đầu bài
    m = _RE_REL_LOOSE.search(text[:400])
    if m:
        n, unit = int(m.group(1)), m.group(2).lower()
        return (scraped - timedelta(days=n * (7 if unit == "tuần" else 1 if unit == "ngày" else 0))).isoformat()
    pt = post.get("postTime")
    return _trim(pt) if pt and _RE_POSTTIME_OK.search(pt) and _trim(pt) else scraped_s


# ========================================
# 3. ĐỊA CHỈ
# ========================================

_WS_ASCII_NBSP = r"[ \t\r\n\f\v\xa0]"
_ADDR_REPL = [
    (re.compile(r"\bTPHCM\b", _I | re.A), "TP. Hồ Chí Minh"),
    (re.compile(r"\bTP\." + _WS_ASCII_NBSP + r"*HCM\b", _I | re.A), "TP. Hồ Chí Minh"),
    (re.compile(r"\bTP\.HCM\b", _I | re.A), "TP. Hồ Chí Minh"),
    (re.compile(r"\bHCM\b", re.A), "TP. Hồ Chí Minh"),
    (re.compile(r"\bHN\b", re.A), "Hà Nội"),
    (re.compile(r"\bĐN\b", re.A), "Đà Nẵng"),
    (re.compile(r"\bBD\b", re.A), "Bình Dương"),
    (re.compile(r"\bHP\b", re.A), "Hải Phòng"),
    (re.compile(r"TP\.\s+TP\.", _I), "TP."),
]


def normalize_addr(s):
    if not s:
        return ""
    s = re.sub(r"^[•\-\*\s\[]+", "", s)
    s = re.sub(r"[\]\s]+\Z", "", s)
    for rx, rep in _ADDR_REPL:
        s = rx.sub(rep, s)
    s = re.sub(r"^làm\s*việc\s+", "", s, flags=_I)
    s = re.sub(r"[,;\s\.]+\Z", "", s)
    return _trim(s)


_GEO_WORDS = [
    "hà nội", "hồ chí minh", "đà nẵng", "hải phòng", "cần thơ",
    "bình dương", "đồng nai", "nghệ an", "thanh hóa", "quảng ninh",
    "thái nguyên", "nam định", "khánh hòa", "lâm đồng", "bắc ninh",
    "sài gòn", "thủ đức", "tân bình", "hoàng mai", "thanh xuân",
    "đống đa", "cầu giấy", "mỹ đình", "nam từ liêm", "duy tân",
    "gò vấp", "tân phú", "bình thạnh", "hạ long", "thanh trì",
    "ninh kiều", "biên hòa", "vĩnh hưng", "khuất duy tiến",
    "thạch thất", "hoàng quốc việt", "nguyễn trãi", "lê văn lương",
    "phạm văn đồng", "trần duy hưng", "xuân thủy", "cầu diễn",
    "nguyễn xiển", "lê đức thọ", "nguyễn huy tưởng", "duy tân",
    "quận", "huyện", "phường", "đường", "phố", "ngõ", "ngách",
    "tòa", "lô", "số ", "tp.", "tỉnh",
    "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9", "q10", "q11", "q12",
    "q.1", "q.2", "q.3", "q.4", "q.5", "q.6", "q.7", "q.8", "q.9", "q.10", "q.11", "q.12",
]
_RE_BAD_ADDR = re.compile(r"thứ\s*[0-9]|chủ\s*nhật|giờ\s*hành\s*chính|sáng|chiều", _I)


def is_valid_addr(s, has_keyword):
    if not s or len(s) < 3:
        return False
    if "@" in s or "http" in s:
        return False
    if _RE_BAD_ADDR.search(s):
        return False
    if has_keyword:
        return True
    lower = s.lower()
    return any(w in lower for w in _GEO_WORDS)


_RE_P1 = [
    re.compile(r"(?:•\s*)?(?:\*{1,2})?(?:địa\s*(?:chỉ|điểm)(?:\s*làm\s*việc)?)\s*[:\-]\s*([^\n]{3,150})", _I),
    re.compile(r"(?:làm\s*việc\s*tại|trụ\s*sở)\s*[:\-]\s*([^\n]{3,120})", _I),
    re.compile(r"(?:\*\s*)?ĐỊA\s*CHỈ\s*[:\-]\s*([^\n]{3,120})", _I),
]
_RE_P2 = re.compile(
    r"(?:địa\s*(?:chỉ|điểm)(?:\s*làm\s*việc)?|ĐỊA\s*ĐIỂM\s*LÀM\s*VIỆC)[:\s]*\n\s*(?:[-•]\s*)?([^\n]{3,150})", _I)
_RE_P3 = re.compile(r"khu\s*vực\s+([^\n,]{3,40},\s*[^\n]{3,40})", _I)
_RE_P4 = re.compile(r"\([^)]+\)\s*-\s*(?:khu\s*vực\s+)?([^\n]{5,60})", _I)
_RE_P4B = re.compile(r"^([^\n(\[\]]{3,30}/[^\n(\[\]]{2,25})(?:\s*\([^)]*\))?\Z")
_RE_P5_SPLIT = re.compile(r"\s*[-–—]\s*")
_RE_P6 = re.compile(r"^\[([^\]]{2,60})\]")
_RE_P6_KW = re.compile(r"tuyển|dụng|group", _I)
_RE_P6_DASH = re.compile(r"-\s*([^-\]]+?)(?:\s+TUYỂN|\s+CẦN|\Z)", _I)
_RE_P6_LAMVIEC = re.compile(r"làm\s*việc\s+(" + _DOT + r"+)", _I)
_RE_P6_FIX1 = re.compile(r"^(TP\.[^0-9,]+)\s+(Q[0-9]+)" + _DOT + r"*\Z", _I)
_RE_P6_FIX2 = re.compile(r"^(Q[0-9]+)[^,]*,\s*(TP\." + _DOT + r"+)\Z")
_RE_P7 = re.compile(r"([0-9]+[A-Za-z/\-]*\s+[^\n,@]{3,40},\s*[^\n,@]{3,40},\s*[^\n@]{3,40})")
_RE_P8 = re.compile(r"tòa\s+nhà\s+[^\n,]{2,30},\s*[^\n]{5,80}", _I)
_CITY_LIST = [
    r"TP\. Hồ Chí Minh", "Hà Nội", "Đà Nẵng", "Hải Phòng",
    "Bình Dương", "Cần Thơ", "Đồng Nai", "Nghệ An",
    "Thanh Hóa", "Quảng Ninh",
]
_RE_P9 = [
    re.compile(r"(?:^|\n)\s*([^\n0-9@,]{2,30},\s*" + c + r")\s*(?:\n|$)", _I | re.M)
    for c in _CITY_LIST
]


def extract_dia_chi(text):
    if not text:
        return ""

    # P1
    for rx in _RE_P1:
        m = rx.search(text)
        if m and m.group(1):
            addr = normalize_addr(_trim(m.group(1)))
            if is_valid_addr(addr, True):
                return addr

    # P2
    m = _RE_P2.search(text)
    if m and m.group(1):
        addr = normalize_addr(_trim(m.group(1)))
        if is_valid_addr(addr, True):
            return addr

    # P3
    m = _RE_P3.search(text)
    if m and m.group(1):
        addr = normalize_addr(_trim(m.group(1)))
        if is_valid_addr(addr, False):
            return addr

    # P4
    m = _RE_P4.search(text)
    if m and m.group(1):
        addr = normalize_addr(_trim(m.group(1)))
        if is_valid_addr(addr, False):
            return addr

    # P4b
    first_line = text.split("\n")[0] or ""
    m = _RE_P4B.search(first_line)
    if m and m.group(1):
        addr = normalize_addr(_trim(m.group(1)))
        if len(addr) <= 40 and is_valid_addr(addr, False):
            return addr

    # P5
    parts = _RE_P5_SPLIT.split(first_line)
    if len(parts) >= 2:
        last = normalize_addr(_trim(parts[-1]))
        if is_valid_addr(last, False) and len(last) <= 30:
            return last

    # P6
    m = _RE_P6.search(text)
    if m and m.group(1):
        inner = m.group(1)
        if not _RE_P6_KW.search(inner):
            addr = normalize_addr(_trim(inner))
            addr = _RE_P6_FIX1.sub(r"\2, \1", addr, count=1)
            addr = _RE_P6_FIX2.sub(r"\1, \2", addr, count=1)
            if is_valid_addr(addr, False):
                return addr
        else:
            d = _RE_P6_DASH.search(inner)
            if d and d.group(1):
                addr = normalize_addr(_trim(d.group(1)))
                if is_valid_addr(addr, False):
                    return addr
            lv = _RE_P6_LAMVIEC.search(inner)
            if lv and lv.group(1):
                addr = normalize_addr(_trim(lv.group(1)))
                if is_valid_addr(addr, False):
                    return addr

    # P7
    m = _RE_P7.search(text)
    if m and m.group(1):
        addr = normalize_addr(_trim(m.group(1)))
        if is_valid_addr(addr, False) and "@" not in addr:
            return addr

    # P8
    m = _RE_P8.search(text)
    if m and m.group(0):
        addr = normalize_addr(_trim(m.group(0)))
        if is_valid_addr(addr, False):
            return addr

    # P9
    for rx in _RE_P9:
        m = rx.search(text)
        if m and m.group(1):
            addr = normalize_addr(_trim(m.group(1)))
            if is_valid_addr(addr, False):
                return addr

    return ""


# ========================================
# 4. TÊN CÔNG TY
# ========================================

_GEO_NAMES = [
    "HN", "HCM", "ĐN", "BD", "HP", "CT",
    "Hà Nội", "Sài Gòn", "TPHCM", "TP.HCM", "TP. HCM",
    "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Bình Dương",
    "HÀ NỘI", "SÀI GÒN", "ĐÀ NẴNG", "HẢI PHÒNG", "BÌNH DƯƠNG",
    "Cần Thơ", "CẦN THƠ", "Đồng Nai", "ĐỒNG NAI",
    "TPHCM", "TP.HCM",
    "HOÀNG QUỐC VIỆT", "Hoàng Quốc Việt",
    "NGUYỄN TRÃI", "PHẠM VĂN ĐỒNG", "LÊ VĂN LƯƠNG",
    "TRẦN DUY HƯNG", "XUÂN THỦY", "DUY TÂN",
    "NGUYỄN XIỂN", "LÊ ĐỨC THỌ",
]

_INVALID_NAME = [re.compile(p, _I) for p in [
    r"\[", r"\]", r"tiêu\s*đề", r"họ\s*tên", r"vị\s*trí\s*ứng", r"tên\s*công\s*ty",
    r"xem\s*thêm", r"nếu\s*bạn", r"khu\s*vực", r"team\s*mình", r"không\s*yêu\s*cầu",
    r"thứ\s*[0-9]", r"chủ\s*nhật",
]]

_BLACKLIST = [
    "gmail", "yahoo", "hotmail", "tham gia", "bình luận", "chia sẻ", "thích",
    "xem thêm", "tác giả", "facebook", "youtube", "tiktok", "mxh",
    "để hoàn thiện", "trang bị", "mình đã", "ứng viên", "ứng tuyển",
    "môi trường", "quyền lợi", "yêu cầu", "mô tả", "không yêu cầu",
    "phúc lợi", "công việc chính",
    "nếu bạn", "chúng tôi", "team mình", "khu vực",
    "tuyển dụng video", "tuyển dụng nhân", "tuyển dụng việc",
]


def _is_geo_name(name):
    return _trim(name) in _GEO_NAMES


def is_valid_company_name(name):
    if not name or len(name) < 2:
        return False
    if len(name.split(" ")) > 7:
        return False
    if re.match(r"[0-9]", name):
        return False
    if _is_geo_name(name):
        return False
    return not any(rx.search(name) for rx in _INVALID_NAME)


def _is_black(s):
    lower = s.lower()
    return any(b in lower for b in _BLACKLIST)


_RE_TRAIL_PAREN = re.compile(r"\s*\([^)]*\)\s*\Z")


def _clean_name(s):
    s = _RE_TRAIL_PAREN.sub("", s, count=1)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[:\-\s!]+\Z", "", s)
    return _trim(s)


def _try_return(candidate):
    name = _clean_name(candidate)
    if not name:
        return None
    if not is_valid_company_name(name):
        return None
    if _is_black(name):
        return None
    norm = normalize_addr(name)
    if norm != name and is_valid_addr(norm, False):
        return None
    return name


_RE_N_P1A = re.compile(r"\[([^\]]{2,40})\]\s+(?:TUYỂN|CẦN\s+TUYỂN)", _I)
_RE_N_P1B = re.compile(r"\[([^\]]{2,60}?)(?:\s+TUYỂN|\s+CẦN\s+TUYỂN)", _I)
_RE_N_P2 = re.compile(r"^\[([^\]]{2,40})\](?!\s*(?:tuyển|cần|mô\s*tả))", _I)
_RE_N_P2_GEO = re.compile(r"làm việc|tuyển dụng|group|ứng tuyển", _I)
_RE_N_P3 = re.compile(r"\*{1,2}công\s*ty\s*[:\s]+([^\n*\-]{2,50})", _I)
_RE_N_P4 = re.compile(r"công\s*ty\s+(?:tnhh\s+|cổ\s*phần\s+|cp\s+|mtv\s+)?([^\n,\-]{2,50}?)\s+tuyển", _I)
_RE_N_P5 = re.compile(r"lĩnh\s*vực[^\n]*-\s*([^\n]{2,40}?)\s+tuyển", _I)
_RE_N_P6 = re.compile(r"^(" + _DOT + r"{2,50}?)\s*[-–]\s*(?:TUYỂN|CẦN TUYỂN)")
_RE_N_P6B = re.compile(r"(?:^|\n)\s*([A-ZÀ-ỹ][A-ZÀ-ỹ ]{1,30}[A-ZÀ-ỹ])\s+ĐANG\s+(?:TÌM|TUYỂN)")
_RE_N_P9 = re.compile(r"([A-Z][A-Z ]{0,20}[A-Z])\s+là\s+(?:trung\s*tâm|công\s*ty|tập\s*đoàn|thương\s*hiệu)")
_RE_N_P9_BAD = re.compile(r"chúng\s*tôi|đây|bạn|ứng\s*viên", _I)
_RE_N_P7_HEAD = re.compile(r"^\[[^\]]*\]\s*")
_RE_N_P7 = re.compile(
    r"^(" + _DOT + r"+?)\s+(?:TUYỂN\s+DỤNG|TUYỂN\s+GẤP|CẦN\s+TUYỂN\s+GẤP|CẦN\s+TUYỂN|TUYỂN)")
_RE_N_P8_SKIP = re.compile(r"^[#0-9\-•*\[@]")
_RE_N_TUYEN = re.compile(r"tuyển", _I)


def extract_ten_cong_ty(text):
    if not text:
        return ""

    lines = [l for l in (_trim(x) for x in text.split("\n")) if len(l) > 0]
    first_line = lines[0] if lines else ""
    first_clean = _trim(_RE_TRAIL_PAREN.sub("", first_line, count=1))

    # P1
    head = _js_substring(text, 300)
    m = _RE_N_P1A.search(head)
    if m and m.group(1):
        name = _try_return(re.split(r"\s*-\s*", m.group(1))[0])
        if name:
            return name
    m = _RE_N_P1B.search(head)
    if m and m.group(1):
        name = _try_return(_trim(re.split(r"\s*[-–]\s*", m.group(1))[0]))
        if name:
            return name

    # P2
    m = _RE_N_P2.search(text)
    if m and m.group(1):
        bc = _trim(m.group(1))
        bn = normalize_addr(bc)
        is_geo = (_is_geo_name(bc) or _is_geo_name(bn) or is_valid_addr(bn, False)
                  or bool(_RE_N_P2_GEO.search(bc)))
        if not is_geo:
            name = _try_return(bc)
            if name:
                return name

    # P3
    m = _RE_N_P3.search(text)
    if m and m.group(1):
        name = _try_return(m.group(1))
        if name:
            return name

    # P4
    m = _RE_N_P4.search(text)
    if m and m.group(1):
        name = _try_return(m.group(1))
        if name:
            return name

    # P5
    m = _RE_N_P5.search(text)
    if m and m.group(1):
        name = _try_return(m.group(1))
        if name:
            return name

    # P6
    m = _RE_N_P6.search(first_clean)
    if m and m.group(1):
        name = _try_return(m.group(1))
        if name:
            return name

    # P6b
    m = _RE_N_P6B.search(text)
    if m and m.group(1):
        name = _try_return(_trim(m.group(1)))
        if name:
            return name

    # P9
    m = _RE_N_P9.search(text)
    if m and m.group(1):
        cand = _trim(m.group(1))
        if not _RE_N_P9_BAD.search(cand):
            name = _try_return(cand)
            if name:
                return name

    # P7
    first_p7 = _trim(_RE_N_P7_HEAD.sub("", first_clean, count=1))
    m = _RE_N_P7.search(first_p7)
    if m and m.group(1):
        name = _try_return(m.group(1))
        if name:
            return name

    # P8
    for i in range(len(lines) - 1):
        curr, nxt = lines[i], lines[i + 1]
        if _RE_N_P8_SKIP.match(curr):
            continue
        if len(curr.split(" ")) > 6:
            continue
        if len(curr) < 2 or len(curr) > 60:
            continue
        if curr != curr.upper():
            continue
        if not _RE_N_TUYEN.search(nxt):
            continue
        name = _try_return(curr)
        if name:
            return name

    return ""


# ========================================
# 5. MAIN
# ========================================

_GENERIC_DOMAINS = ["gmail", "yahoo", "hotmail", "outlook", "icloud"]
_SKIP_DOMAIN_KEYWORDS = ["school", "edu", "ac", "gov", "org", "uni", "college", "giadinh"]


def _capitalize_domain(domain):
    return domain if "-" in domain else domain.upper()


def _is_skip_domain(domain):
    lower = domain.lower()
    return any(s in lower for s in _SKIP_DOMAIN_KEYWORDS)


# Từ khóa tuyển dụng bị bóc nhầm thành tên công ty ("CẦN TUYỂN ..." -> "CẦN", "Hot Job")
_BAD_NAMES = {"CẦN", "TUYỂN", "CẦN TUYỂN", "TUYỂN GẤP", "TUYỂN DỤNG", "GẤP", "HOT", "HOT JOB", "VIỆC LÀM", "NHÂN SỰ"}


# Từ mô tả loại hình/lĩnh vực: tên chỉ gồm các từ này (vd "Sản xuất & Thương mại cần") không phải tên công ty
_GENERIC_WORDS = {
    "công", "ty", "tnhh", "cổ", "phần", "cp", "mtv", "một", "thành", "viên", "sản", "xuất", "sx", "thương", "mại", "tm",
    "dịch", "vụ", "dv", "xây", "dựng", "đầu", "tư", "phát", "triển", "kinh", "doanh", "vận", "tải", "du", "lịch",
    "giáo", "dục", "và", "&", "cần", "đang", "tuyển", "dụng", "gấp",
}


def _is_bad_name(name):
    name = (name or "").strip(" -–:|.!")
    if name.upper() in _BAD_NAMES:
        return True
    words = re.findall(r"[\wÀ-ỹ&]+", name.lower())
    return bool(words) and all(w in _GENERIC_WORDS for w in words)


def _mst_link(company, address):
    """Link tìm kiếm 'địa chỉ + mst' cho lead chưa có tên công ty nhưng có địa chỉ cụ thể (có số nhà và ít nhất 2 phần)."""
    address = (address or "").strip()
    if company or not (re.search(r"[0-9]", address) and "," in address):
        return ""
    return "https://www.google.com/search?q=" + quote(address + " mst công ty")


def transform_post(post):
    """Một bài thô -> dict giống output node 'Lọc trường1'."""
    cleaned = clean_text(post.get("text"))
    ten = extract_ten_cong_ty(cleaned)
    if _is_bad_name(ten):
        ten = ""

    emails = post.get("emails") or []
    if not ten and emails:
        domain = ((emails[0].split("@") + [""])[1]).split(".")[0].lower()
        if domain and domain not in _GENERIC_DOMAINS and not _is_skip_domain(domain):
            ten = _capitalize_domain(domain)

    return {
        "postId": post.get("postId"),
        "postUrl": post.get("postUrl"),
        "groupName": post.get("groupName"),
        "email": ", ".join(emails),
        "phone": ", ".join(post.get("phones") or []),
        "ngayDang": extract_ngay_dang(post),
        "tenCongTy": ten,
        "diaChi": extract_dia_chi(cleaned),
        "scrapedAt": post.get("scrapedAt"),
        "text": cleaned,
    }


# ========================================
# 6. XUẤT CSV (thay Google Sheets)
# ========================================

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_TEXT_COLUMNS = ("Tên công ty", "Địa chỉ", "Nội dung bài viết")


def _safe_cell(value):
    """Chặn Excel hiểu nội dung Facebook là công thức khi mở trực tiếp file CSV."""
    return "'" + value if value.startswith(_FORMULA_START) else value


def load_existing(folder):
    """Đọc mọi CSV đã xuất trong folder -> (tập link đã có, tổng số dòng)."""
    links, total = set(), 0
    for f in sorted(Path(folder).glob("fb_leads_*.csv")):
        with open(f, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                total += 1
                link = (row.get("Link bài viết") or "").strip()
                if link:
                    links.add(link)
    return links, total


def load_seen_emails(folder):
    """Email đã có trong các CSV cũ, để dedup email giữa các lần chạy (mỗi lượt chạy là một tiến trình mới)."""
    emails = set()
    for f in sorted(Path(folder).glob("fb_leads_*.csv")):
        with open(f, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                for e in (row.get("Email") or "").split(","):
                    if e.strip():
                        emails.add(e.strip())
    return emails


def load_seen_phones(folder):
    """SĐT của các lead không có email trong CSV cũ (lead có email đã dedup theo email)."""
    phones = set()
    for f in sorted(Path(folder).glob("fb_leads_*.csv")):
        with open(f, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("Email") or "").strip():
                    continue
                for p in (row.get("SĐT") or "").split(","):
                    if p.strip():
                        phones.add(p.strip())
    return phones


def write_csv(posts, folder, filename, mst_lookup=False, append=False, stats=None):
    """Biến đổi + loại trùng theo link + đối chiếu với kho + ghi CSV. Trả về (đường dẫn hoặc None, số dòng ghi).
    Bài có liên hệ đã gặp KHÔNG bị bỏ: fb_cluster.classify_new xếp mỗi bài vào "Lead mới" (nhà tuyển dụng chưa có trong kho),
    "Bổ sung" (nhà tuyển dụng đã có nhưng bài thêm email/SĐT/tên công ty mới) hoặc "Trùng" (không thêm gì -> mới bỏ).
    mst_lookup=True: lead thiếu tên công ty nhưng có địa chỉ cụ thể thì tra tên + MST theo địa chỉ (fb_mst_lookup.py).
    append=True: ghi nối vào file nếu đã có (ghi từng group); stats (dict) nhận số lead_moi / bo_sung / trung."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    seen_links, total = load_existing(folder)
    crm = fb_customers.load_index(CUSTOMER_INDEX)

    # Bước 1: biến đổi + loại trùng link
    cands = []
    for post in posts:
        r = transform_post(post)
        link = (r["postUrl"] or "").strip()
        if link in seen_links:
            continue
        seen_links.add(link)
        cands.append((r, link))

    # Bước 2: đối chiếu với kho (các CSV đã có), chỉ bỏ bài không bổ sung thông tin nào
    prelim = [{"Email": r["email"], "SĐT": r["phone"], "Tên công ty": r["tenCongTy"] or "", "Nội dung bài viết": r["text"],
               "Link bài viết": link, "Thời gian crawl": r["scrapedAt"], "MST": "", "Tên trong CRM": "", "_file": filename}
              for r, link in cands]
    kinds = fb_cluster.classify_new(fb_cluster.load_rows(folder), prelim) if prelim else []
    if stats is not None:
        stats.update(lead_moi=kinds.count("Lead mới"), bo_sung=kinds.count("Bổ sung"), trung=kinds.count("Trùng"))

    rows = []
    for (r, link), kind in zip(cands, kinds):
        if kind == "Trùng":
            continue
        total += 1
        mst = {"mst": "", "note": ""}
        if mst_lookup and _mst_link(r["tenCongTy"], r["diaChi"]):
            mst = fb_mst_lookup.lookup(r["diaChi"])
            if mst["confidence"] == "Cao":
                r["tenCongTy"] = mst["name"]
        extra = fb_enrich.enrich(r)
        fallback = extra.pop("_tenCongTy")
        extra["Vị trí tuyển"] = _safe_cell(extra["Vị trí tuyển"])
        company = r["tenCongTy"] or fallback
        status, crm_id, crm_name = _crm_lookup(crm, company)
        rows.append({
            **extra,
            "Trạng thái CRM": status, "ID CRM": crm_id, "Tên trong CRM": _safe_cell(crm_name),
            "Link tra MST": _mst_link(company, r["diaChi"]),
            "MST": mst["mst"], "Ghi chú tra MST": mst["note"],
            "Group": r["groupName"] or "",
            "STT": total,
            "Tên công ty": _safe_cell(company),
            "Địa chỉ": _safe_cell(r["diaChi"]),
            "Nội dung bài viết": _safe_cell(r["text"]),
            "SĐT": r["phone"],
            "Email": r["email"],
            "Ngày đăng bài": r["ngayDang"],
            "Thời gian crawl": r["scrapedAt"],
            "Link bài viết": link,
            "Loại dòng": kind,
        })

    if not rows:
        return None, 0

    path = folder / filename
    new_file = not (append and path.exists())
    with open(path, "w" if new_file else "a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
        if new_file:
            w.writeheader()
        w.writerows(rows)
    return path, len(rows)
