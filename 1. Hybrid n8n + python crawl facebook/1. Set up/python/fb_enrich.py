"""
FB ENRICH - tách thêm dữ liệu có cấu trúc + chấm điểm lead (bằng quy tắc, chạy cục bộ, không gọi dịch vụ ngoài)

Đầu vào : dict đã qua fb_transform.transform_post (tenCongTy, diaChi, email, phone, text, ...)
Đầu ra  : dict các cột bổ sung đặt SAU 9 cột gốc trong CSV

Tất cả là suy đoán bằng từ khóa: dùng để lọc/thống kê, không thay cho việc đọc bài gốc khi cần chắc chắn.
"""

import re
from datetime import date

_I = re.I
_A = re.A

EXTRA_COLUMNS = [
    "Tỉnh/Thành", "Ngành", "Vị trí tuyển", "Lương", "Lương min (triệu)", "Lương max (triệu)",
    "Kinh nghiệm", "Loại email", "Điểm lead", "Ghi chú lead", "Bài cũ",
]

OLD_POST_DAYS = 7
_RE_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_RE_VN_DATE = re.compile(r"^(\d{1,2})\s+Tháng\s+(\d{1,2})", _I)


def is_old_post(rec):
    """'Có' nếu bài đăng cách ngày crawl quá OLD_POST_DAYS ngày; để trống nếu mới hoặc không đọc được ngày."""
    try:
        crawl = date.fromisoformat((rec.get("scrapedAt") or "")[:10])
    except ValueError:
        crawl = date.today()
    s = (rec.get("ngayDang") or "").strip()
    try:
        m = _RE_ISO_DATE.match(s)
        if m:
            posted = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            m = _RE_VN_DATE.match(s)
            if not m:
                return ""
            posted = date(crawl.year, int(m.group(2)), int(m.group(1)))
            if posted > crawl:
                posted = date(crawl.year - 1, posted.month, posted.day)
    except ValueError:
        return ""
    return "Có" if (crawl - posted).days > OLD_POST_DAYS else ""

# ========================================
# TỈNH / THÀNH (63 tỉnh cũ, cùng danh sách với hệ thống crawl CV)
# ========================================

_HN_D = ["cầu giấy", "đống đa", "hoàng mai", "thanh xuân", "nam từ liêm", "bắc từ liêm", "hà đông",
         "long biên", "ba đình", "hai bà trưng", "tây hồ", "hoàn kiếm", "thanh trì", "gia lâm",
         "đông anh", "thạch thất", "mỹ đình", "hoàng quốc việt", "nguyễn trãi", "lê văn lương",
         "trần duy hưng", "xuân thủy", "cầu diễn", "nguyễn xiển", "lê đức thọ", "phạm văn đồng",
         "khuất duy tiến", "hoài đức", "mê linh", "sóc sơn", "quốc oai"]
_HCM_D = ["thủ đức", "tân bình", "tân phú", "bình thạnh", "gò vấp", "phú nhuận", "bình tân", "nhà bè",
          "củ chi", "hóc môn", "bình chánh", "sài gòn", "quận 1", "quận 2", "quận 3", "quận 4",
          "quận 5", "quận 6", "quận 7", "quận 8", "quận 9", "quận 10", "quận 11", "quận 12"]

