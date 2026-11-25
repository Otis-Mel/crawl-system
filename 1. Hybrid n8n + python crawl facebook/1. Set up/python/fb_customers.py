"""
FB CUSTOMERS - đối chiếu tên công ty của lead với danh sách công ty đã có trong CRM (chạy cục bộ, chỉ đọc).

Nguồn : "02. Follow Client\\10. All Sources.xlsx" (cột Company Name -> ID CRM), rút gọn thành customers_index.csv
        bằng build_customer_index.py. Dữ liệu khách không rời máy và không gửi cho dịch vụ nào.
Ý nghĩa: "Có trong CRM" = tên công ty (đã bỏ dấu, bỏ 'Công ty/TNHH/Cổ phần...') trùng khít một tên trong CRM.
         "Nghi trùng CRM" = giống >= 92% nhưng không trùng khít, cần người kiểm tra.
         Danh sách này KHÔNG cho biết công ty có đang là khách trả tiền hay không.
"""

import csv
import re
import unicodedata
from pathlib import Path

STATUS_IN = "Có trong CRM"
STATUS_MAYBE = "Nghi trùng CRM"
STATUS_NEW = "Chưa có trong CRM"
FUZZY_CUTOFF = 92

_LEGAL = [
    r"\bcong ty\b", r"\bcty\b", r"\btrach nhiem huu han\b", r"\bmot thanh vien\b", r"\bco phan\b",
    r"\btnhh\b", r"\bctcp\b", r"\bmtv\b", r"\bjsc\b", r"\bco ltd\b", r"\bltd\b", r"\bcompany\b",
    r"\blimited\b", r"\bjoint stock\b", r"\bcorporation\b", r"\bcorp\b", r"\binc\b", r"\bcp\b",
]
_LEGAL_RX = [re.compile(p) for p in _LEGAL]


def normalize(name):
    """Bỏ dấu, chữ thường, bỏ ký tự đặc biệt và từ chỉ loại hình công ty."""
    if not name:
        return ""
    s = unicodedata.normalize("NFD", str(name).lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    for rx in _LEGAL_RX:
        s = rx.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) >= 3 else ""


class CustomerIndex:
    def __init__(self, path):
        self.exact = {}
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                self.exact[row["norm_name"]] = (row["crm_id"], row["sample_name"])
        self.norms = list(self.exact)
        try:
            from rapidfuzz import fuzz, process
            self._fuzz, self._process = fuzz, process
        except ImportError:
            self._fuzz = self._process = None

    def match(self, company_name):
        """-> (trạng thái, ID CRM, tên trong CRM). Tên rỗng/quá ngắn -> ('', '', '')."""
        n = normalize(company_name)
        if not n:
            return "", "", ""
        hit = self.exact.get(n)
        if hit:
            return STATUS_IN, hit[0], hit[1]
        if self._process and len(n) >= 8:
            best = self._process.extractOne(n, self.norms, scorer=self._fuzz.ratio, score_cutoff=FUZZY_CUTOFF)
            if best:
                crm_id, sample = self.exact[best[0]]
                return STATUS_MAYBE, crm_id, sample
        return STATUS_NEW, "", ""


def load_index(path):
    p = Path(path)
    return CustomerIndex(p) if p.exists() else None
