import requests

WANTED_BASE_URL = "https://www.wanted.co.kr"
WANTED_API_URL = f"{WANTED_BASE_URL}/api/v4/jobs"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "wanted-user-agent": "user-web",
    "Accept": "application/json",
    "Referer": "https://www.wanted.co.kr/",
}

PARAMS = {
    "country": "kr",
    "job_sort": "job.latest_order",
    "locations": "all",
    "years": -1,
    "limit": 100,
    "tag_type_ids": 656,  # 데이터 분석가 카테고리 (wdlist/507/656)
}

TITLE_KEYWORDS = (
    "analyst", "analytics", "분석가", "분석", "애널리스트",
)


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TITLE_KEYWORDS)


def fetch_jobs() -> list[dict]:
    jobs = []
    offset = 0

    while True:
        params = {**PARAMS, "offset": offset}
        resp = requests.get(WANTED_API_URL, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            title = item.get("position", "")
            if not _is_relevant(title):
                continue
            address = item.get("address") or {}
            jobs.append(
                {
                    "id": f"wanted_{item['id']}",
                    "title": title,
                    "company": (item.get("company") or {}).get("name", ""),
                    "url": f"{WANTED_BASE_URL}/wd/{item['id']}",
                    "location": address.get("location", ""),
                    "source": "wanted",
                }
            )

        next_link = (data.get("links") or {}).get("next")
        if not next_link:
            break
        offset += len(items)

    return jobs