_PROVINCES = {
    "TP. Hồ Chí Minh": ["hồ chí minh", "tphcm", "tp.hcm", "tp. hcm", "tp hcm", "hcmc"] + _HCM_D,
    "Hà Nội": ["hà nội", "hanoi"] + _HN_D,
    "Đà Nẵng": ["đà nẵng", "hải châu", "thanh khê", "sơn trà", "ngũ hành sơn", "liên chiểu", "cẩm lệ"],
    "Hải Phòng": ["hải phòng"], "Cần Thơ": ["cần thơ", "ninh kiều"], "Bình Dương": ["bình dương", "thuận an", "dĩ an", "thủ dầu một", "bến cát", "tân uyên"],
    "Đồng Nai": ["đồng nai", "biên hòa", "long thành", "nhơn trạch"], "Long An": ["long an"],
    "Bà Rịa - Vũng Tàu": ["vũng tàu", "bà rịa"], "Bắc Ninh": ["bắc ninh"], "Bắc Giang": ["bắc giang"],
    "Hải Dương": ["hải dương"], "Hưng Yên": ["hưng yên"], "Vĩnh Phúc": ["vĩnh phúc", "vĩnh yên"],
    "Thái Nguyên": ["thái nguyên"], "Quảng Ninh": ["quảng ninh", "hạ long", "cẩm phả", "móng cái"],
    "Nam Định": ["nam định"], "Thái Bình": ["thái bình"], "Ninh Bình": ["ninh bình"], "Hà Nam": ["hà nam", "phủ lý"],
    "Thanh Hóa": ["thanh hóa"], "Nghệ An": ["nghệ an", "vinh"], "Hà Tĩnh": ["hà tĩnh"],
    "Quảng Bình": ["quảng bình", "đồng hới"], "Quảng Trị": ["quảng trị"], "Thừa Thiên Huế": ["huế"],
    "Quảng Nam": ["quảng nam", "hội an", "tam kỳ"], "Quảng Ngãi": ["quảng ngãi"], "Bình Định": ["bình định", "quy nhơn"],
    "Phú Yên": ["phú yên", "tuy hòa"], "Khánh Hòa": ["khánh hòa", "nha trang", "cam ranh"], "Ninh Thuận": ["ninh thuận"],
    "Bình Thuận": ["bình thuận", "phan thiết"], "Lâm Đồng": ["lâm đồng", "đà lạt", "bảo lộc"],
    "Đắk Lắk": ["đắk lắk", "đăk lăk", "buôn ma thuột"], "Gia Lai": ["gia lai", "pleiku"], "Kon Tum": ["kon tum"],
    "Đắk Nông": ["đắk nông"], "Bình Phước": ["bình phước"], "Tây Ninh": ["tây ninh"],
    "Tiền Giang": ["tiền giang", "mỹ tho"], "Bến Tre": ["bến tre"], "Vĩnh Long": ["vĩnh long"],
    "Đồng Tháp": ["đồng tháp", "cao lãnh"], "An Giang": ["an giang", "long xuyên"], "Kiên Giang": ["kiên giang", "rạch giá", "phú quốc"],
    "Cà Mau": ["cà mau"], "Bạc Liêu": ["bạc liêu"], "Sóc Trăng": ["sóc trăng"], "Hậu Giang": ["hậu giang"],
    "Trà Vinh": ["trà vinh"], "Lào Cai": ["lào cai"], "Yên Bái": ["yên bái"], "Phú Thọ": ["phú thọ", "việt trì"],
    "Tuyên Quang": ["tuyên quang"], "Lạng Sơn": ["lạng sơn"], "Cao Bằng": ["cao bằng"], "Sơn La": ["sơn la"],
    "Điện Biên": ["điện biên"], "Hòa Bình": ["hòa bình"],
}
_PLACE_NAMES = {p.lower() for p in _PROVINCES} | {a for al in _PROVINCES.values() for a in al}


def is_place_name(name):
    """True nếu cả chuỗi chỉ là tên tỉnh/quận (n8n đôi khi bóc nhầm địa danh thành tên công ty)."""
    return (name or "").strip(" []()-–.,").lower() in _PLACE_NAMES


# Viết tắt ngắn, chỉ khớp khi đứng riêng (ASCII)
_ABBR = [(re.compile(r"(?<![A-Za-z0-9])hcm(?![A-Za-z0-9])", _I), "TP. Hồ Chí Minh"),
         (re.compile(r"(?<![A-Za-z0-9])sg(?![A-Za-z0-9])", _I), "TP. Hồ Chí Minh"),
         (re.compile(r"(?<![A-Za-z0-9])q\.?\s?(?:[1-9]|1[0-2])(?![0-9])", _I), "TP. Hồ Chí Minh"),
         (re.compile(r"(?<![A-Za-z0-9])hn(?![A-Za-z0-9])", _I), "Hà Nội")]


