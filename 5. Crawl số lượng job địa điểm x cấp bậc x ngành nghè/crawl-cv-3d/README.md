# CV Count Crawler — 4 Websites

## Tổng quan dự án

Crawl số lượng CV từ **4 website tuyển dụng lớn tại Việt Nam** mỗi ngày, lưu vào 1 file Excel chung để theo dõi xu hướng thị trường lao động theo thời gian.

| Website | Trạng thái |
|---------|-----------|
| CareerViet | ✅ Hoàn thành |
| VietnamWorks | ✅ Hoàn thành |
| Vieclam24h | ✅ Hoàn thành |
| TopCV | ✅ Hoàn thành (2D — Ngành × Tỉnh, không có cấp bậc) |

---

## Cấu trúc project

```
project/
├── main.py                  # Chạy lần lượt 4 site trong 1 lần, ghi chung 1 Excel
├── excel_writer.py          # Dùng chung cho tất cả sites
├── config.py                # Cấu hình chung (delay, timeout, đường dẫn)
├── careerviet/
│   ├── auth.py
│   ├── crawler.py
│   └── mappings.py
├── vietnamworks/
│   ├── auth.py
│   ├── crawler.py
│   ├── mappings.py
│   ├── excel_vnw.py         # Ghi 3 sheet VNW vào file Excel chung
│   ├── setup_cookies_vnw.py # Playwright login → cookies.json
│   ├── cookies.json         # Session cookie VNW (KHÔNG commit)
│   └── linh_vuc.json        # 49 lĩnh vực: name → ID (đã extract sẵn, dùng lại)
├── vieclam24h/              # Chưa implement
├── topcv/                   # Chưa implement
├── cookies/
│   ├── careerviet.json      # Session cookie (KHÔNG commit lên git)
│   ├── vietnamworks.json
│   ├── vieclam24h.json
│   └── topcv.json
├── setup_cookies.py         # Playwright — lấy cookie từng site (chạy 1 lần)
├── run.bat                  # Wrapper chạy main.py + ghi log hàng ngày
├── setup_scheduler.ps1      # Đăng ký Windows Task Scheduler
└── CV_Count_Tracker.xlsx
```

> **Lưu ý:** Hiện tại các file careerviet nằm trực tiếp trong `project/` — sẽ tổ chức lại vào subfolder khi bắt đầu site thứ 2.

---

## Output Excel

1 file `CV_Count_Tracker.xlsx`, chia thành 4 sheets 3D:

| Sheet | Nội dung | Hàng/ngày |
|-------|---------|-----------|
| `CareerViet` | Ngành × Địa điểm × Cấp bậc — CRV (50 × 71) | ~3,550 |
| `VietnamWorks_LV` | Lĩnh vực × Địa điểm × Cấp bậc — VNW (49 × 66) | ~3,234 |
| `VietnamWorks_Ngành` | Ngành nghề × Địa điểm × Cấp bậc — VNW (159 × 66) | ~10,494 |
| `VL24h` | Ngành × Địa điểm × Kinh nghiệm — VL24h (53 × 63) | ~3,339 |

**Format mỗi sheet:**

| Date | Ngành | Địa điểm | Cấp bậc 1 | Cấp bậc 2 | ... |
|------|-------|----------|-----------|-----------|-----|
| 2026-05-18 | IT | Hà Nội | 1000 | 500 | ... |

- Mỗi ngày append thêm dòng, không ghi đè
- Dùng Pivot Table để phân tích cross-tab (Ngành × ĐĐ × Cấp bậc × Thời gian)
- Checkpoint mỗi 200 hàng → an toàn nếu crawl bị kill giữa chừng
- Resume tự động khi restart: đọc các cặp đã có trong Excel, skip

---

## Migration từ 2D sang 3D

Trước khi chạy lần đầu với code mới:

```powershell
# 1. Backup file cũ
Copy-Item CV_Count_Tracker.xlsx CV_Count_Tracker_2D_backup.xlsx

# 2. Xóa file gốc để code tạo lại với sheet 3D
Remove-Item CV_Count_Tracker.xlsx
```

