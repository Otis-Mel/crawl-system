# TopCV CV Crawler — Chi tiết dự án

> 🔧 **FIXED 2026-05-27 (chiều)** — Bug location format đã sửa. Slug map cho 63 tỉnh đã verify từ Vue dropdown dataOptions. 10-cell spot-check pass. Data cũ trong `topcv_cv_raw_2026-05-27.json` (1,197 cells với Vietnamese name) đã DEPRECATED — re-crawl với slug format đang chạy.

## Tổng quan

Crawl số lượng CV trên TopCV Recruiter portal theo **2 chiều: Ngành × Tỉnh** (21 × 63 = 1,323 cells). Append vào sheet `TopCV` trong `CV_Count_Tracker.xlsx` chung với 3 jobsite khác.

**Khác biệt với 3 jobsite kia:** TopCV CV **KHÔNG** crawl dimension Cấp bậc — xem [NOTE_CAP_BAC_TOPCV_for_Sep.md](./NOTE_CAP_BAC_TOPCV_for_Sep.md) cho lý do (4 cách thử, false positive 15-30%).

| Item | Giá trị |
|---|---|
| Endpoint | `POST tuyendung.topcv.vn/api/v1/recruitment-campaigns/{id}/search-cv/cvs` |
| Auth | JWT qua axios interceptor — không bypass được, phải dùng UI |
| Method | Browser-driven (Claude in Chrome + JS injection) |
| Filters | `keyword` (search position), `locations` (**slug format `["location:hcm"]`**), `selected_search_tags=["position"]` |
| Output | 1,323 rows (21 ngành × 63 tỉnh) long format |
| ETA | ~3-5 giờ tuỳ rate limit |

---

## ⚠️ Location format — CRITICAL

**SAI (silent fail):** `locations: ["TP Hồ Chí Minh"]` → backend trả status=success NHƯNG total giảm 8.5x (4,896 thay vì 41,744).

**ĐÚNG:** `locations: ["location:hcm"]` → match UI số.

### Discovery slug map (2026-05-27)
- Source: Vue.js multiselect component `$parent._data.dataOptions` (412 locations: 64 provinces + ~150 districts + ~200 wards)
- Extract: 63 real provinces + 1 pseudo region (`ĐBS Cửu Long` — skip)
- Verify: spot-check 10 diverse cells (HN, HCM, ĐN, HP, BD + Cao Bằng, Hà Giang, Lai Châu, Ninh Thuận, Phú Yên) × diverse kw → 10/10 pass + sample titles 100% match keyword

### Slug pattern KHÔNG auto-derivable
| Vietnamese name | Slug | Note |
|---|---|---|
| TP Hồ Chí Minh | `location:hcm` | abbreviation, không phải "hochiminh" |
| Bà Rịa Vũng Tàu | `location:vungtau` | chỉ "vungtau" |
| Huế | `location:hue` | OK |
| Đăk Lăk | `location:daklak` | kiểu cũ "đăk" không phải "đắk" |
| ĐBS Cửu Long | `location:cuulong` | **PSEUDO** — region group, không phải tỉnh thật |

→ Pattern auto-derive (vd "hochiminh", "bariavungtau") chắc chắn fail. Phải scrape từ Vue store.

→ Slug map đầy đủ trong [`topcv_cv_locations.json`](./topcv_cv_locations.json).

---

## Methodology — 4 vấn đề đã giải quyết

Khi user (sếp) review batch đầu, phát hiện **4 vấn đề methodology** khiến số liệu không trust được. Đã fix tất cả ở phiên bản hiện tại:

### 1. Ngành mapping mismatch (MKT 21 keywords vs CRV chuẩn)
**Vấn đề:** Team Marketing cấp 21 keywords (vd "bán hàng" + "kinh doanh" tách 2). CRV chuẩn merge thành 1 ngành "Bán hàng/Kinh doanh" → không pair được Job side.

