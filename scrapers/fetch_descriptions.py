"""
공고 URL에서 상세 내용(description)을 수집하여 DB에 저장.
소스별로 다른 방식 사용:
  - wanted: REST API JSON
  - remember: REST API JSON
  - linkedin: Playwright 헤드리스 브라우저 (봇 탐지 우회)
"""
from __future__ import annotations

import logging
import random
import sqlite3
import time

import requests

from db import DB_PATH, init_db

logger = logging.getLogger(__name__)

WANTED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Wanted-User-Country": "KR",
    "Wanted-User-Language": "ko",
    "Accept": "application/json",
    "Referer": "https://www.wanted.co.kr/",
}

REMEMBER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://career.rememberapp.co.kr",
    "Referer": "https://career.rememberapp.co.kr/",
}


def _fetch_wanted(job_id: str) -> str | None:
    """wanted_{숫자} → API 호출 → 텍스트 반환"""
    numeric_id = job_id.removeprefix("wanted_")
    try:
        r = requests.get(
            f"https://www.wanted.co.kr/api/v4/jobs/{numeric_id}",
            headers=WANTED_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning("Wanted %s: HTTP %d", job_id, r.status_code)
            return None
        detail = r.json().get("job", {}).get("detail", {})
        parts = [
            detail.get("intro", ""),
            detail.get("main_tasks", ""),
            detail.get("requirements", ""),
            detail.get("preferred_points", ""),
            detail.get("benefits", ""),
        ]
        return "\n\n".join(p for p in parts if p).strip() or None
    except Exception as e:
        logger.warning("Wanted %s 오류: %s", job_id, e)
        return None


def _fetch_remember(job_id: str) -> str | None:
    """remember_{숫자} → API 호출 → 텍스트 반환"""
    numeric_id = job_id.removeprefix("remember_")
    try:
        r = requests.get(
            f"https://career-api.rememberapp.co.kr/job_postings/{numeric_id}",
            headers=REMEMBER_HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning("Remember %s: HTTP %d", job_id, r.status_code)
            return None
        job = r.json().get("data", {})
        parts = [
            job.get("introduction", ""),
            job.get("job_description", ""),
            job.get("qualifications", ""),
            job.get("preferred_qualifications", ""),
        ]
        return "\n\n".join(p for p in parts if p).strip() or None
    except Exception as e:
        logger.warning("Remember %s 오류: %s", job_id, e)
        return None


def _fetch_linkedin_batch(jobs: list[tuple[str, str]]) -> dict[str, str]:
    """LinkedIn 공고 목록을 Playwright 브라우저 하나로 순차 방문하여 description 반환.

    jobs: list of (job_id, url)
    returns: {job_id: description}
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    results: dict[str, str] = {}

    SELECTORS = [
        "div#job-details",
        "div.description__text",
        "div.show-more-less-html__markup",
        "section.description",
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1280, "height": 900},
        )
        # navigator.webdriver = false 처리
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        for job_id, url in jobs:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                # "더 보기" 버튼이 있으면 클릭하여 전체 내용 펼치기
                try:
                    page.click(
                        "button.show-more-less-html__button--more, "
                        "button[aria-label*='더 보기'], button[aria-label*='See more']",
                        timeout=3000,
                    )
                except PWTimeout:
                    pass

                text = None
                for selector in SELECTORS:
                    el = page.query_selector(selector)
                    if el:
                        text = el.inner_text().strip()
                        break

                if text:
                    results[job_id] = text
                    logger.info("LinkedIn %s: %d자 수집", job_id, len(text))
                else:
                    logger.warning("LinkedIn %s: 본문 셀렉터 미매칭", job_id)

            except PWTimeout:
                logger.warning("LinkedIn %s: 페이지 로드 타임아웃", job_id)
            except Exception as e:
                logger.warning("LinkedIn %s 오류: %s", job_id, e)

            time.sleep(random.uniform(3, 7))

        browser.close()

    return results


def fetch_all_descriptions() -> None:
    """description이 없는 모든 공고를 소스별로 수집하여 DB 업데이트"""
    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        rows = conn.execute(
            "SELECT id, url, source FROM jobs WHERE description IS NULL ORDER BY source, id"
        ).fetchall()

    if not rows:
        logger.info("수집할 description 없음 (전부 완료)")
        return

    logger.info("description 수집 시작: %d건", len(rows))

    updated = 0

    # Wanted / Remember: requests로 개별 수집
    for job_id, url, source in rows:
        desc = None
        if source == "wanted":
            desc = _fetch_wanted(job_id)
            time.sleep(random.uniform(0.5, 1.5))
        elif source == "remember":
            desc = _fetch_remember(job_id)
            time.sleep(random.uniform(0.5, 1.5))
        else:
            continue

        if desc:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("UPDATE jobs SET description=? WHERE id=?", (desc, job_id))
                conn.commit()
            updated += 1

    # LinkedIn: Playwright로 배치 수집
    linkedin_jobs = [(job_id, url) for job_id, url, source in rows if source == "linkedin"]
    if linkedin_jobs:
        logger.info("LinkedIn Playwright 수집 시작: %d건", len(linkedin_jobs))
        linkedin_results = _fetch_linkedin_batch(linkedin_jobs)
        with sqlite3.connect(DB_PATH) as conn:
            for job_id, desc in linkedin_results.items():
                conn.execute("UPDATE jobs SET description=? WHERE id=?", (desc, job_id))
            conn.commit()
        updated += len(linkedin_results)

    logger.info("description 수집 완료: %d/%d건 성공", updated, len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    fetch_all_descriptions()