> File backup giữ nguyên toàn bộ lịch sử 2D. File mới bắt đầu từ hôm nay với format 3D.

---

## Tự động hóa

- **Task Scheduler** chạy `run.bat` lúc **21:00 tối mỗi ngày** (xong trước 6:30 sáng hôm sau)
- `main.py` chạy lần lượt CRV → VNW → VL24h, ước tính tổng ~9.5 giờ
- Log lưu tại `project/logs/YYYY-MM-DD.txt`
- Khi cookie hết hạn: script thông báo rõ, chạy lại `setup_cookies.py`

---

---

# CAREERVIET — Chi tiết kỹ thuật

## Cấu trúc trang

- Framework: **Next.js App Router** (SSR + client hydration)
- CV count **KHÔNG nằm trong HTML** — được render phía client sau khi JavaScript gọi API
- Cần đăng nhập bằng tài khoản **Employer** mới xem được trang tìm hồ sơ

## Auth

- Login qua **Google OAuth** (không có form email/password)
- Session lưu trong **HttpOnly cookies** — không đọc được bằng JavaScript hay thư viện ngoài
- Chrome 147+ dùng **App-Bound Encryption** → các thư viện như `browser-cookie3`, `rookiepy` đều không hoạt động
- **Giải pháp:** Dùng `setup_cookies.py` (Playwright) — mở browser 1 lần, user login thủ công, Playwright lưu toàn bộ cookie (kể cả HttpOnly) vào `cookies/careerviet.json`
- Các lần crawl sau dùng `requests` + cookie file — không cần browser

## API Endpoint (đã xác nhận)

**Endpoint:** `POST https://internal-api.careerviet.vn/api/v1/jss/emp/resumes/hr-centrals`

**Auth:** Session cookies (không cần Bearer token)

**Count trả về tại:** `response.metadata.itemCount`

**Body — Ngành nghề:**
```json
{"industry_ids": [4], "level_id": 3, "limit": 1, "order": "desc", "sort_by": ""}
```

**Body — Địa điểm:**
```json
{"location_ids": [{"location_id": 8}], "level_id": 3, "limit": 1, "order": "desc", "sort_by": ""}
```

> ⚠️ `industry_ids` nhận **integer**, `location_ids` nhận **object** `{"location_id": N}` — khác nhau, dễ nhầm

## Mapping APIs

| Dữ liệu | Endpoint |
|---------|----------|
| Cấp bậc | `GET /api/v1/cs/jsk/levels/searches` |
| Ngành nghề | `GET /api/v1/cs/jsk/industries/groups/list` |
| Địa điểm | `GET /api/v1/cs/jsk/locations` |

## Cấp bậc

| ID | Tên |
|----|-----|
| 1  | Sinh viên/ Thực tập sinh |
| 2  | Mới tốt nghiệp |
| 3  | Nhân viên |
| 4  | Trưởng nhóm / Giám sát |
| 5  | Quản lý |
| 11 | Quản lý cấp cao |
| 12 | Điều hành cấp cao |

## Ước tính thời gian chạy (3D với probe-skip, delay 0.4s)

| Pass | Requests | Thời gian |
|------|-----------|-----------|
| Probe (50 × 71 cặp) | 3,550 | ~24 phút |
| Detail (~50% non-zero × 7 CB) | ~12,425 | ~83 phút |
| **Tổng CareerViet** | | **~107 phút** |

## Những lỗi đã gặp — không lặp lại

