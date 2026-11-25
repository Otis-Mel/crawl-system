"""
Vieclam24h crawler — CSR/API pattern.

Mỗi request:
  GET https://apiv2.vieclam24h.vn/seeker/fe/api/v1/search/ai-resume?<params>
  → parse JSON: response["data"]["total_items"]

Auth: Authorization: Bearer <re_access_token> (lấy từ cookies.json)

Filters dùng (dạng PHP array với index 0):
  - occupation_ids[0]=<id>   (Ngành nghề)
  - province_ids[0]=<id>     (Địa điểm)
  - experience[0]=<value>    (Kinh nghiệm — chỉ dùng trong detail pass)

Probe-then-detail: query không có experience[0] trước.
Nếu total=0 → ghi 0 cho mọi mức KN, tiết kiệm 8 requests/combo.
"""
import sys
import time
import requests

sys.stdout.reconfigure(encoding="utf-8")

from vieclam24h.auth import API_URL
from vieclam24h.excel_vl24h import get_today_done_pairs, append_rows

DELAY_SECONDS   = 0.5
REQUEST_TIMEOUT = 20
MAX_RETRIES     = 3

CHECKPOINT_EVERY = 200

_BASE_PARAMS = {"per_page": 1, "action": "loadmore"}


def _fetch_count(
    session: requests.Session,
    occupation_id: int | None = None,
    province_id:   int | None = None,
    experience:    str | None = None,
) -> int | None:
    params = dict(_BASE_PARAMS)
    if occupation_id is not None:
        params["occupation_ids[0]"] = str(occupation_id)
    if province_id is not None:
        params["province_ids[0]"] = str(province_id)
    if experience is not None:
        params["experience[0]"] = str(experience)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") in (1, 200):
                    return data["data"]["total_items"]
                print(f"  [crawler] API error (lần {attempt}): {data.get('msg')}", flush=True)
            else:
                print(f"  [crawler] HTTP {resp.status_code} (lần {attempt})", flush=True)
        except Exception as e:
            print(f"  [crawler] Lỗi: {e} (lần {attempt})", flush=True)
        time.sleep(DELAY_SECONDS)
    return None


def crawl_all(
    session:    requests.Session,
    nganh_nghe: list[dict],
    dia_diem:   list[dict],
    kinh_nghiem: list[dict],
    limit: int | None = None,
) -> None:
    """
    Crawl 3D: Ngành × Địa điểm × Kinh nghiệm với probe-then-detail.
    Checkpoint mỗi CHECKPOINT_EVERY hàng. Resume tự động.
    """
    kn_names = [kn["name"] for kn in kinh_nghiem]

    occ_list = nganh_nghe[:limit] if limit else nganh_nghe
    loc_list = dia_diem[:limit]   if limit else dia_diem

    done_pairs = get_today_done_pairs()
    if done_pairs:
        print(f"[vl24h] Resume: đã có {len(done_pairs)} cặp (Ngành × ĐĐ) hôm nay — skip", flush=True)

    total      = len(occ_list) * len(loc_list)
    done_count = len(done_pairs)
    buffer: list[dict] = []

    print(f"[vl24h] Crawl VL24h ({len(occ_list)} Ngành × {len(loc_list)} ĐĐ × {len(kinh_nghiem)} KN)...", flush=True)

    for occ in occ_list:
        for loc in loc_list:
            if (occ["name"], loc["name"]) in done_pairs:
                continue

            probe = _fetch_count(session, occupation_id=occ["id"], province_id=loc["id"])
            time.sleep(DELAY_SECONDS)

            if probe == 0:
                counts = {kn["name"]: 0 for kn in kinh_nghiem}
            else:
                counts = {}
                for kn in kinh_nghiem:
                    count = _fetch_count(
                        session,
                        occupation_id=occ["id"],
                        province_id=loc["id"],
                        experience=kn["value"],
                    )
                    counts[kn["name"]] = count if count is not None else 0
                    time.sleep(DELAY_SECONDS)

            done_count += 1
            buffer.append({
                "industry": occ["name"],
                "location": loc["name"],
                "counts":   counts,
            })
            total_cv = sum(counts.values())
            print(
                f"  [{done_count}/{total}] {occ['name'][:22]} × {loc['name'][:18]}: "
                f"probe={probe or 0} → {total_cv:,}",
                flush=True,
            )

            if len(buffer) >= CHECKPOINT_EVERY:
                append_rows(buffer, kn_names)
                buffer.clear()

    if buffer:
        append_rows(buffer, kn_names)
