"""
FB CLUSTER - gom các dòng lead Facebook thành CỤM nhà tuyển dụng, bổ sung dần thông tin và xét trạng thái xác thực

Đầu vào : tất cả 2. Output\\fb_leads\\fb_leads_*.csv (kho đã crawl)
Đầu ra  : 2. Output\\fb_master\\fb_master.csv  (mỗi dòng = một cụm: tên công ty + email + SĐT)

Cách gom: hai dòng thuộc cùng cụm nếu trùng một trong các khóa
  - email, SĐT (bỏ qua SĐT khi bài có hơn MAX_PHONES_LINK số: tin tổng hợp/môi giới, nối sẽ gộp nhầm nhiều công ty),
  - tên công ty (đã chuẩn hóa), tên miền email doanh nghiệp (không tính gmail/yahoo...), nội dung bài giống hệt.
Mỗi lần chạy tính lại từ toàn bộ kho nên thông tin được bổ sung dần: lần 1 chỉ có SĐT, lần 2 ra email cùng cụm thì cụm có cả hai.

Tên công ty: tên thương hiệu cũng được tính là tên công ty. Có tên thương hiệu thì tra tên đăng ký (website công ty, Bing,
DuckDuckGo - fb_company_lookup.py); tra được thì dùng tên đăng ký, không thì giữ tên thương hiệu. Cột "Độ tin tên công ty" cho biết
tên đến từ đâu để người xem biết cái nào nên kiểm lại.

Trạng thái (luôn cần tên công ty):
  "Verified đủ 3/3"  có tên công ty + email + SĐT
  "Verified 2/3"     có tên công ty + (email hoặc SĐT)
  "Cần check"        còn lại (ghi rõ thiếu gì ở cột "Cần bổ sung")

Chạy: python fb_cluster.py    (run_fb_parallel.ps1 gọi sau mỗi lượt crawl)
Hàm classify_new() được fb_transform.write_csv dùng để KHÔNG bỏ bài đã có liên hệ mà giữ lại nếu bài bổ sung thêm thông tin.
"""

import csv
import glob
import hashlib
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import fb_company_lookup
import fb_mst_lookup

WORK_DIR = Path(__file__).parent
LEADS_DIR = WORK_DIR.parent.parent / "2. Output" / "fb_leads"
MASTER_DIR = WORK_DIR.parent.parent / "2. Output" / "fb_master"
MASTER_FILE = MASTER_DIR / "fb_master.csv"

MAX_PHONES_LINK = 3          # bài có nhiều hơn số này SĐT thì không dùng SĐT để nối cụm
LOOKUP_SECONDS = 600         # thời gian tối đa mỗi lần chạy để tra tên đăng ký (cái chưa tra xong sẽ tra tiếp lần sau)
FREE_DOMAINS = {"gmail.com", "yahoo.com", "yahoo.com.vn", "hotmail.com", "outlook.com", "icloud.com", "live.com",
                "outlook.com.vn", "gmail.com.vn", "googlemail.com", "msn.com", "me.com", "protonmail.com", "qq.com", "163.com"}