| Vấn đề | Nguyên nhân | Cách fix |
|--------|------------|----------|
| Parse HTML không tìm được count | CV count là client-side rendered, không có trong HTML ban đầu | Dùng POST API trực tiếp |
| Cookie không lấy được tự động | Chrome 147+ App-Bound Encryption | Dùng Playwright login 1 lần |
| `location_ids` trả về 400 | Format khác `industry_ids` — phải dùng object | `[{"location_id": N}]` thay vì `[N]` |
| Excel thiếu cột cấp bậc | File tạo lần đầu với test 2 cấp bậc, header bị thiếu | Xóa file, tạo lại với đủ 7 cấp bậc |
| Task Scheduler lỗi permission | `RunLevel Highest` yêu cầu admin | Bỏ `RunLevel Highest` |
| Unicode error khi chạy script | Windows console CP1252 không encode được tiếng Việt | Thêm `sys.stdout.reconfigure(encoding='utf-8')` đầu mỗi script |
| Location API trả về cả địa điểm nước ngoài (121 locations) | API gộp tất cả quốc gia, không filter mặc định | Trong `fetch_locations`: chỉ lấy group có `country_id == 1` (Việt Nam = 71 tỉnh/thành) |

---

---

# VIETNAMWORKS — Chi tiết kỹ thuật

## Cấu trúc trang

- React micro-frontend (Module Federation) — không SSR
- 3 cấp filter độc lập: **Lĩnh vực** (49 ngành kinh tế) > **Ngành nghề** (159 nhóm chức năng) > **Chức năng** (job function chi tiết)
- Resume search GQL ở subdomain riêng: `ms.vietnamworks.com`

## Auth

- Login bằng email/password (employer account)
- Cookie + `Authorization: Bearer <ONB_JWT>` header BẮT BUỘC cả 2 — chỉ cookie sẽ 401
- `setup_cookies_vnw.py`: Playwright mở browser, user login thủ công, lưu cookies vào `vietnamworks/cookies.json`

## API Endpoint (đã verify)

**Endpoint count:** `POST https://ms.vietnamworks.com/resume-search-api/graphql`

**Query template:**
```graphql
query Count($f: String!) {
  searchES(
    algoliaFilter: { filters: $f, page: 0, hitsPerPage: 1, restrictSearchableAttributes: "" }
    locale: "vn"
  ) { nbHits }
}
```

**Filter syntax (Lucene, verified qua intercept browser):**

| Chiều | URL param | GQL filter |
|---|---|---|
| Lĩnh vực | `industry=X` (legacy, không UI) | `expectedCategoryIds:(X)` |
| **Lĩnh vực dùng thật** (UI 'Lĩnh vực') | `jobIndustry=X` | `expectedIndustryV3Ids:(X)` |
| **Ngành nghề** (UI 'Ngành nghề') | `jobFunction=X` | `expectedjobFunctionV3Id:(X)` |
| Cấp bậc | `jobLevel=X` | `jobLevelId:X` |
| Địa điểm | `location=X` | `expectedWorkingLocation.cityId:(X)` |

Combine bằng ` AND ` giữa các filter.

> ⚠️ **Đặt tên UI khác URL/GQL**: UI "Lĩnh vực" → URL `jobIndustry` (KHÔNG phải `industry`). URL `industry` là field legacy, hiện UI không dùng.

**Ground truth verified:** `expectedjobFunctionV3Id:(123) AND jobLevelId:5 = 1816` (Quản lý văn phòng × Nhân viên).

## Mapping APIs

| Dữ liệu | Nguồn |
|---|---|
| Lĩnh vực (49) | `vietnamworks/linh_vuc.json` — đã extract sẵn bằng Playwright, dùng lại |
| Ngành nghề (159) | `GET https://employer.vietnamworks.com/api/choices/job-functions?lang=1` (tiếng Việt) |
| Địa điểm (66) | `GET https://employer.vietnamworks.com/api/lead-cities/1` (tiếng Việt có dấu) |
| Cấp bậc (5) | Hardcode trong `mappings.py` |

## Cấp bậc

| ID | Tên |
|----|-----|
| 1 | Mới tốt nghiệp |
| 5 | Nhân viên |
| 7 | Trưởng phòng |
| 3 | Giám đốc và cấp cao hơn |

> ID 8 ("Thực tập sinh/Sinh viên") không xuất hiện trong filter UI employer — đã loại khỏi crawler.

## Ước tính thời gian chạy (3D với probe-skip, delay 0.4s)