**Fix:** Map 21 MKT → 21 CRV ngành chuẩn 1-1 ([keywords_by_crv_nganh.json](./keywords_by_crv_nganh.json)). Mapping table review trong [TopCV_mapping_for_review.xlsx](./TopCV_mapping_for_review.xlsx).

### 2. `and_tags` fuzzy unreliable
**Vấn đề:** search "kế toán" + `and_tags=["quản lý"]` match CV có chữ "quản lý" trong toàn body (kể cả "báo cáo cho quản lý") → KHÔNG đảm bảo person IS quản lý.

**Fix:** DROP `and_tags`. Mỗi search chỉ 1 keyword chính.

### 3. Job title scope=position
**Vấn đề:** search "kế toán" với scope=`all` trả CV có title "Trưởng phòng kinh doanh" vì body mention "kế toán" trong scope mô tả công ty cũ.

**Fix:** Set `selected_search_tags=["position"]` — chỉ match CURRENT title. Như định nghĩa của Job side ("tin tuyển dụng ngành X").

### 4. Scope inconsistent (all vs experience)
**Vấn đề:** scope=`all` vs `experience` ra số khác nhau (vd kế toán: 272K vs 53K). Không document → kết quả không comparable batch sang batch.

**Fix:** Chốt 1 scope chuẩn = `["position"]` cho mọi snapshot.

---

## Approach kỹ thuật

### Tại sao browser-driven (không phải requests)
TopCV recruiter API yêu cầu:
- Cookies + JWT bound vào browser context
- CSRF token rotate
- App's axios interceptor inject Bearer dynamic

→ Không reproduce auth bằng `requests` được. **Bắt buộc dùng UI:** mở browser, drive form filters qua JavaScript, intercept API response qua XHR hook.

### Stack
| Layer | Tool |
|---|---|
| Browser control | **Claude in Chrome** extension (`mcp__Claude_in_Chrome__javascript_tool`) |
| Form mutation | Vue.js `form.__vue__.filters.{name}.value = X` (direct mutation) |
| API capture | `XMLHttpRequest.prototype.open/send` override → `window._apiResp` buffer |
| Direct API fetch | `fetch()` với Bearer token từ localStorage — fast hơn UI drive |
| Persistence | `localStorage["topcv_recrawl_v4"]` (crash-safe state) |
| Script reload | Full crawler script saved as string trong `localStorage.TOPCV_CRAWLER_SCRIPT` |

### Resume pattern
- Mỗi cell xong → append vào `window._fc` + persist to `localStorage`
- Resume: load `_fc` từ localStorage → build `donePairs` Set `{crv}|{tinh}` → skip cells already done (cả success + timeout)
- Survives page reload, session expiry, browser crash

### Anti-stuck mechanisms
1. **429 cooldown** 5 phút (patched từ 2 phút), max 4 retries.
2. **Auto-skip** sau retry exhausted: thêm cell vào `_fc` với `total=null + note="429_FORCE_SKIP"` để move on.
3. **Sanity check 3 cells đầu** vs UI count trước khi loop production — abort nếu mismatch.

---

## Files

```
topcv/
├── README.md                              # File này
├── NOTE_CAP_BAC_TOPCV_for_Sep.md         # Lý do drop cấp bậc dimension (4 cách thử)
├── PHASE_A_REPORT.md                      # Inspect API endpoint (Phase A)
├── _phase_a_v2_methodology_test.py        # 8-cell test verify position scope
├── _build_topcv_mapping.py                # Build mapping 21 MKT → 21 CRV
├── _generate_location_slugs.py            # ⚠️ DEPRECATED — pattern auto-derive sai, không dùng
├── _export_topcv_to_excel.py              # Export JSON → Excel (sheet TopCV + review file)
├── keywords_by_crv_nganh.json             # 21 CRV ngành → 1 keyword chính
├── topcv_cv_locations.json                # 63 tỉnh + slug verified từ Vue dataOptions
├── TopCV_mapping_for_review.xlsx          # Mapping table cho sếp review
├── TopCV_CV_Count_2026-05-27.xlsx         # ⚠️ DEPRECATED — data cũ với Vietnamese name
└── topcv_cv_raw_2026-05-27.json           # ⚠️ DEPRECATED — 1,197 cells với format sai
```

