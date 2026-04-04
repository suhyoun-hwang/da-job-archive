import logging
import time

import requests

logger = logging.getLogger(__name__)

API_URL = "https://career-api.rememberapp.co.kr/job_postings/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Origin": "https://career.rememberapp.co.kr",
    "Referer": "https://career.rememberapp.co.kr/",
}

PER_PAGE = 20
DELAY = 1.0

TITLE_KEYWORDS = ("analyst", "analytics", "분석가", "분석", "애널리스트")


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TITLE_KEYWORDS)


def fetch_jobs() -> list[dict]:
    jobs = []
    page = 1

    while True:
        resp = requests.post(
            API_URL,
            headers=HEADERS,
            json={
                "page": page,
                "per": PER_PAGE,
                "search": {
                    "job_category_names": [{"level1": "AI·데이터", "level2": "데이터 분석가"}],
                    "organization_type": "without_headhunter",
                },
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            title = item.get("title", "")
            if not _is_relevant(title):
                continue

            org = item.get("organization") or {}
            addresses = item.get("addresses") or []
            location = ""
            if addresses:
                a = addresses[0]
                parts = [a.get("address_level1", ""), a.get("address_level2", "")]
                location = " ".join(p for p in parts if p)

            jobs.append(
                {
                    "id": f"remember_{item['id']}",
                    "title": title,
                    "company": org.get("name", ""),
                    "url": f"https://career.rememberapp.co.kr/job/posting/{item['id']}",
                    "location": location,
                    "source": "remember",
                }
            )

        meta = data.get("meta", {})
        if page >= meta.get("total_pages", 1):
            break

        page += 1
        time.sleep(DELAY)

    if not jobs:
        logger.warning("Remember 수집 결과 0건 — API 구조 변경 확인 필요")

    return jobs