def extract_province(*texts):
    """Lấy tỉnh xuất hiện sớm nhất trong chuỗi đầu tiên có địa danh."""
    for text in texts:
        if not text:
            continue
        low = text.lower()
        best = (10 ** 9, "")
        for prov, aliases in _PROVINCES.items():
            for a in aliases:
                i = low.find(a)
                # "vinh", "huế": phải đứng riêng để tránh khớp nhầm trong từ khác
                if i >= 0 and a in ("vinh", "huế") and re.search(r"[a-zà-ỹ]", low[max(i - 1, 0):i] + low[i + len(a):i + len(a) + 1]):
                    i = -1
                if 0 <= i < best[0]:
                    best = (i, prov)
        for rx, prov in _ABBR:
            m = rx.search(text)
            if m and m.start() < best[0]:
                best = (m.start(), prov)
        if best[1]:
            return best[1]
    return ""


# ========================================
# NGÀNH (nhóm lớn, theo từ khóa ở phần đầu bài)
# ========================================

_INDUSTRY = [
    ("Kế toán / Kiểm toán", [r"kế toán", r"kiểm toán", r"\bkt\s*tổng\s*hợp"]),
    ("Nhân sự", [r"nhân sự", r"hcns", r"(?<![a-z])hr(?![a-z])", r"recruiter", r"c&b", r"headhunt", r"tuyển dụng viên", r"chuyên viên tuyển dụng"]),
    ("Hành chính / Văn phòng", [r"hành chính", r"lễ tân", r"thư ký", r"trợ lý", r"nhập liệu", r"văn thư"]),
    ("Kinh doanh / Bán hàng", [r"kinh doanh", r"(?<![a-z])sales?(?![a-z])", r"bán hàng", r"telesale", r"tư vấn viên", r"business development", r"(?<![a-z])bd(?![a-z])", r"account", r"bán lẻ", r"cửa hàng", r"thị trường"]),
    ("Marketing / Truyền thông", [r"marketing", r"(?<![a-z])mkt(?![a-z])", r"(?<![a-z])seo(?![a-z])", r"content", r"quảng cáo", r"truyền thông", r"social media", r"fanpage", r"digital", r"tiktok", r"(?<![a-z])kol(?![a-z])", r"booking", r"(?<![a-z])pr(?![a-z])"]),
    ("Thiết kế / Sáng tạo", [r"thiết kế", r"designer", r"đồ họa", r"graphic", r"video", r"editor", r"dựng phim", r"quay phim", r"photograph", r"ui/ux", r"(?<![a-z])mc(?![a-z])"]),
    ("CNTT / Lập trình", [r"lập trình", r"developer", r"(?<![a-z])dev(?![a-z])", r"software", r"(?<![a-z])it(?![a-z])", r"phần mềm", r"tester", r"(?<![a-z])qa(?![a-z/])", r"devops", r"backend", r"frontend", r"fullstack", r"java", r"(?<![a-z])php(?![a-z])", r"\.net", r"python", r"react", r"android", r"(?<![a-z])ios(?![a-z])", r"helpdesk", r"an ninh mạng", r"data analyst", r"(?<![a-z])ai(?![a-z])", r"sysadmin"]),
    ("Tài chính / Ngân hàng / Bảo hiểm", [r"ngân hàng", r"tín dụng", r"bảo hiểm", r"tài chính", r"chứng khoán", r"cho vay", r"thu hồi nợ", r"thẩm định"]),
    ("Chăm sóc khách hàng", [r"chăm sóc khách hàng", r"cskh", r"tổng đài", r"customer service", r"call center", r"hỗ trợ khách hàng", r"(?<![a-z])cs(?![a-z])"]),
    ("Logistics / Xuất nhập khẩu", [r"logistics", r"xuất nhập khẩu", r"(?<![a-z])xnk(?![a-z])", r"kho vận", r"nhân viên kho", r"vận chuyển", r"giao hàng", r"shipper", r"tài xế", r"lái xe", r"điều phối", r"forwarder", r"chứng từ", r"hải quan", r"supply chain", r"mua hàng", r"purchasing", r"thu mua"]),
    ("Sản xuất / Kỹ thuật", [r"sản xuất", r"kỹ thuật", r"cơ khí", r"công nhân", r"vận hành", r"bảo trì", r"(?<![a-z])qc(?![a-z])", r"(?<![a-z])kcs(?![a-z])", r"cơ điện", r"kỹ sư", r"chất lượng", r"xưởng", r"may mặc", r"điện lạnh", r"cnc"]),
    ("Xây dựng / Bất động sản", [r"xây dựng", r"kiến trúc", r"giám sát công trình", r"dự toán", r"bất động sản", r"(?<![a-z])bđs(?![a-z])", r"(?<![a-z])bds(?![a-z])", r"môi giới", r"nội thất", r"autocad", r"thi công"]),
    ("Nhà hàng / Khách sạn / Du lịch", [r"nhà hàng", r"khách sạn", r"(?<![a-z])bếp(?![a-z])", r"phục vụ", r"pha chế", r"barista", r"du lịch", r"lữ hành", r"hướng dẫn viên", r"f&b", r"(?<![a-z])spa(?![a-z])", r"housekeeping", r"buồng phòng", r"homestay", r"pizza", r"cafe", r"coffee", r"cà phê", r"trà sữa", r"quán"]),
    ("Giáo dục / Đào tạo", [r"giáo viên", r"giảng viên", r"gia sư", r"đào tạo", r"trợ giảng", r"giáo dục", r"tiếng anh", r"trung tâm anh ngữ"]),
    ("Y tế / Dược", [r"y tế", r"dược", r"điều dưỡng", r"bác sĩ", r"phòng khám", r"nha khoa", r"bệnh viện"]),
    ("Pháp lý", [r"pháp chế", r"pháp lý", r"luật sư", r"(?<![a-z])luật(?![a-z])"]),
]
_INDUSTRY_RX = [(name, [re.compile(p, _I) for p in pats]) for name, pats in _INDUSTRY]