---

## Ước tính thời gian chạy

| Pha | Thời gian |
|---|---|
| Setup (login + inject script) | 5 phút |
| Sample 5 ngành × 63 tỉnh = 315 cells (rate ~10-12/min, no UI render) | ~30-45 phút |
| Full crawl 1,323 cells (21 ngành × 63 tỉnh) | **~2-3 giờ** (faster than V3 vì direct fetch) |
| Retry timeout cells | ~15 phút |
| Export Excel | <1 phút |
| **Tổng full** | **~3-4 giờ** |

---

## Workflow chạy snapshot mới

1. **Login TopCV Recruiter** vào `https://tuyendung.topcv.vn/app/recruitment-campaigns/{ID}/search-cv` (account OCB hiện dùng campaign 2490023).
2. **Verify slug map còn valid:** chạy spot-check 3 cells (kế toán × HN, marketing × HCM, IT × ĐN) — confirm match UI count ±2%.
3. **Inject crawler script V4 (direct fetch, slug format).**
4. **Monitor** mỗi 4-5 phút qua Claude in Chrome.
5. **Khi `_RECRAWL_DONE=true`** → đọc `localStorage.topcv_recrawl_v4` lưu thành JSON file `topcv_cv_raw_{date}.json`.
6. **Run `py _export_topcv_to_excel.py`** → append vào `CV_Count_Tracker.xlsx` sheet `TopCV` + tạo review file riêng.
7. **Retry timeout cells** (separate pass, optional): re-run với same script (donePairs sẽ skip cells đã có data).

---

## Output Excel format

Append vào sheet `TopCV` của `CV_Count_Tracker.xlsx` — long format:

| Date | Ngành | Địa điểm | CV count | Note |
|---|---|---|---|---|
| 2026-05-27 | Kế toán / Kiểm toán | Hà Nội | 54,575 | |
| 2026-05-27 | Bán hàng / Kinh doanh | TP Hồ Chí Minh | 41,744 | |
| ... | ... | ... | ... | ... |
| 2026-05-27 | Điện / Điện tử / ... | Hà Giang | | 429_FORCE_SKIP |

