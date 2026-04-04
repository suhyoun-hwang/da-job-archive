import logging
import time
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

PARAMS = {
    "keywords": "데이터 분석가",
    "location": "South Korea",
    "count": 25,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

MAX_PAGES = 10
DELAY = 2.0

TITLE_KEYWORDS = (
    "analyst", "analytics", "분석가", "분석",
)


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in TITLE_KEYWORDS)


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


def fetch_jobs() -> list[dict]:
    jobs = []
    session = requests.Session()

    for page in range(MAX_PAGES):
        start = page * 25
        resp = session.get(
            BASE_URL,
            headers=HEADERS,
            params={**PARAMS, "start": start},
            timeout=10,
        )

        if resp.status_code in (403, 429):
            logger.warning("LinkedIn 요청 차단 (status=%d), 수집 중단", resp.status_code)
            break

        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_="base-card")
        if not cards:
            break

        for card in cards:
            try:
                urn = card.get("data-entity-urn", "")
                job_id = urn.split(":")[-1]

                title_tag = card.find("h3", class_="base-search-card__title")
                title = title_tag.get_text(strip=True) if title_tag else ""

                company_tag = card.find("h4", class_="base-search-card__subtitle")
                company = company_tag.get_text(strip=True) if company_tag else ""

                link_tag = card.find("a", class_="base-card__full-link")
                url = _clean_url(link_tag["href"]) if link_tag else ""

                location_tag = card.find("span", class_="job-search-card__location")
                location = location_tag.get_text(strip=True) if location_tag else ""

                if not job_id or not title:
                    continue
                if not _is_relevant(title):
                    continue

                jobs.append(
                    {
                        "id": f"linkedin_{job_id}",
                        "title": title,
                        "company": company,
                        "url": url,
                        "location": location,
                        "source": "linkedin",
                    }
                )
            except Exception:
                continue

        time.sleep(DELAY)

    if not jobs:
        logger.warning("LinkedIn 수집 결과 0건 — HTML 구조 변경 확인 필요")

    return jobs