def extract_industry(position, text):
    """Ưu tiên vị trí tuyển và 300 ký tự đầu (tiêu đề); toàn bài chỉ làm phụ."""
    head = ((position or "") + " \n" + (text or "")[:300])
    body = (text or "")[300:1500]
    best, best_score = "", 0
    for name, rxs in _INDUSTRY_RX:
        score = sum(3 * len(rx.findall(head)) + len(rx.findall(body)) for rx in rxs)
        if score > best_score:
            best, best_score = name, score
    return best if best_score >= 3 else ("Khác" if (text or "").strip() else "")


# ========================================
# VỊ TRÍ TUYỂN
# ========================================

_RE_POS_LABEL = re.compile(r"vị\s*trí(?:\s*tuyển(?:\s*dụng)?)?\s*[:\-]\s*([^\n]{3,80})", _I)
_RE_POS_TUYEN = re.compile(r"(?:cần\s+tuyển(?:\s+dụng)?|đang\s+tuyển(?:\s+dụng)?|tuyển\s+dụng|tuyển\s+gấp|tuyển)\s*[:\-]?\s*(?:gấp\s*[:\-]?\s*)?(?:[0-9]+\s*(?:bạn|nhân\s*viên|vị\s*trí)\s*)?([^\n]{3,100})", _I)
_RE_POS_GENERIC = re.compile(r"(?:các|nhiều|những)\s+vị\s*trí|vị\s*trí\s+sau|như\s+sau|sau\s+đây|^(?:nhân\s*viên\s*)?(?:cho|các|nhiều|một)\b", _I)
_RE_POS_CUT = re.compile(r"\s+[-–—|]\s+|\s*[(\[|•]|\s+tại\s+|\s+khu\s*vực\s+|\s+làm\s*việc\s+|\s+lương\s|\s+thu\s*nhập\s|\s+ở\s+", _I)