_BAD_NAMES = {"cần", "tuyển", "cần tuyển", "tuyển gấp", "tuyển dụng", "gấp", "hot", "hot job", "việc làm", "nhân sự"}
_COMPANY_WORDS = re.compile(r"\b(cong ty|tnhh|co phan|cp|mtv|tm|dv|sx|cty|chi nhanh|van phong|group|jsc|ltd)\b")
# Dấu hiệu một chuỗi KHÔNG phải tên công ty (đã bỏ dấu): chức danh, lời rao tuyển, thông tin liên hệ, địa danh, từ chung chung
_JOB_WORDS = re.compile(r"(truong|nhan vien|chuyen vien|giam doc|tuyen|quan ly|ky su|lap trinh|thuc tap|ke toan|phu trach|cong tac|nhan su|vi tri|^cac |yeu cau|muc luong|quyen loi|mo ta)")
_CONTACT_WORDS = re.compile(r"(zalo|hotline|lien he|\bcall\b|\bsdt\b|email|\d{6,})")
_PLACE_WORDS = re.compile(r"\b(ha noi|ho chi minh|hcm|sai gon|da nang|hai phong|can tho|binh duong|dong nai|vung tau|bac ninh|hai duong|thai nguyen|quang ninh|long an|long bien|dak lak|dak nong|tan phu|thu duc|binh thanh|go vap|tan binh|phu nhuan|cau giay|dong da|ba dinh|hoang mai|thanh xuan|khanh hoa|nghe an|thanh hoa|ha nam|ninh thuan|quang binh|quang tri|phu tho|hau giang|tien giang|ba ria|lam dong|mien bac|mien nam|mien trung|kcn|khu vuc|kv)\b")
_GENERIC_NAMES = {"thu nhap", "chung minh", "nha minh", "co nhu cau", "hien", "nao dang", "urgent", "luong", "quyen loi", "dia diem", "ung vien"}
_ORG_WORDS = re.compile(r"\b(cong ty|tnhh|co phan|cty|tap doan|jsc|ltd|group|corp|bank|ngan hang|trung tam|truong (?:dai hoc|mam non|tieu hoc|thcs|thpt|quoc te|cao dang|trung cap)|nha hang|hotel|khach san|spa|store|shop|studio|agency|chi nhanh)\b")

SRC_ORG, SRC_DOMAIN, SRC_CRM, SRC_BRAND = "Có loại hình công ty", "Khớp tên miền email", "Khớp MST/CRM", "Thương hiệu"
SRC_LOOKED_UP = "Tên đăng ký (tra website/MST)"
SRC_ADDRESS = "Tên đăng ký (tra từ địa chỉ)"

MASTER_COLUMNS = ["Cụm ID", "Trạng thái", "Cần bổ sung", "Tên công ty", "Tên thương hiệu (từ bài)", "Độ tin tên công ty", "Email", "SĐT",
                  "Số bài", "Số lần crawl", "Lần đầu thấy", "Lần cuối thấy", "Vị trí tuyển", "Ngành", "Tỉnh/Thành", "Địa chỉ", "MST",
                  "Group", "Link bài đầu", "Link bài cuối", "Ghi chú"]


