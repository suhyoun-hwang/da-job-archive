import logging
from scrapers.wanted import fetch_jobs as fetch_wanted_jobs
from scrapers.linkedin import fetch_jobs as fetch_linkedin_jobs
from scrapers.remember import fetch_jobs as fetch_remember_jobs
from classify import classify_all
from db import save_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SCRAPERS = [
    ("원티드", fetch_wanted_jobs),
    ("링크드인", fetch_linkedin_jobs),
    ("리멤버", fetch_remember_jobs),
]


def collect():
    for name, scraper in SCRAPERS:
        logger.info("수집 시작 — %s 데이터 분석가 공고", name)
        try:
            jobs = scraper()
            inserted = save_jobs(jobs)
            logger.info("%s 완료: 전체 %d건 중 신규 %d건 저장", name, len(jobs), inserted)
        except Exception as e:
            logger.error("%s 수집 오류: %s", name, e)

    logger.info("회사 규모/업종 분류 시작")
    try:
        classify_all()
    except Exception as e:
        logger.error("분류 오류: %s", e)


if __name__ == "__main__":
    collect()