| Sheet | Probe | Detail (~50% × 5 CB) | Thời gian |
|---|---|---|---|
| VietnamWorks_LV (49 × 66) | 3,234 | ~8,085 | ~76 phút |
| VietnamWorks_Ngành (159 × 66) | 10,494 | ~26,235 | ~245 phút |
| **Tổng VietnamWorks** | | | **~321 phút** |

## Cách cập nhật `linh_vuc.json` (khi taxonomy đổi)

49 lĩnh vực không có API endpoint — IDs nằm trong React state. Cách lấy:
1. Mở Playwright, navigate `https://employer.vietnamworks.com/v3/candidate/search`
2. Đổi sang tiếng Việt (flag góc phải trên cùng) → click "Bộ lọc" → click dropdown "Chọn lĩnh vực"
3. Scroll virtual list lấy hết tên option (49 cái)
4. Cho từng tên: navigate fresh → mở dropdown → scroll đến option → click → click "Tìm kiếm" → đọc URL → parse `jobIndustry=X` → lưu mapping

## Những lỗi đã gặp — không lặp lại

| Vấn đề | Cách fix |
|---|---|
| GQL trả 401 dù cookie hợp lệ | Cần thêm `Authorization: Bearer <ONB_JWT>` header — chỉ cookie không đủ |
| Dùng `expectedCategoryIds` cho ngành nghề (filter sai) | Mỗi filter UI dùng GQL field khác nhau — phải intercept browser để verify, không đoán theo tên URL |
| Hardcode toạ độ chuột để click element | Luôn dùng locator hoặc tìm element động qua `evaluate` + bounding rect |
| `headless=True` redirect login dù có cookie | Microfrontend kiểm tra browser fingerprint — dùng `headless=False` |
| Click `wait_for_load_state('networkidle')` timeout | Page polling liên tục — dùng `wait_for_timeout(N)` cố định |
| Intercept GQL chỉ thấy filter rỗng | React Router xử lý URL params async — đợi 6-8s rồi capture request CUỐI có filter |
| Cố lấy ID từ DOM attribute của antd Select | IDs nằm trong React state, không phải DOM — phải click option rồi đọc URL update để lấy ID |
| antd Select virtualized — chỉ render 7/49 option | Scroll `.rc-virtual-list-holder` để load thêm vào DOM |
| Dùng `locale: "vi"` trong GQL | UI thật gửi `locale: "vn"` — verify bằng intercept |
| Tìm endpoint bằng cách probe URL khả dĩ | `/api/choices/industries` không tồn tại — IDs lĩnh vực phải lấy qua tương tác UI, không có API riêng |
| Crawl 27 phút bị kill → mất sạch tiến độ | `crawler.py` chỉ ghi Excel ở cuối — đã sửa: `save_dimension()` lưu Excel sau mỗi chiều (LV → Ngành → ĐĐ). Resume bằng `has_today_data()` skip chiều đã xong. |
| Python buffer stdout khi chạy background → log file 0 bytes | Chạy với `py -u` (unbuffered) hoặc set `PYTHONUNBUFFERED=1` |

---

# VIECLAM24H — Chi tiết kỹ thuật

## Cấu trúc trang

- **Next.js App Router — CSR** (không phải SSR): raw HTML không chứa count, data load hoàn toàn phía client
- Count lấy qua API riêng tại subdomain `apiv2.vieclam24h.vn`
- Trang search yêu cầu đăng nhập bằng tài khoản **Employer NTD**

## Auth

- Playwright mở thẳng **SEARCH_URL** (trang yêu cầu auth) → user đăng nhập thủ công
- Dùng `context.on("request")` để intercept network request tới `apiv2.vieclam24h.vn` → lấy `Authorization: Bearer <token>`
- Token **không** nằm trong cookie hay localStorage — chỉ xuất hiện trong network request
- Lưu token vào `vieclam24h/cookies.json` dưới key `re_access_token`

> ⚠️ Phải navigate đến SEARCH_URL (không phải HOME_URL) mới trigger API call và bắt được token

## API Endpoint (đã verify)

**Endpoint:** `GET https://apiv2.vieclam24h.vn/seeker/fe/api/v1/search/ai-resume`

**Auth:** `Authorization: Bearer <re_access_token>`