def _strip(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D").lower()


def _emails(r):
    return [e.strip().lower() for e in re.split(r"[,;\s]+", r.get("Email", "")) if "@" in e]


def _phones(r):
    out = []
    for p in re.split(r"[,;]", r.get("SĐT", "")):
        p = re.sub(r"\D", "", p)
        if p.startswith("84") and len(p) == 11:
            p = "0" + p[2:]
        if len(p) in (10, 11) and p.startswith("0") and p not in out:
            out.append(p)
    return out


def _corp_domains(emails):
    return [e.split("@")[1] for e in emails if e.split("@")[1] not in FREE_DOMAINS]


def _name_source(r, emails):
    """Nguồn/độ tin của tên công ty trong một dòng.
    -> SRC_CRM | SRC_ORG | SRC_DOMAIN | SRC_BRAND (đều tính là có tên công ty)
       ""  (rõ ràng không phải tên công ty: chức danh, lời rao, thông tin liên hệ, địa danh, từ chung chung)"""
    name = r.get("Tên công ty", "").strip()
    n = _strip(name).strip(" -:|.!")
    if not n or n in {_strip(x) for x in _BAD_NAMES} or _CONTACT_WORDS.search(n):
        return ""
    if r.get("MST", "").strip() or r.get("Tên trong CRM", "").strip():
        return SRC_CRM
    has_org = bool(_ORG_WORDS.search(n))
    if not has_org and (_JOB_WORDS.search(n) or _PLACE_WORDS.search(n) or n in _GENERIC_NAMES):
        return ""
    flat = re.sub(r"[^a-z0-9]", "", n)
    stems = [re.sub(r"[^a-z0-9]", "", d.split(".")[0]) for d in _corp_domains(emails)]
    if any(len(s) > 3 and (flat == s or flat.startswith(s) or s.startswith(flat)) for s in stems):
        return SRC_DOMAIN
    if has_org:
        return SRC_ORG
    if name == name.lower() or len(flat) < 3:             # cụm viết thường toàn bộ ("có nhu cầu", "hiện") là câu bị bóc nhầm
        return ""
    return SRC_BRAND


def _company_key(name):
    n = _strip(name)
    if n.strip() in {_strip(x) for x in _BAD_NAMES}:
        return ""
    n = re.sub(r"[^a-z0-9]+", " ", _COMPANY_WORDS.sub(" ", n)).strip()
    return n if len(n) >= 4 else ""


def _body_hash(r):
    """Hash nội dung bài (bỏ phần liên hệ) để nhận ra cùng một tin đăng lại với thông tin liên hệ khác."""
    t = _strip(r.get("Nội dung bài viết", ""))
    t = re.sub(r"(email|zalo|sdt|hotline|lien he|phone)[^\n]*", " ", t)
    words = re.sub(r"[^a-z]+", " ", t).split()
    words = words[8:] if len(words) > 30 else words          # bỏ phần đầu bài (tên group, tên người đăng)
    return hashlib.md5(" ".join(words).encode()).hexdigest() if len(words) >= 25 else ""


def load_rows(folder=None):
    rows = []
    for f in sorted(glob.glob(str(Path(folder or LEADS_DIR) / "fb_leads_*.csv"))):
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                r["_file"] = Path(f).name
                rows.append(r)
    rows.sort(key=lambda r: (r.get("Thời gian crawl") or "", r["_file"]))
    return rows


def prepare(rows):
    """Thêm các trường tính sẵn (_em, _ph, _src...) vào từng dòng."""
    for r in rows:
        r["_em"], r["_ph"] = _emails(r), _phones(r)
        r["_many_ph"] = len(r["_ph"]) > MAX_PHONES_LINK
        r["_src"] = _name_source(r, r["_em"])
    return rows


def build_clusters(rows):
    prepare(rows)
    parent = list(range(len(rows)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    keys = defaultdict(list)
    for i, r in enumerate(rows):
        for e in r["_em"]:
            keys["e:" + e].append(i)
        for d in _corp_domains(r["_em"]):
            keys["d:" + d].append(i)
        if not r["_many_ph"]:
            for p in r["_ph"]:
                keys["p:" + p].append(i)
        if r["_src"] and _company_key(r["Tên công ty"]):
            keys["c:" + _company_key(r["Tên công ty"])].append(i)
        if _body_hash(r):
            keys["b:" + _body_hash(r)].append(i)
    for members in keys.values():
        for j in members[1:]:
            parent[find(j)] = find(members[0])
    clusters = defaultdict(list)
    for i in range(len(rows)):
        clusters[find(i)].append(i)
    return list(clusters.values())


def classify_new(existing_rows, new_rows):
    """Với mỗi dòng mới (đã có các trường của CSV) trả về "Lead mới" | "Bổ sung" | "Trùng".
    Lead mới: chưa có cụm nào trong kho trùng khóa với dòng này.
    Bổ sung : thuộc cụm đã có nhưng thêm được email, SĐT hoặc tên công ty mà cụm chưa có.
    Trùng   : thuộc cụm đã có và không thêm gì mới -> chỉ loại này mới bị bỏ."""
    rows = list(existing_rows) + list(new_rows)
    for r in new_rows:
        r.setdefault("_file", "new")
    clusters = build_clusters(rows)
    owner = {}
    for k, members in enumerate(clusters):
        for i in members:
            owner[i] = k
    out = []
    for n, r in enumerate(new_rows):
        i = len(existing_rows) + n
        prev = [rows[j] for j in clusters[owner[i]] if j < i]
        if not prev:
            out.append("Lead mới")
            continue
        has_e, has_p = any(x["_em"] for x in prev), any(x["_ph"] for x in prev)
        known_e, known_p = {e for x in prev for e in x["_em"]}, {p for x in prev for p in x["_ph"]}
        adds = ((r["_em"] and not has_e) or (r["_ph"] and not has_p) or any(e not in known_e for e in r["_em"])
                or any(p not in known_p for p in r["_ph"]) or (r["_src"] and not any(x["_src"] for x in prev)))
        out.append("Bổ sung" if adds else "Trùng")
    return out


def _uniq(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def brand_candidates(rows, members):
    """(tên thương hiệu, tên miền email doanh nghiệp) cần tra tên đăng ký cho một cụm; None nếu không cần."""
    rs = [rows[i] for i in members]
    named = [r for r in rs if r["_src"] in (SRC_DOMAIN, SRC_BRAND)]
    if not named or any(r["_src"] in (SRC_ORG, SRC_CRM) for r in rs):
        return None
    brand = Counter(r["Tên công ty"].strip() for r in named).most_common(1)[0][0]
    domains = _uniq(d for r in rs for d in _corp_domains(r["_em"]))
    return brand, domains[0] if domains else ""


def address_candidate(rows, members):
    """Địa chỉ cụ thể (có số nhà và dấu phẩy) của cụm chưa có tên công ty -> tra "địa chỉ + mst" (fb_mst_lookup); None nếu không áp dụng."""
    rs = [rows[i] for i in members]
    if any(r["_src"] for r in rs):
        return None
    for r in rs:
        a = r.get("Địa chỉ", "").strip()
        if a and re.search(r"\d", a) and "," in a:
            return a
    return None


def resolve_addresses(addresses, max_seconds):
    """Tra lần lượt các địa chỉ chưa có trong cache (fb_mst_lookup tự ghi cache), dừng khi hết max_seconds. -> số địa chỉ đã tra."""
    t0, done = time.time(), 0
    cache = fb_mst_lookup._load_cache()
    for a in addresses:
        if time.time() - t0 > max_seconds:
            break
        if fb_mst_lookup._norm(a) not in cache:
            fb_mst_lookup.lookup(a)
            done += 1
    return done


def summarize(rows, members, cid):
    rs = [rows[i] for i in members]
    named = [(r["Tên công ty"].strip(), r["_src"]) for r in rs if r["_src"] and _company_key(r.get("Tên công ty", ""))]
    order = (SRC_CRM, SRC_ORG, SRC_DOMAIN, SRC_BRAND)
    named.sort(key=lambda x: order.index(x[1]))
    brand = Counter(n for n, src in named if src == named[0][1]).most_common(1)[0][0] if named else ""
    name_src = named[0][1] if named else ""
    company, mst_code, note_lookup = brand, "", ""
    cand = brand_candidates(rows, members)
    if cand:
        found = fb_company_lookup.cached(*cand)
        if found and found["name"]:
            company, mst_code, name_src = found["name"], found["mst"], SRC_LOOKED_UP
            note_lookup = found["note"] or found["confidence"]
    addr = address_candidate(rows, members)
    if addr and not company:
        found = fb_mst_lookup._load_cache().get(fb_mst_lookup._norm(addr))
        if found and found.get("confidence") == "Cao":
            company, mst_code, name_src, note_lookup = found["name"], found["mst"], SRC_ADDRESS, "Tra từ địa chỉ (cùng số nhà + tên đường)"
        elif found and found.get("note"):
            note_lookup = found["note"]
    mst_code = mst_code or next((r["MST"].strip() for r in rs if r.get("MST", "").strip()), "")
    emails = _uniq(e for r in rs for e in r["_em"])
    phones = _uniq(p for r in rs for p in r["_ph"])
    many = any(r["_many_ph"] for r in rs)
    if company and emails and phones:
        status, missing = "Verified đủ 3/3", ""
    elif company and (emails or phones):
        status, missing = "Verified 2/3", "Thiếu SĐT" if emails else "Thiếu email"
    else:
        need = [x for x, ok in (("tên công ty", company), ("email", emails), ("SĐT", phones)) if not ok]
        status, missing = "Cần check", "Thiếu " + ", ".join(need)
    links = _uniq(r.get("Link bài viết", "") for r in rs)
    times = [r.get("Thời gian crawl", "") for r in rs if r.get("Thời gian crawl")]
    notes = []
    if name_src == SRC_BRAND:
        notes.append("Tên thương hiệu, chưa tra được tên đăng ký")
    if note_lookup:
        notes.append(note_lookup)
    if many:
        notes.append("Có bài đăng nhiều SĐT (nghi tin tổng hợp/môi giới)")
    if len(phones) > 8:
        notes.append("Cụm có nhiều SĐT, nên kiểm tra có gộp nhầm không")
    return {
        "Cụm ID": cid, "Trạng thái": status, "Cần bổ sung": missing, "Tên công ty": company,
        "Tên thương hiệu (từ bài)": brand if brand != company else "", "Độ tin tên công ty": name_src,
        "Email": "; ".join(emails), "SĐT": "; ".join(phones), "Số bài": len(links),
        "Số lần crawl": len({r["_file"][9:22] for r in rs}),
        "Lần đầu thấy": min(times)[:16] if times else "", "Lần cuối thấy": max(times)[:16] if times else "",
        "Vị trí tuyển": "; ".join(_uniq(r.get("Vị trí tuyển", "").strip() for r in rs)[:3]),
        "Ngành": "; ".join(_uniq(r.get("Ngành", "") for r in rs)[:2]),
        "Tỉnh/Thành": "; ".join(_uniq(r.get("Tỉnh/Thành", "") for r in rs)[:2]),
        "Địa chỉ": next((r["Địa chỉ"].strip() for r in rs if r.get("Địa chỉ", "").strip()), ""),
        "MST": mst_code,
        "Group": "; ".join(_uniq(r.get("Group", "") for r in rs)[:3]),
        "Link bài đầu": links[0] if links else "", "Link bài cuối": links[-1] if links else "",
        "Ghi chú": " | ".join(notes),
    }


def main(lookup_seconds=LOOKUP_SECONDS):
    rows = load_rows()
    if not rows:
        print("Chưa có dữ liệu trong", LEADS_DIR)
        return
    clusters = build_clusters(rows)
    pending = [c for c in (brand_candidates(rows, m) for m in clusters) if c]
    tra = fb_company_lookup.resolve_many(pending, max_seconds=lookup_seconds) if lookup_seconds else 0
    addrs = [a for a in (address_candidate(rows, m) for m in clusters) if a]
    tra_dc = resolve_addresses(addrs, lookup_seconds) if lookup_seconds else 0
    # ID cụm lấy từ bài đầu tiên của cụm nên giữ nguyên giữa các lần chạy
    out = [summarize(rows, m, "C" + hashlib.md5(rows[min(m)].get("Link bài viết", str(min(m))).encode()).hexdigest()[:8]) for m in clusters]
    order = {"Verified đủ 3/3": 0, "Verified 2/3": 1, "Cần check": 2}
    out.sort(key=lambda d: d["Lần cuối thấy"], reverse=True)
    out.sort(key=lambda d: order[d["Trạng thái"]])
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    with open(MASTER_FILE, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MASTER_COLUMNS)
        w.writeheader()
        w.writerows(out)
    c = Counter(d["Trạng thái"] for d in out)
    src = Counter(d["Độ tin tên công ty"] for d in out)
    print(f"Kho {len(rows)} dòng -> {len(out)} cụm | Verified đủ 3/3: {c['Verified đủ 3/3']} | Verified 2/3: {c['Verified 2/3']} | "
          f"Cần check: {c['Cần check']} | tra tên đăng ký lần này: {tra}/{len(pending)} thương hiệu, {tra_dc}/{len(addrs)} địa chỉ | nguồn tên: {dict(src)} -> {MASTER_FILE}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(int(sys.argv[1]) if len(sys.argv) > 1 else LOOKUP_SECONDS)