def extract_position(text):
    if not text:
        return ""
    m = _RE_POS_LABEL.search(text)
    cands = [m.group(1)] if m else []
    for line in [l for l in (x.strip() for x in text.split("\n")) if l][:3]:
        line = re.sub(r"^\[[^\]]*\]\s*", "", line)
        t = _RE_POS_TUYEN.search(line)
        if t:
            cands.append(t.group(1))
    for c in cands:
        c = re.sub(r"^vị\s*trí\s*[:\-]?\s*", "", c.strip(), flags=_I)
        c = _RE_POS_CUT.split(c)[0].strip(" :-–—•*#.,!")
        if 2 < len(c) <= 60 and "@" not in c and not _RE_POS_GENERIC.search(c):
            return c
    return ""


# ========================================
# LƯƠNG
# ========================================

_NUM = r"([0-9]+(?:[.,][0-9]+)?)"
_UNIT = r"(?:tr|triệu|trieu|m|củ|million)(?![a-zà-ỹ])"
_RE_SAL_RANGE = re.compile(_NUM + r"\s*(?:" + _UNIT + r")?\s*(?:-|–|—|~|đến|tới)\s*" + _NUM + r"\s*" + _UNIT, _I)
_RE_SAL_UPTO = re.compile(r"(?:up\s*to|lên\s*đến|lên\s*tới|tối\s*đa|đến|tới)\s*" + _NUM + r"\s*" + _UNIT, _I)
_RE_SAL_FROM = re.compile(r"(?:từ|trên|>=|≥|min)\s*" + _NUM + r"\s*" + _UNIT, _I)
_RE_SAL_ONE = re.compile(_NUM + r"\s*" + _UNIT, _I)
_RE_SAL_VND = re.compile(r"([0-9]{1,3}(?:[.,][0-9]{3}){2,})\s*(?:-|–|—|~|đến|tới)?\s*([0-9]{1,3}(?:[.,][0-9]{3}){2,})?", _I)
_RE_SAL_USD = re.compile(r"(?:\$\s*([0-9][0-9.,]*)|([0-9][0-9.,]*)\s*(?:usd|\$))", _I)
_RE_SAL_KW = re.compile(r"lương|thu\s*nhập|salary|income|mức\s*(?:thu|lương)", _I)
_RE_SAL_NEG = re.compile(r"thỏa\s*thuận|thoả\s*thuận|thương\s*lượng|cạnh\s*tranh|negotiable", _I)


def _f(x):
    return float(x.replace(",", ".")) if x else None


def _fmt(v):
    return ("%g" % v) if v is not None else ""


def extract_salary(text):
    """-> (chuỗi lương, min triệu, max triệu). Chỉ đọc vùng gần từ 'lương/thu nhập' và phần đầu bài."""
    if not text:
        return "", None, None
    zones = [text[m.start(): m.start() + 90] for m in _RE_SAL_KW.finditer(text[:2500])][:4]
    zones.append(text[:250])
    for z in zones:
        m = _RE_SAL_RANGE.search(z)
        if m:
            lo, hi = _f(m.group(1)), _f(m.group(2))
            if lo is not None and hi is not None and lo <= hi and hi < 1000:
                return f"{_fmt(lo)}-{_fmt(hi)} triệu", lo, hi
        m = _RE_SAL_UPTO.search(z)
        if m and _f(m.group(1)) < 1000:
            return f"Đến {_fmt(_f(m.group(1)))} triệu", None, _f(m.group(1))
        m = _RE_SAL_FROM.search(z)
        if m and _f(m.group(1)) < 1000:
            return f"Từ {_fmt(_f(m.group(1)))} triệu", _f(m.group(1)), None
        m = _RE_SAL_VND.search(z)
        if m:
            lo = float(re.sub(r"[.,]", "", m.group(1))) / 1e6
            hi = float(re.sub(r"[.,]", "", m.group(2))) / 1e6 if m.group(2) else lo
            if 1 <= lo <= hi < 1000:
                return (f"{_fmt(lo)}-{_fmt(hi)} triệu" if hi != lo else f"{_fmt(lo)} triệu"), lo, hi
        if _RE_SAL_KW.search(z):
            m = _RE_SAL_ONE.search(z)
            if m and 1 <= _f(m.group(1)) < 1000:
                return f"{_fmt(_f(m.group(1)))} triệu", _f(m.group(1)), _f(m.group(1))
            m = _RE_SAL_USD.search(z)
            if m:
                return f"{(m.group(1) or m.group(2)).strip('.,')} USD", None, None
            if _RE_SAL_NEG.search(z):
                return "Thỏa thuận", None, None
    for z in zones:
        if _RE_SAL_NEG.search(z) and _RE_SAL_KW.search(z):
            return "Thỏa thuận", None, None
    return "", None, None


