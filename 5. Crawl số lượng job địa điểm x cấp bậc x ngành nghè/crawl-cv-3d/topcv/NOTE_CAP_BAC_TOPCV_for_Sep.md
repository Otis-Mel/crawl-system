# Note gửi sếp: TopCV CV không crawl được dimension Cấp bậc

**Ngày:** 2026-05-26
**Tác giả:** Bach Pham

---

## Vấn đề

Build dashboard CRV cần dữ liệu CV TopCV theo 3 dimension: **Ngành × Tỉnh × Cấp bậc** (mirror format 3 jobsite kia).

→ Test thử nhiều cách, **dimension Cấp bậc KHÔNG inferable từ TopCV CV search một cách reliable**.

---

## Bản chất tại sao khó

| Job side (CRV/VNW/VL24h/TopCV Job) | CV side (TopCV CV) |
|---|---|
| 1 tin tuyển dụng = 1 cấp bậc duy nhất (recruiter chọn từ dropdown) | 1 CV = lifetime job titles (Thực tập → Nhân viên → Quản lý → Giám đốc) |
| Có structured filter "cấp bậc" trong API | KHÔNG có structured filter "cấp bậc" cho CV. API reject mọi field như `experience_min/max`, `level`, `job_level` (return 422) |
| Clean partition → đếm đúng | Mọi inference từ keyword đều fuzzy → false positive cao |

---

## 3 cách đã thử

### Cách 1: `and_tags` keyword stacking (scope=`all`)
- VD: search "kế toán" + and_tags=["trưởng phòng"]
- **Vấn đề:** match CV bất kỳ có chữ "trưởng phòng" trong toàn bộ CV body, kể cả trong scope mô tả công ty cũ ("báo cáo cho trưởng phòng kế toán")
- **Kết quả:** false positive ~25-30%. CV Nhân viên bị tag là Quản lý.

### Cách 2: `and_tags` + `scope=position` (chỉ search trong job title)
- VD: search "giám đốc" + and_tags=[] + scope=`["position"]`
- **Kết quả test thực tế (11,054 CV "giám đốc" trên TopCV)** — top 3 CV trả về:
  1. **H. N.** — title: "Trợ lý giám đốc" ← KHÔNG phải Giám đốc thật
  2. T. B. — title: "Chỉ huy trưởng/ Giám đốc dự án" ← OK
  3. A. D. — title: "Trợ lý Giám đốc" ← KHÔNG phải Giám đốc thật
- **Vấn đề:** scope=position match prefix fuzzy → "Trợ lý/Phó/Phụ trách giám đốc" cũng count
- **False positive ~20-25%**

### Cách 3: Keyword + `not_tags` exclusion list
- VD: scope=position + and_tags=["giám đốc"] + not_tags=["trợ lý", "phó", "phụ trách", "nguyên"]
- **Vấn đề:** vẫn miss edge cases (vd "Quyền giám đốc", "Phó tổng giám đốc" có thể là cấp Giám đốc thật, nhưng bị exclude)
- **Còn vấn đề "Nhân viên" overlap:** mọi CV Quản lý CŨNG có chữ "nhân viên" trong experience cũ → nếu and_tags=["nhân viên"] sẽ count cả CV Quản lý. Nếu KHÔNG có and_tag (baseline) thì count luôn cả Thực tập + Giám đốc.
- **False positive vẫn ~15-20%** + setup phức tạp (exclusion list mỗi cấp khác nhau)

### Cách 4: `dob` (Năm sinh) làm age proxy
- VD: Sinh 1985-1994 → cấp Quản lý (30-40 tuổi)
- **Pro:** Structured filter có sẵn TopCV. Mỗi CV có 1 dob duy nhất → không overlap.
- **Con:** Noisy ±15-20%. 1 người 35 tuổi có thể là Junior Marketing (mới chuyển ngành) hoặc CEO. Age ≠ Seniority chính xác.

---

## Tóm tắt accuracy

| Cách | False positive rate | Complexity | Comparable Job side? |
|---|---|---|---|
| 1. and_tags scope=all | ~25-30% | Low | ❌ noise quá cao |
| 2. and_tags scope=position | ~20-25% | Low | ⚠ partial |
| 3. keyword + not_tags | ~15-20% | High (tuning manual) | ⚠ partial |
| 4. dob age proxy | ~15-20% (structured) | Medium | ⚠ partial |
| **DROP cấp bậc (2D only)** | **0% (no inference)** | **Lowest** | **✅ Ngành × Tỉnh OK** |

---

## Đề xuất

**Crawl TopCV CV 2D only (Ngành × Tỉnh), KHÔNG có Cấp bậc.**

Lý do:
1. Số liệu 100% trust được — sếp dùng tự tin pitch khách.
2. Dashboard Supply-Demand ratio cho TopCV vẫn work ở 2 dimension (Ngành × Tỉnh đủ Sales rep filter).
3. 3 jobsite còn lại (CRV/VNW/VL24h CV side) đã có đủ Cấp bậc → dashboard vẫn có 3D cho 3/4 jobsite, chỉ TopCV 2D.
4. Crawl nhanh hơn (~2h vs ~6h), output ~819 rows (13 ngành × 63 tỉnh) sạch.

**Nếu sếp insist phải có Cấp bậc cho TopCV:**
- Dùng `dob` (Năm sinh) làm age proxy → 4 cấp (Thực tập, Mới TN, Nhân viên, Quản lý+Giám đốc gộp 1)
- Accept ±15-20% noise + document caveat trong dashboard tooltip "TopCV cấp bậc = age proxy, không chính xác như Job side"
- Crawl ~3.5h, output ~4,095 rows (13 ngành × 63 tỉnh × 5 cấp)

---

## Câu hỏi cần sếp quyết

1. **Crawl 2D only (recommended) hay dùng dob proxy 3D?**
2. Nếu chọn 2D — chấp nhận dashboard TopCV cell thiếu cấp bậc breakdown so với 3 jobsite kia?
3. Có cần Phase 2 sau (Q3/Q4 2026) thử ML model phân loại cấp bậc dựa trên full CV text? (out of scope hiện tại, nhưng có thể plan)
