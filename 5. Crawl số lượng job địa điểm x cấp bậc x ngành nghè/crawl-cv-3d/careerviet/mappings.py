import requests

INDUSTRY_API = "https://internal-api.careerviet.vn/api/v1/cs/jsk/industries/groups/list"
LOCATION_API = "https://internal-api.careerviet.vn/api/v1/cs/jsk/locations"
LEVEL_API    = "https://internal-api.careerviet.vn/api/v1/cs/jsk/levels/searches"


def fetch_levels(session: requests.Session) -> list[dict]:
    """[{"id": 1, "name": "Intern"}, ...]"""
    resp = session.get(LEVEL_API, timeout=10)
    return [
        {"id": item["level_id"], "name": item["level_name_vn"]}
        for item in resp.json().get("data", [])
    ]


def fetch_industries(session: requests.Session) -> list[dict]:
    """[{"id": 4, "name": "Tiếp thị / Marketing"}, ...]"""
    resp = session.get(INDUSTRY_API, timeout=10)
    industries = []
    for group in resp.json().get("data", []):
        for item in group.get("industries", []):
            industries.append({
                "id":   item["industry_id"],
                "name": item["industry_name_vn"],
            })
    return industries


def fetch_locations(session: requests.Session) -> list[dict]:
    """[{"id": 8, "name": "Ho Chi Minh"}, ...] — chỉ Việt Nam (country_id=1)"""
    resp = session.get(LOCATION_API, timeout=10)
    locations = []
    for country in resp.json().get("data", {}).get("results", []):
        if country.get("country_id") != 1:
            continue
        for item in country.get("locations", []):
            locations.append({
                "id":   item["location_id"],
                "name": item["location_name"],
            })
    return locations