# ========================================
# KINH NGHIỆM
# ========================================

_RE_EXP_NONE = re.compile(r"không\s*(?:yêu\s*cầu|cần|đòi\s*hỏi)\s*(?:có\s*)?kinh\s*nghiệm|chưa\s*(?:có\s*)?kinh\s*nghiệm|fresher|mới\s*tốt\s*nghiệp|không\s*cần\s*kn|sẽ\s*được\s*đào\s*tạo", _I)
_RE_EXP_YEARS = re.compile(r"(?:kinh\s*nghiệm|(?<![a-zà-ỹ])kn(?![a-zà-ỹ]))[^\n]{0,40}?" + _NUM + r"(?:\s*(?:-|–|đến|tới)\s*" + _NUM + r")?\s*năm|" + _NUM + r"(?:\s*(?:-|–|đến|tới)\s*" + _NUM + r")?\s*năm\s*(?:kinh\s*nghiệm|(?<![a-zà-ỹ])kn(?![a-zà-ỹ])|làm)", _I)


def extract_experience(text):
    if not text:
        return ""
    t = text[:2500]
    m = _RE_EXP_YEARS.search(t)
    if m:
        g = m.groups()
        a, b = (g[0], g[1]) if g[0] else (g[2], g[3])
        if a:
            return f"{a}-{b} năm" if b else f"{a} năm"
    if _RE_EXP_NONE.search(t):
        return "Không yêu cầu"
    return ""


# ========================================
# CHẤT LƯỢNG LEAD
# ========================================

_PERSONAL = {"gmail", "yahoo", "hotmail", "outlook", "icloud", "live", "msn", "protonmail"}
_RE_AGENCY_TEXT = re.compile(
    r"headhunt|tuyển\s*dụng\s*(?:hộ|giúp|cho\s*(?:khách\s*hàng|đối\s*tác))|khách\s*hàng\s*của\s*(?:chúng\s*tôi|mình)|"
    r"đối\s*tác\s*(?:của\s*)?(?:chúng\s*tôi|mình)|recruitment\s*(?:agency|consult)|staffing|outsourc|"
    r"cung\s*ứng\s*nhân\s*(?:lực|sự)|(?:tư\s*vấn|dịch\s*vụ)\s*(?:tuyển\s*dụng|nhân\s*sự)", _I)
_RE_AGENCY_NAME = re.compile(
    r"nhân\s*lực|nguồn\s*nhân|manpower|headhunt|staffing|recruit|talent|hr\s*agent|hragent|nhân\s*sự\s*(?:tư\s*vấn|quốc)|"
    r"adecco|vietnamworks|careerlink|navigos|randstad|robert\s*walters|kellyservices", _I)


_RE_COMPANY = re.compile(
    r"((?<![a-zà-ỹ])(?:công\s*ty|cty|tập\s*đoàn|ngân\s*hàng|trung\s*tâm)\s+[^\n\-–—|()\[\]]{3,70}?)"
    r"(?=\s+(?:tuyển|cần\s+tuyển|đang\s+tuyển)|\s*[-–—|(\[:]|\n|\Z)", _I)


