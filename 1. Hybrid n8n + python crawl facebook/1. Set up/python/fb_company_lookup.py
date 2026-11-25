"""
FB COMPANY LOOKUP - từ tên thương hiệu (vd NOVALAND) tra tên công ty chính thức + MST

Thứ tự tra:
  1. Website công ty theo tên miền email doanh nghiệp (tên pháp lý + MST thường nằm ở chân trang)
  2. Bing: "<thương hiệu> mã số thuế công ty", chỉ nhận kết quả của trang danh bạ doanh nghiệp có tiêu đề "MST - TÊN CÔNG TY"
     và tên chứa thương hiệu
  3. DuckDuckGo (cùng cách như Bing)
Bing và DuckDuckGo trả HTML thường, không cần chạy JavaScript. Google chặn truy cập tự động bằng captcha và masothue.com
chặn tìm kiếm trực tiếp, nên không dùng được.
Chỉ gửi tên thương hiệu / tên miền ra ngoài, không gửi email, SĐT hay nội dung bài.
Kết quả (kể cả "không tìm thấy") nhớ trong 3. Reference\\mst_cache.json với khóa "brand:<tên>[@tên miền]".

Độ tin:
  "Từ website công ty"  tên pháp lý tìm thấy trên website của chính công ty
  "Khớp tên"            đúng một MST có tên chứa thương hiệu
  "Nhiều kết quả"       nhiều MST cùng chứa thương hiệu: lấy kết quả xếp đầu, liệt kê các kết quả còn lại để người xem chọn
  ""                    không tra được -> người gọi giữ nguyên tên thương hiệu làm tên công ty
"""

import html
import re
import time
import urllib.parse
import urllib.request

import fb_mst_lookup as mst

_TITLE = re.compile(r"\s*(\d{10}(?:-\d{3})?)\s*[-–]\s*(.+)")
_TITLE2 = re.compile(r"\s*(.+?)\s*[-–]\s*(?:Mã số thuế|MST)\s*(\d{10}(?:-\d{3})?)", re.I)
_CUT = re.compile(r"\s*[-–]\s*(?:MaSoThue|Mã số thuế|Masothue|Thông tin).*$", re.I)
_SITE_NAME = re.compile(r"((?:CÔNG TY|Công [Tt]y|CTY|Cty|TẬP ĐOÀN|Tập [Đđ]oàn|NGÂN HÀNG|Ngân [Hh]àng)\s+[^\n<>|©;:,.]{3,90})")
_SITE_CUT = re.compile(r"\s{2,}.*$|\s+(?:là|Xem|Trụ sở|Địa chỉ|xác định|chuyên|\(|-\s).*$")
_SITE_MST = re.compile(r"(?:MST|Mã số thuế|MSDN|Mã số doanh nghiệp)[^0-9]{0,25}(\d{10}(?:-\d{3})?)")


def _flat(s):
    return re.sub(r"[^a-z0-9]", "", mst._norm(s))


def _ddg_results(page_html):
    out = []
    for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page_html, re.S):
        href = html.unescape(m.group(1))
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [""])[0]
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        out.append((urllib.parse.unquote(q) or href, title, title))
    return out


def _candidates(brand, engine):
    q = urllib.parse.quote(f"{brand} mã số thuế công ty")
    if engine == "bing":
        results = mst._results(mst._get(f"https://www.bing.com/search?setlang=vi&cc=vn&q={q}"))
    else:
        results = _ddg_results(mst._get(f"https://html.duckduckgo.com/html/?q={q}"))
    found = {}
    for url, title, _ in results:
        if not any(site in url for site in mst.REGISTRY_SITES):
            continue
        m = _TITLE.match(title)
        if m:
            code, name = m.group(1), m.group(2)
        else:
            m = _TITLE2.match(title)
            if not m:
                continue
            name, code = m.group(1), m.group(2)
        name = _CUT.sub("", name.split(",")[0]).strip(" -–.,")
        if mst._NAME.match(name) and code not in found:
            found[code] = name
    return found


def _from_website(brand, domain):
    """Tên pháp lý (+ MST) lấy từ website công ty: chỉ nhận tên chứa phần đầu tên miền hoặc thương hiệu."""
    if not domain:
        return None
    text = ""
    for u in (f"https://{domain}", f"https://www.{domain}"):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": mst._UA}), timeout=10).read(400000).decode("utf-8", "replace")
            text = html.unescape(re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I))
            text = re.sub(r"<[^>]+>", " ", text)
            break
        except Exception:
            continue
    if not text:
        return None
    stem = re.sub(r"[^a-z0-9]", "", domain.split(".")[0].lower())
    keys = {k for k in (stem, _flat(brand), re.sub(r"(group|corp|holdings?|vn|jsc)$", "", stem)) if len(k) >= 4}
    names = [_SITE_CUT.sub("", n).strip(" -–.,") for n in _SITE_NAME.findall(text)]
    names = [n for n in names if len(n) > 10 and any(k in _flat(n) for k in keys)]
    if not names:
        return None
    best = max(set(names), key=lambda n: (names.count(n), -len(n)))
    code = _SITE_MST.search(text)
    return {"name": best, "mst": code.group(1) if code else "", "confidence": "Từ website công ty", "note": "Website " + domain}


def cache_key(brand, domain=""):
    return "brand:" + _flat(brand) + ("@" + domain if domain else "")


def cached(brand, domain=""):
    return mst._load_cache().get(cache_key(brand, domain))


def resolve(brand, domain=""):
    """-> {"name", "mst", "confidence", "note"}; name rỗng nếu không tra được. domain: tên miền email doanh nghiệp (nếu có)."""
    empty = {"name": "", "mst": "", "confidence": "", "note": ""}
    if len(_flat(brand)) < 3:
        return empty
    cache = mst._load_cache()
    key = cache_key(brand, domain)
    if key in cache:
        return cache[key]
    res = _from_website(brand, domain)
    if not res:
        hits = {}
        try:
            for engine in ("bing", "ddg"):
                hits = {c: n for c, n in _candidates(brand, engine).items() if _flat(brand) in _flat(n)}
                if hits:
                    break
        except Exception:
            return empty                              # lỗi mạng: không ghi cache để lần sau thử lại
        if len(hits) == 1:
            (code, name), = hits.items()
            res = {"name": name, "mst": code, "confidence": "Khớp tên", "note": ""}
        elif hits:
            items = list(hits.items())
            res = {"name": items[0][1], "mst": items[0][0], "confidence": "Nhiều kết quả",
                   "note": "Cũng khớp: " + "; ".join(f"{n} ({c})" for c, n in items[1:4])}
        else:
            res = empty
    cache[key] = res
    mst._save_cache()
    return res


def resolve_many(pairs, max_seconds=600):
    """Tra lần lượt các (thương hiệu, tên miền) chưa có trong cache, dừng khi hết max_seconds (lần sau tra tiếp). -> số lượt đã tra."""
    t0, done = time.time(), 0
    for brand, domain in pairs:
        if time.time() - t0 > max_seconds:
            break
        if cached(brand, domain) is None:
            resolve(brand, domain)
            done += 1
    return done


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for b in sys.argv[1:]:
        brand, _, domain = b.partition("@")
        print(b, "->", resolve(brand, domain))