**Count trả về tại:** `response["data"]["total_items"]`

**Response code thành công:** `200` (không phải `1`)

**Params:**

| Filter | URL param |
|--------|-----------|
| Ngành nghề | `occupation_ids[0]=<id>` |
| Địa điểm | `province_ids[0]=<id>` |
| Kinh nghiệm | `experience[0]=<value>` (1–8) |
| Pagination | `per_page=1&action=loadmore` |

> ⚠️ Dùng PHP-style với index 0: `occupation_ids[0]` — **KHÔNG** phải `occupation_ids[]` như URL trình duyệt

## Chiều thứ 2

Vieclam24h không có "Cấp bậc" riêng biệt như CareerViet/VietnamWorks. Thay vào đó dùng **Kinh nghiệm** (8 mức):

| Value | Tên |
|-------|-----|
| 1 | Chưa có kinh nghiệm |
| 2 | Dưới 1 năm |
| 3 | 1 năm |
| 4 | 2 năm |
| 5 | 3 năm |
| 6 | 4 năm |
| 7 | 5 năm |
| 8 | Hơn 5 năm |

## Mapping

| Dữ liệu | Nguồn | Số lượng |
|---------|-------|---------|
| Ngành nghề | `vieclam24h/nganh_nghe.json` — extract từ React fiber state | 53 |
| Địa điểm | `vieclam24h/dia_diem.json` — extract từ React fiber state | 63 |
| Kinh nghiệm | `vieclam24h/kinh_nghiem.json` — hardcode | 8 |

## Ước tính thời gian chạy (3D với probe-skip, delay 0.5s)

| Pass | Requests | Thời gian |
|------|-----------|-----------|
| Probe (53 × 63 cặp) | 3,339 | ~28 phút |
| Detail (~50% non-zero × 8 KN) | ~13,356 | ~111 phút |
| **Tổng VL24h** | | **~139 phút** |

## Những lỗi đã gặp — không lặp lại

| Vấn đề | Nguyên nhân | Cách fix |
|--------|------------|----------|
| Dùng `requests.get` HTML + regex để lấy count | Nhầm trang dùng SSR — thực ra CSR, HTML không có count | Gọi thẳng API `apiv2.vieclam24h.vn` |
| `page.on("request")` không bắt được Bearer token | Navigate HOME_URL không cần auth → không có API call | Navigate thẳng SEARCH_URL (yêu cầu auth) để trigger API call ngay |
| Login detection sai — báo "đã login" ngay lập tức | `wait_for_url` thỏa mãn ngay vì HOME_URL không chứa "login" | Dùng `context.on("request")` chờ đến khi bắt được token từ API call |
| `re_access_token` không tìm được trong cookies/localStorage | Token không lưu dạng cookie hay storage — chỉ tồn tại trong request header | Intercept request qua Playwright `context.on("request")` |
| API trả `code: 200` bị coi là lỗi | Các site khác trả `code: 1` — vieclam24h dùng `200` | Check `data.get("code") in (1, 200)` |
| URL dùng `occupation_ids[]=X`, API thật dùng `occupation_ids[0]=X` | URL trình duyệt ≠ API param format | Dùng PHP-style index 0: `params["occupation_ids[0]"] = id` |
| Session cookies thôi không đủ để gọi API từ Python | API kiểm tra Bearer token, cookies chỉ đủ khi gọi từ browser (CORS) | Bắt buộc có header `Authorization: Bearer <token>` |
| Mất tiến độ nếu crawl bị kill giữa chừng | Cũ: lưu Excel sau khi xong cả chiều (53 hoặc 63 items) | `append_row()` lưu 1 dòng ngay sau mỗi item; `get_today_done_items()` để resume tự động |

---

# TOPCV — Chi tiết kỹ thuật

> 📘 Chi tiết đầy đủ trong [`topcv/README.md`](./topcv/README.md). Phần dưới là tóm tắt cho người đọc cross-site.

## Cấu trúc trang