_NOT_NAME_START = {"làm", "về", "chuyên", "hoạt", "cung", "kinh", "đang", "có", "là", "tôi", "mình",
                   "bất", "tài", "xây", "sản", "thương"}


def company_fallback(text):
    """Tên công ty từ 2 dòng đầu khi bắt đầu bằng 'Công ty/Tập đoàn/Ngân hàng...' (n8n bỏ sót các bài này)."""
    lines = [l for l in (x.strip() for x in (text or "").split("\n")) if l][:2]
    for line in lines:
        line = re.sub(r"^\[[^\]]*\]\s*", "", line)
        m = _RE_COMPANY.search(line)
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).strip(" :-–—.,!")
            # ít nhất 5 từ và sau "Công ty" không phải động từ/mô tả: loại "Công ty tài chính", "CTY LÀM VỀ..."
            words = name.split(" ")
            rest = words[2:] if words[0].lower() in ("công", "tập") else words[1:]
            if (5 <= len(words) <= 9 and "@" not in name and rest
                    and rest[0].lower() not in _NOT_NAME_START):
                return name
    return ""


def email_type(email):
    first = (email or "").split(",")[0].strip()
    if "@" not in first:
        return ""
    dom = first.split("@")[1].split(".")[0].lower()
    return "Cá nhân" if dom in _PERSONAL else "Doanh nghiệp"


def score_lead(rec, extra):
    """Điểm 0-100 theo độ đầy đủ; kèm ghi chú các điểm cần lưu ý."""
    score, notes = 0, []
    if rec.get("tenCongTy"):
        score += 25
    else:
        notes.append("Thiếu tên công ty")
    et = extra["Loại email"]
    if et == "Doanh nghiệp":
        score += 20
    elif et == "Cá nhân":
        score += 8
        notes.append("Email cá nhân")
    if not rec.get("email"):
        notes.append("Chỉ có SĐT" if rec.get("phone") else "Không có email/SĐT")
    if rec.get("phone"):
        score += 15
    else:
        notes.append("Thiếu SĐT")
    if rec.get("diaChi"):
        score += 10
    if extra["Tỉnh/Thành"]:
        score += 10
    if extra["Ngành"] and extra["Ngành"] != "Khác":
        score += 8
    if extra["Vị trí tuyển"]:
        score += 7
    if extra["Lương"]:
        score += 5
    agency = bool(_RE_AGENCY_NAME.search(rec.get("tenCongTy") or "") or _RE_AGENCY_TEXT.search((rec.get("text") or "")[:1500]))
    if agency:
        score -= 20
        notes.append("Nghi tuyển dụng hộ / công ty nhân sự")
    return max(0, min(100, score)), "; ".join(notes)


def enrich(rec):
    """rec: dict từ fb_transform.transform_post. Trả về dict các cột bổ sung."""
    text = rec.get("text") or ""
    pos = extract_position(text)
    sal, lo, hi = extract_salary(text)
    extra = {
        "Tỉnh/Thành": extract_province(rec.get("diaChi"), text[:300]),
        "Ngành": extract_industry(pos, text),
        "Vị trí tuyển": pos,
        "Lương": sal,
        "Lương min (triệu)": _fmt(lo),
        "Lương max (triệu)": _fmt(hi),
        "Kinh nghiệm": extract_experience(text),
        "Loại email": email_type(rec.get("email")),
    }
    # Tên công ty bổ sung khi n8n/Python gốc không bóc được; dùng cả khi chấm điểm
    fallback = "" if rec.get("tenCongTy") else company_fallback(text)
    extra["_tenCongTy"] = fallback
    scored = dict(rec, tenCongTy=rec.get("tenCongTy") or fallback)
    extra["Điểm lead"], extra["Ghi chú lead"] = score_lead(scored, extra)
    extra["Bài cũ"] = is_old_post(rec)
    return extra
