import time
import requests
from config import DELAY_SECONDS, REQUEST_TIMEOUT, MAX_RETRIES
from excel_writer import get_today_done_pairs, append_rows

API_URL = "https://internal-api.careerviet.vn/api/v1/jss/emp/resumes/hr-centrals"

CHECKPOINT_EVERY = 200


def _post(session: requests.Session, body: dict) -> int | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.post(API_URL, json=body, timeout=REQUEST_TIMEOUT)
            if resp.status_code in (200, 201):
                return resp.json().get("metadata", {}).get("itemCount", 0)
            print(f"  [crawler] HTTP {resp.status_code} (lần {attempt}) — {body}")
        except Exception as e:
            print(f"  [crawler] Lỗi: {e} (lần {attempt})")
        time.sleep(DELAY_SECONDS)
    return None


def crawl_all(
    session: requests.Session,
    industries: list[dict],
    locations: list[dict],
    levels: list[dict],
) -> None:
    """
    Crawl 3D: industry × location × level với probe-then-detail.
    - Probe pass (không có level): nếu total=0 thì ghi 0 cho mọi level, tiết kiệm N requests.
    - Checkpoint mỗi CHECKPOINT_EVERY hàng.
    - Resume tự động: đọc done_pairs từ Excel, skip pairs đã crawl hôm nay.
    """
    level_names = [lv["name"] for lv in levels]
    done_pairs  = get_today_done_pairs()
    if done_pairs:
        print(f"[crv] Resume: đã có {len(done_pairs)} cặp (Ngành × ĐĐ) hôm nay — skip", flush=True)

    total      = len(industries) * len(locations)
    done_count = len(done_pairs)
    buffer: list[dict] = []

    for ind in industries:
        for loc in locations:
            if (ind["name"], loc["name"]) in done_pairs:
                continue

            probe_body = {
                "industry_ids": [ind["id"]],
                "location_ids": [{"location_id": loc["id"]}],
                "limit":  1,
                "order":  "desc",
                "sort_by": "",
            }
            probe = _post(session, probe_body)
            time.sleep(DELAY_SECONDS)

            if probe == 0:
                counts = {lv["name"]: 0 for lv in levels}
            else:
                counts = {}
                for lv in levels:
                    body = {
                        "industry_ids": [ind["id"]],
                        "location_ids": [{"location_id": loc["id"]}],
                        "level_id": lv["id"],
                        "limit":  1,
                        "order":  "desc",
                        "sort_by": "",
                    }
                    count = _post(session, body)
                    counts[lv["name"]] = count if count is not None else 0
                    time.sleep(DELAY_SECONDS)

            done_count += 1
            buffer.append({
                "industry": ind["name"],
                "location": loc["name"],
                "counts":   counts,
            })
            total_cv = sum(counts.values())
            print(
                f"  [{done_count}/{total}] {ind['name'][:22]} × {loc['name'][:18]}: "
                f"probe={probe or 0} → {total_cv:,}",
                flush=True,
            )

            if len(buffer) >= CHECKPOINT_EVERY:
                append_rows(buffer, level_names)
                buffer.clear()

    if buffer:
        append_rows(buffer, level_names)
