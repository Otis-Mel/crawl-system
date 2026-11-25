"""
FB MST LOOKUP - tra tên công ty + mã số thuế từ địa chỉ trong bài tuyển dụng

Làm đúng như người dùng tra tay: search "địa chỉ + mst công ty", rồi chỉ nhận kết quả có cùng số nhà + tên đường.
- Bing chỉ trả MST + tên công ty trong tiêu đề, còn địa chỉ nằm ở trang chi tiết; nên mở tối đa MAX_DETAIL trang danh bạ
  doanh nghiệp (masothue, infodoanhnghiep, thuvienphapluat...) và chỉ nhận công ty có địa chỉ trùng số nhà + tên đường.
- Chỉ gửi địa chỉ công ty lên công cụ tìm kiếm (Bing), không gửi email/SĐT/nội dung bài.
- Kết quả được nhớ trong 3. Reference\\mst_cache.json để cùng một địa chỉ không phải tra lại.
- Mọi lỗi mạng/định dạng đều trả về "không tìm thấy", không làm hỏng lượt chạy.

Độ tin cậy:
  "Cao"          đúng một công ty (một MST) khớp địa chỉ -> dùng làm tên công ty
  "Nhiều công ty" nhiều MST cùng khớp (vd tòa nhà dùng chung) -> KHÔNG gán, chỉ liệt kê để người xem chọn
  ""             không tìm thấy
Tên tra được là tên theo đăng ký; địa chỉ đăng ký có thể ghi tên phường/quận cũ nên chỉ so khớp số nhà + tên đường.
"""

import html
import json
import re
import base64
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

CACHE_FILE = Path(__file__).parent.parent.parent / "3. Reference" / "mst_cache.json"
MAX_DETAIL = 4               # số trang danh bạ tối đa mở cho mỗi địa chỉ
REGISTRY_SITES = ("masothue.com", "infodoanhnghiep.com", "thuvienphapluat.vn", "thongtincongty.vn", "dulieuphapluat.vn", "hosocongty.vn")
DELAY_SECONDS = 2.0          # nghỉ giữa hai lần tra thật để không dồn dập
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0 Safari/537.36"

_MST = re.compile(r"(?<!\d)(\d{10}(?:-\d{3})?)(?!\d)")
_NAME = re.compile(
    r"((?:CÔNG TY|Công [Tt]y|CHI NHÁNH|Chi [Nn]hánh|DOANH NGHIỆP TƯ NHÂN|Doanh [Nn]ghiệp [Tt]ư [Nn]hân|HỢP TÁC XÃ|Hợp [Tt]ác [Xx]ã)"
    r"\s+[^,.|;\n]{3,80})")
_NAME_CUT = re.compile(r"\s*(?:-\s|–\s|Mã số|MST|Địa chỉ|Quận|Phường|Thành phố|TP\.|Việt Nam).*$", re.S)
_ADDR_HEAD = re.compile(r"^\s*(?:số\s*)?(\d+[A-Za-z]?(?:[/-]\d+[A-Za-z]?)*)\s*(?:đường|phố|ngõ|ngách|đ\.)?\s*([^,]+)", re.I)

_cache = None
_last_call = 0.0


def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", s.lower()).strip()


def _load_cache():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8-sig"))
        except Exception:
            _cache = {}
    return _cache


def _save_cache():
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _street_pattern(address):
    """Regex (trên chữ không dấu) để nhận ra 'số nhà + tên đường' của địa chỉ trong kết quả tìm kiếm."""
    m = _ADDR_HEAD.match(address or "")
    if not m:
        return None
    number = _norm(m.group(1))
    street_words = _norm(m.group(2)).split()[:3]
    if not number or not street_words:
        return None
    return re.compile(r"(?<![0-9])" + re.escape(number) + r"(?![0-9])[^,;|]{0,30}" + r"\s+".join(map(re.escape, street_words)))


def _get(url, timeout=20):
    global _last_call
    wait = DELAY_SECONDS - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "vi,en;q=0.8"})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _real_url(href):
    """Bing bọc link trong /ck/a?...&u=a1<base64>; giải ra link thật."""
    href = html.unescape(href)
    if "bing.com/ck/a" in href:
        u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            try:
                b = u[2:]
                return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode("utf-8", "replace")
            except Exception:
                return ""
    return href


def _results(page_html):
    """-> list (url, tiêu đề, cả khối chữ) của các kết quả tìm kiếm."""
    out = []
    for block in re.findall(r'<li class="b_algo".*?</li>', page_html, re.S):
        h = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not h:
            continue
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h.group(2)))).strip()
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", block)))
        out.append((_real_url(h.group(1)), title, text))
    return out


def _find_company(address):
    """{mst: tên} của các công ty có địa chỉ đăng ký trùng số nhà + tên đường."""
    pat = _street_pattern(address)
    if not pat:
        return {}
    found, tried = {}, 0
    for url, title, text in _results(_get("https://www.bing.com/search?setlang=vi&cc=vn&q=" + urllib.parse.quote(f"{address} mst công ty"))):
        if not any(site in url for site in REGISTRY_SITES):
            continue
        m = re.match(r"\s*(\d{10}(?:-\d{3})?)\s*[-–]\s*(.+)", title)           # "2802835688 - Công Ty TNHH Queen Milk, Quận ..."
        if m:
            mst, name = m.group(1), m.group(2)
        else:                                                                       # "CÔNG TY TNHH QUEEN MILK - Mã số thuế 2802835688"
            m = re.match(r"\s*(.+?)\s*[-–]\s*(?:Mã số thuế|MST)\s*(\d{10}(?:-\d{3})?)", title, re.I)
            if not m:
                continue
            name, mst = m.group(1), m.group(2)
        name = _NAME_CUT.sub("", name.split(",")[0]).strip(" -–.,")
        if not _NAME.match(name) or mst in found:
            continue
        if pat.search(_norm(text)):                                                 # địa chỉ có sẵn trong đoạn trích
            found[mst] = name
        elif tried < MAX_DETAIL:
            tried += 1
            try:
                if pat.search(_norm(re.sub(r"<[^>]+>", " ", html.unescape(_get(url, 15))))):
                    found[mst] = name
            except Exception:
                continue
    return found


def lookup(address):
    """-> {"name", "mst", "confidence", "note"}; confidence rỗng nếu không dùng được."""
    empty = {"name": "", "mst": "", "confidence": "", "note": ""}
    key = _norm(address)
    if not key:
        return empty
    cache = _load_cache()
    if key in cache:
        return cache[key]
    try:
        found = _find_company(address)
    except Exception:
        return empty                              # lỗi mạng: không ghi cache để lần sau thử lại
    if len(found) == 1:
        (mst, name), = found.items()
        res = {"name": name, "mst": mst, "confidence": "Cao", "note": "Tra từ địa chỉ (cùng số nhà + tên đường)"}
    elif len(found) > 1:
        res = {"name": "", "mst": "", "confidence": "Nhiều công ty",
               "note": "Nhiều công ty cùng địa chỉ: " + "; ".join(f"{n} ({m})" for m, n in list(found.items())[:4])}
    else:
        res = empty
    cache[key] = res
    _save_cache()
    return res