**Khác với 3 jobsite kia:** chỉ có 1 cột "CV count" thay vì N cột cấp bậc. Dashboard cần handle đặc biệt cho TopCV (xem Wave 4 Phase C — task #17).

---

## Snapshot 2026-05-27 — DEPRECATED + re-crawl

**Data CŨ (Vietnamese name format — DEPRECATED):**
- 1,197 cells | 1,152 có data (96.2%) | 45 timeout
- 642,469 CVs total — **silent under-count ~8.5x do bug location format**

**Data MỚI (slug format, đang re-crawl từ 2026-05-27 chiều):**
- Sample 5 ngành (Kế toán, Marketing, IT, Luật, Bán hàng/KD) × 63 tỉnh = 315 cells
- Sau khi sample OK → full crawl 21 ngành × 63 tỉnh = 1,323 cells
- Expected total CVs ~5-8M (8x scale up vs data cũ)

---

## Những lỗi đã gặp — không lặp lại

| Vấn đề | Nguyên nhân | Cách fix |
|---|---|---|
| **🆕 Locations silent fail** (HCM = 4,896 thay vì 41,744) | Crawler gửi Vietnamese name `["TP Hồ Chí Minh"]` — backend không reject (status=success) nhưng trả fuzzy match số nhỏ | Phải dùng slug `["location:hcm"]` từ Vue dataOptions. Scrape từ multiselect, KHÔNG auto-derive |
| **🆕 Phantom "verified" claim** | File `topcv_cv_locations.json` ghi "verified Vietnamese name works" mà không có test code | Bắt buộc mọi field "verified" phải kèm test script chạy được + spot-check ≥3 cells vs UI |
| **🆕 Pattern auto-derive sai** | `_generate_location_slugs.py` đoán `Hồ Chí Minh → hochiminh` nhưng UI dùng `hcm` | Slug = arbitrary code, phải scrape từ source UI |
| HCM under-count (tên Vietnamese variant) | Dùng "Hồ Chí Minh" thay vì "TP Hồ Chí Minh" | DEPRECATED — fix bằng slug format, không cần lo tên Vietnamese variant nữa |
| 3.5s wait → chip stale read | DOM update async, đọc cũ | XHR hook chờ actual API response (`window._apiResp`) |
| Button stuck `disabled+btn-loading` sau ~100 cells | TopCV UI leak loading state | btn-unstick observer mỗi 1s, force reset sau 8s stuck |
| Page reload → JS context dies → crawler chết | Không có persistence | Save full script vào `localStorage.TOPCV_CRAWLER_SCRIPT`, eval lại sau reload |
| 429 hit liên tục trên 1 cell | TopCV rate limit IP sticky 2+ phút | Cooldown 5 phút (patched từ 2 phút), max 4 retries |
| Wrote `0` cho API timeout | Lẫn lộn "0 CV thật" vs "API timeout" | Strict: chỉ ghi `0` khi UI hiện "Không tìm thấy CV". Timeout/429 → `total=null + note` |
| Crawler stuck retrying same cell forever | `donePairs` không include timeout cells | Include ALL processed cells (success + timeout) trong `donePairs` |
| Set wakeup 25 phút → page reloaded → 25 phút lãng phí | Poll quá ít | Monitor mỗi 4-5 phút (giữ cache warm) |
| Threshold preventive reload 10 cells gây ETA tăng 2x | Mỗi reload Claude phải re-inject thủ công | Tăng threshold lên 200 + add btn-unstick observer thay vì reload |
| Vue v-model setter + 'input' event không sync filter | TopCV không react đúng | Direct mutation `form.__vue__.filters.{name}.value = X` |
| Loops conflicting (V1 + V2 fighting nhau) | Multiple eval không clear async loops | Full page reload để nuke all running async loops |

---

## Decisions chốt từ sếp

| # | Vấn đề | Decision |
|---|---|---|
| 1 | Crawl 2D hay 3D? | **2D only** (Ngành × Tỉnh) — drop cấp bậc do false positive cao |
| 2 | Ngành mapping | **1-1 với CRV chuẩn 21 ngành** (merge MKT keywords) |
| 3 | Search scope | `selected_search_tags=["position"]` cho mọi snapshot |
| 4 | Khi API timeout | `total=null + note="API_TIMEOUT"` — KHÔNG ghi 0 |
| 5 | Khi UI "Không tìm thấy CV phù hợp" | `total=0` — đây là 0 thật |
| 6 | Schedule | One-shot snapshot (chưa cần weekly) |
| 7 | **🆕 Re-crawl strategy** | Sample 5 ngành × 63 tỉnh trước → review → full re-crawl |

---

## Lessons learned cho future crawler

1. **Mọi field "verified" trong JSON config phải kèm `_test_<field>.py`** chạy được + assertion pass — không claim phantom verified.
2. **Sanity check 3 cells đầu vs UI count** bắt buộc trước khi loop production. Nếu mismatch >5% → abort + investigate.
3. **Single source of truth:** config files phải reference Phase A inspection report. Không có 2 file ghi format khác nhau cho cùng 1 field.
4. **Backend silent failure đáng sợ hơn explicit error.** Validate response data shape, không chỉ status code.
5. **Slug/ID arbitrary code phải scrape từ source UI**, không auto-derive bằng pattern. Vietnamese diacritic normalization không reliable cho slug map.
