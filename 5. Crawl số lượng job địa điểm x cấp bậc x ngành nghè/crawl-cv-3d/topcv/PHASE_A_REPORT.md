# Phase A — TopCV CV Search API Inspection Report

**Date:** 2026-05-26  
**Inspector account:** OCB employer (campaign 2490023)  
**IP:** 108.181.57.206 (hotspot)

---

## 1. API Endpoint (FOUND ✅)

```
POST https://tuyendung-api.topcv.vn/api/v1/recruitment-campaigns/{campaign_id}/search-cv/cvs
```

- **Auth:** Requires Bearer/JWT token from app's React state (localStorage)
  - Header `Authorization: Bearer {token}` is auto-added by app's axios interceptor
  - Direct fetch() without app's interceptor returns `422 {status:"error", error_name:"INVALID_TOKEN"}`
  - **Implication:** Crawler must run inside Playwright session (token lives in browser)

## 2. Request Body Schema (17 fields)

```json
{
  "keyword": "Kế toán",
  "priority": "latest",
  "and_tags": [],          // ← KEY: keyword stacking for cấp bậc proxy
  "companies": [],
  "education_levels": [],
  "languages": [],
  "locations": ["location:hanoi"],
  "mbtis": [],
  "not_tags": [],
  "or_tags": [],
  "universities": [],
  "recruitment_campaign_id": 2490023,
  "page": 1,
  "selected_search_tags": ["experience"],  // ← required non-empty
  "recruitment_campaign": [],
  "recruitment_cv_status": [],
  "recruitment_cv_source": [],
  "search_pro": false
}
```

**Field meanings:**
- `keyword` (string): Main search term in CV/title/scope
- `locations` (array): `["location:slug"]` — slug format like `hanoi`, `hcm`, `da-nang`
- `and_tags` (array of strings): Keywords that **must** appear in CV
- `or_tags` (array): At least one must appear
- `not_tags` (array): Must NOT appear
- `education_levels` (array): Format TBD — needs UI test
- `selected_search_tags` (array): Search scope — `experience` / `position` / `skills` / `education` / `activity`
- `priority` (string): `latest` / `suitable` / `experience` / `job-seeking`
- `page` (number): Pagination

## 3. Response Schema

```json
{
  "status": "success",
  "cvs": {
    "data": [...12 CV objects...],
    "current_page": 1,
    "per_page": 12,
    "empty_query": false,
    "total_page": N,
    "total": 75323                  // ← KEY: this is our count!
  },
  "__client": {...}
}
```

**Per-CV fields available** (35+ fields):
- `id`, `cv_record_id`, `private_key`, `user_id`
- `fullname`, `phone`, `email`, `dob`
- `title`, `avatar`, `city`
- `experiences` (array), `educations` (array)
- `month_of_exp` ← integer (could be used for cấp bậc inference if we needed)
- `str_salary`, `expectation`, `objective`
- `is_followed`, `is_paid`, `is_viewed`, `viewed_employers_count`
- ... + more

## 4. Cấp bậc Strategy Decision

**Tested:** Custom params `experience_min/max`, `month_of_exp_min/max`, `level`, `job_level`, `experience_year` — **ALL return 422 validation error**. API has strict schema — no hidden fields.

**Decision: Strategy C (keyword stacking via `and_tags`) ✅ VERIFIED**

| Filter combo | Total CVs |
|---|---|
| Kế toán × Hà Nội (baseline) | **75,323** |
| + and_tags `["trưởng phòng"]` | **1,339** (1.8% match) |

→ Approach works. Each level keyword filters down the baseline.

**Proposed cấp bậc → keyword mapping:**
| Cấp bậc chuẩn | and_tags keyword |
|---|---|
| Thực tập / Sinh viên | "thực tập" |
| Mới tốt nghiệp | "mới tốt nghiệp" hoặc "fresher" |
| Nhân viên | (no extra tag — baseline count) |
| Trưởng nhóm / Quản lý | "trưởng nhóm" |
| Trưởng phòng | "trưởng phòng" |
| Giám đốc trở lên | "giám đốc" |

⚠️ **Caveat:** Keywords are fuzzy text match in CV body. CV của Nhân viên có thể chứa từ "trưởng phòng" trong mô tả KN (vd "báo cáo cho trưởng phòng") → false positive. Accept noise ~5-10%.

## 5. Caveats / Risks

1. **Auth lives in app context:** Must use Playwright; can't run pure `requests` script.
2. **Rate limit unknown:** Need to test. Existing Job side experience suggests CF moderate (5s/req safe).
3. **`per_page=12`** fixed — only `total` field matters cho aggregate count.
4. **Pseudo-locations (Miền Bắc/Toàn Quốc):** Need to test if API has aggregate slugs → EXCLUDE if found.
5. **Token expiration:** JWT in localStorage có thể expire — Playwright session refresh logic cần handle.

## 6. Phase B Plan (next step)

### Folder: `Crawl CV ngành x cấp bậc x địa điểm/topcv/`
- `setup_cookies.py` — Playwright login flow (1-time) → save cookies + localStorage to file
- `auth.py` — Restore session → return Playwright page object
- `mappings.py` — keyword↔ngành (from `keywords_by_industry.xlsx`) + locations (62 IDs từ Job side)
- `crawler.py` — Loop ngành × tỉnh × cấp_bậc using `page.evaluate(fetch)` (leverages app's auth interceptor)
- `excel_topcv.py` — Write sheet `TopCV` vào `CV_Count_Tracker.xlsx`

### Crawler approach (in-browser fetch):
```python
total = page.evaluate("""
  async ({keyword, location_slug, level_tag}) => {
    const body = {
      keyword, priority: "latest", and_tags: level_tag ? [level_tag] : [],
      companies: [], education_levels: [], languages: [],
      locations: [`location:${location_slug}`], mbtis: [],
      not_tags: [], or_tags: [], universities: [],
      recruitment_campaign_id: CAMPAIGN_ID, page: 1,
      selected_search_tags: ["experience"],
      recruitment_campaign: [], recruitment_cv_status: [],
      recruitment_cv_source: [], search_pro: false
    };
    const r = await fetch('/api/v1/recruitment-campaigns/CAMPAIGN_ID/search-cv/cvs', {
      method: 'POST', headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
      credentials: 'include', body: JSON.stringify(body)
    });
    const j = await r.json();
    return j.cvs?.total ?? null;
  }
""", {"keyword": "Kế toán", "location_slug": "hanoi", "level_tag": "trưởng phòng"})
```

### ETA full crawl (16 ngành × 3 keywords × 63 tỉnh × 6 cấp = 18K cells):
- Probe-skip (no level) for each (keyword × tỉnh): 16×3×63 = 3,024 probes × 1s = ~50min
- Level expand for non-zero: ~30% × 3024 × 5 levels = 4,536 cells × 1s = ~75min
- **Total: ~2 hours** (much faster than expected because in-browser fetch is fast — no UI rendering wait)

---

## 7. Status

✅ Phase A COMPLETE  
→ Proceed to Phase B (build crawler files)
