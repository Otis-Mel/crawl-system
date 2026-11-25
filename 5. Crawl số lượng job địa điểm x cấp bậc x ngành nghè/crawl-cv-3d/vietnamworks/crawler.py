import sys
import time
import requests

sys.stdout.reconfigure(encoding="utf-8")

from vietnamworks.auth import GQL_URL
from vietnamworks.excel_vnw import get_today_done_pairs, append_rows

DELAY_SECONDS   = 0.4
REQUEST_TIMEOUT = 15
MAX_RETRIES     = 3

CHECKPOINT_EVERY = 200

_GQL_COUNT = """
query Count($f: String!) {
  searchES(
    algoliaFilter: {
      filters: $f
      page: 0
      hitsPerPage: 1
      restrictSearchableAttributes: ""
    }
    locale: "vn"
  ) {
    nbHits
  }
}
"""


def _query(session: requests.Session, filters: str) -> int | None:
    body = {"query": _GQL_COUNT, "variables": {"f": filters}}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.post(GQL_URL, json=body, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errors"):
                    msg = data["errors"][0].get("message", "unknown")
                    print(f"  [crawler] GQL error (lần {attempt}): {msg}")
                else:
                    return data["data"]["searchES"]["nbHits"]
            else:
                print(f"  [crawler] HTTP {resp.status_code} (lần {attempt})")
        except Exception as e:
            print(f"  [crawler] Lỗi: {e} (lần {attempt})")
        time.sleep(DELAY_SECONDS)
    return None


def _crawl_sheet(
    session:    requests.Session,
    sheet_name: str,
    dim_items:  list[dict],
    locations:  list[dict],
    cap_bac:    list[dict],
    probe_filter_fn,
    detail_filter_fn,
) -> None:
    """
    Crawl 1 sheet 3D: dim × location × cap_bac.
    probe_filter_fn(dim_id, loc_id) → filter string không có jobLevelId.
    detail_filter_fn(dim_id, loc_id, cb_id) → filter string đầy đủ.
    """
    cap_bac_names = [cb["name"] for cb in cap_bac]
    done_pairs    = get_today_done_pairs(sheet_name)
    if done_pairs:
        print(f"[vnw] {sheet_name} resume: đã có {len(done_pairs)} cặp — skip", flush=True)

    total      = len(dim_items) * len(locations)
    done_count = len(done_pairs)
    buffer: list[dict] = []

    for item in dim_items:
        for loc in locations:
            if (item["name"], loc["name"]) in done_pairs:
                continue

            probe = _query(session, probe_filter_fn(item["id"], loc["id"]))
            time.sleep(DELAY_SECONDS)

            if probe == 0:
                counts = {cb["name"]: 0 for cb in cap_bac}
            else:
                counts = {}
                for cb in cap_bac:
                    f = detail_filter_fn(item["id"], loc["id"], cb["id"])
                    count = _query(session, f)
                    counts[cb["name"]] = count if count is not None else 0
                    time.sleep(DELAY_SECONDS)

            done_count += 1
            buffer.append({
                "industry": item["name"],
                "location": loc["name"],
                "counts":   counts,
            })
            total_cv = sum(counts.values())
            print(
                f"  [{done_count}/{total}] {item['name'][:22]} × {loc['name'][:18]}: "
                f"probe={probe or 0} → {total_cv:,}",
                flush=True,
            )

            if len(buffer) >= CHECKPOINT_EVERY:
                append_rows(sheet_name, buffer, cap_bac_names)
                buffer.clear()

    if buffer:
        append_rows(sheet_name, buffer, cap_bac_names)


def crawl_all(
    session:         requests.Session,
    linh_vuc_list:   list[dict],
    nganh_nghe_list: list[dict],
    dia_diem_list:   list[dict],
    cap_bac_list:    list[dict],
) -> None:
    """
    Crawl 2 sheet 3D:
      VietnamWorks_LV    — Lĩnh vực × Địa điểm × Cấp bậc
      VietnamWorks_Ngành — Ngành nghề × Địa điểm × Cấp bậc

    Filter syntax (verified qua intercept browser):
      Lĩnh vực probe:   expectedIndustryV3Ids:(id) AND expectedWorkingLocation.cityId:(loc)
      Ngành nghề probe: expectedjobFunctionV3Id:(id) AND expectedWorkingLocation.cityId:(loc)
      Detail:           ... AND jobLevelId:{cb_id}
    """
    print(f"[vnw] Crawl VietnamWorks_LV ({len(linh_vuc_list)} LV × {len(dia_diem_list)} ĐĐ)...", flush=True)
    _crawl_sheet(
        session,
        sheet_name="VietnamWorks_LV",
        dim_items=linh_vuc_list,
        locations=dia_diem_list,
        cap_bac=cap_bac_list,
        probe_filter_fn=lambda lv_id, loc_id:
            f"expectedIndustryV3Ids:({lv_id}) AND expectedWorkingLocation.cityId:({loc_id})",
        detail_filter_fn=lambda lv_id, loc_id, cb_id:
            f"expectedIndustryV3Ids:({lv_id}) AND expectedWorkingLocation.cityId:({loc_id}) AND jobLevelId:{cb_id}",
    )

    print(f"\n[vnw] Crawl VietnamWorks_Ngành ({len(nganh_nghe_list)} Ngành × {len(dia_diem_list)} ĐĐ)...", flush=True)
    _crawl_sheet(
        session,
        sheet_name="VietnamWorks_Ngành",
        dim_items=nganh_nghe_list,
        locations=dia_diem_list,
        cap_bac=cap_bac_list,
        probe_filter_fn=lambda nn_id, loc_id:
            f"expectedjobFunctionV3Id:({nn_id}) AND expectedWorkingLocation.cityId:({loc_id})",
        detail_filter_fn=lambda nn_id, loc_id, cb_id:
            f"expectedjobFunctionV3Id:({nn_id}) AND expectedWorkingLocation.cityId:({loc_id}) AND jobLevelId:{cb_id}",
    )