- Trang Recruiter portal: `https://tuyendung.topcv.vn/app/recruitment-campaigns/{ID}/search-cv`
- Vue.js SPA, không SSR. CV count render client-side sau khi API trả response.
- Cookies + JWT bound vào browser session — **không reproduce auth bằng `requests` được**.

## Auth

- Login bằng email/password Recruiter account (campaign 2490023 cho OCB).
- JWT inject dynamic vào header `Authorization: Bearer <...>` qua app's axios interceptor.
- Token rotate sau mỗi request, CSRF check → **bắt buộc dùng UI** (Claude in Chrome extension drive browser).

## API Endpoint (đã verify)

**Endpoint:** `POST https://tuyendung.topcv.vn/api/v1/recruitment-campaigns/{campaign_id}/search-cv/cvs`

**Count trả về tại:** `response.cvs.total`

**Body filter (Vue.js form state):**
```json
{
  "keyword": "kế toán",
  "locations": ["location:hcm"],
  "selected_search_tags": ["position"],
  "and_tags": [],
  "or_tags": [],
  "not_tags": []
}
```

> ⚠️ `selected_search_tags=["position"]` BẮT BUỘC — `["all"]` cho noise cao (CV có keyword trong mô tả công ty cũ cũng match)

> ⚠️ `locations` PHẢI dùng SLUG format `["location:hcm"]`, KHÔNG được dùng Vietnamese name `["TP Hồ Chí Minh"]` — backend silent-fail (status=success nhưng total sai ~8.5x). Discovered + fixed 2026-05-27.

## Filter syntax

| Chiều | Format |
|---|---|
| Keyword (proxy cho ngành) | `keyword: "<vietnamese text>"` |
| Địa điểm | `locations: ["location:<slug>"]` (vd `["location:hcm"]`, `["location:hanoi"]`) |
| Scope | `selected_search_tags: ["position"]` — match job title hiện tại |

> ⚠️ **Slug không auto-derivable:** TP HCM=`hcm` (không phải `hochiminh`), Bà Rịa Vũng Tàu=`vungtau`. Slug map đầy đủ scrape từ Vue dropdown dataOptions — xem `topcv/topcv_cv_locations.json`.

## Mapping

| Dữ liệu | Nguồn | Số lượng |
|---|---|---|
| Ngành (proxy qua keyword) | `topcv/keywords_by_crv_nganh.json` — 1-1 với CRV chuẩn | 21 |
| Địa điểm | `topcv/topcv_cv_locations.json` — slug verified từ Vue multiselect dataOptions | 63 (+ 1 pseudo skip) |
| **Cấp bậc** | **DROP** — không có structured filter reliable | — |

## Tại sao không có cấp bậc

4 cách thử đều fail với false positive 15-30%:
1. `and_tags` keyword stacking (scope=all) → match keyword trong body CV cũ
2. `and_tags` + scope=position → match prefix "Trợ lý/Phó giám đốc"
3. `not_tags` exclusion list → miss edge cases ("Quyền giám đốc"), tuning manual phức tạp
4. `dob` (Năm sinh) age proxy → noise ±15-20%, age ≠ seniority

→ **Decision:** crawl 2D only (Ngành × Tỉnh) — số liệu 100% trust được. Xem chi tiết trong [`topcv/NOTE_CAP_BAC_TOPCV_for_Sep.md`](./topcv/NOTE_CAP_BAC_TOPCV_for_Sep.md).

## Methodology — 4 vấn đề đã fix

| # | Vấn đề | Fix |
|---|---|---|
| 1 | Ngành mismatch (21 MKT vs CRV chuẩn) | Map 1-1 → 21 CRV ngành |
| 2 | `and_tags` fuzzy unreliable | DROP `and_tags`, chỉ 1 keyword |
| 3 | scope=all false positive job title | `selected_search_tags=["position"]` |
| 4 | Scope inconsistent batch-to-batch | Chốt scope=position cho mọi snapshot |

## Stack & Anti-stuck

- **Browser control:** Claude in Chrome extension (`mcp__Claude_in_Chrome__javascript_tool`)
- **Form mutation:** Vue `form.__vue__.filters.{name}.value = X` direct
- **API capture:** `XMLHttpRequest.prototype.open/send` override → `window._apiResp` buffer
- **Persistence:** `localStorage["topcv_crawl_results_v3"]` (crash-safe), full script trong `localStorage.TOPCV_CRAWLER_SCRIPT`
- **Btn-unstick observer:** `setInterval` 1s, force reset `disabled+btn-loading` sau 8s
- **429 cooldown:** 5 phút, max 4 retries → auto-skip nếu exhausted

## Ước tính thời gian chạy

| Pha | Thời gian |
|---|---|
| Setup (login + inject script) | ~5 phút |
| Crawl 1,323 cells (21 ngành × 63 tỉnh, direct fetch ~10/min) | **~2-3 giờ** |
| Retry timeout cells | ~15 phút |
| Export Excel | <1 phút |
| **Tổng** | **~3-4 giờ** |

## Output

Sheet `TopCV` trong `CV_Count_Tracker.xlsx` — long format **chỉ 5 cột** (không có cấp bậc breakdown):

| Date | Ngành | Địa điểm | CV count | Note |
|---|---|---|---|---|
| 2026-05-27 | Kế toán / Kiểm toán | Hà Nội | 32,241 | |
| 2026-05-27 | Điện / Điện tử / ... | Hà Giang | | 429_FORCE_SKIP |

→ Dashboard cần handle đặc biệt TopCV không có cấp breakdown (Wave 4 Phase C).

## Snapshot đầu tiên (2026-05-27)

- 1,197 cells | 1,152 có data (96.2%) | 45 timeout cần retry
- **642,469 CVs total** counted
- Top 5: Kế toán (119K), Bán hàng/Kinh doanh (114K), Nhân sự (56K), Bán lẻ (45K), Marketing (45K)

## Những lỗi đã gặp — không lặp lại

| Vấn đề | Cách fix |
|---|---|
| **🆕 Locations silent fail** (HCM = 4,896 thay vì 41,744 ~8.5x miss) | Phải dùng slug `["location:hcm"]` từ Vue dataOptions, KHÔNG dùng Vietnamese name. Backend không reject sai format — status=success nhưng total fuzzy match. Scrape slug từ multiselect, KHÔNG auto-derive |
| **🆕 Phantom "verified" claim** trong config JSON | Mọi field "verified" phải kèm test code chạy được + assertion. Không claim phantom |
| **🆕 Pattern auto-derive slug sai** | Slug = arbitrary code (HCM=hcm, không phải hochiminh). Phải scrape từ source UI |
| 3.5s wait → chip stale read | XHR hook chờ actual API response (`window._apiResp`) |
| Button stuck `disabled+btn-loading` ~100 cells | btn-unstick observer setInterval 1s, force reset sau 8s |
| Page reload → JS context die → crawler chết | Save full script vào `localStorage.TOPCV_CRAWLER_SCRIPT`, eval lại |
| 429 hit liên tục cùng cell | Cooldown 5 phút (patched từ 2 phút), max 4 retries → auto-skip |
| Wrote `0` cho timeout (sai) | Strict: `0` chỉ khi UI hiện "Không tìm thấy CV". Timeout → `total=null + note` |
| Crawler stuck retrying same cell forever | `donePairs` include ALL processed (cả success + timeout) |
| Set wakeup 25 phút → page reload không ai re-inject | Monitor mỗi 4-5 phút (giữ cache warm) |
| Vue v-model setter + 'input' event không sync | Direct mutation `form.__vue__.filters.{name}.value = X` |

---

## Cài đặt

```bash
py -m pip install requests beautifulsoup4 openpyxl playwright
py -m playwright install chromium
```

**Lấy cookie lần đầu (per site):**
```bash
py setup_cookies.py                       # CareerViet
py vietnamworks/setup_cookies_vnw.py      # VietnamWorks
py vieclam24h/setup_cookies_vl24h.py     # Vieclam24h
```

**Đăng ký Task Scheduler (1 lần):**
```powershell
.\setup_scheduler.ps1
```

**Chạy thủ công:**
```bash
py main.py
```
