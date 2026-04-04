# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 가상환경 활성화
source venv/bin/activate

# 수집 즉시 실행 (원티드 + 링크드인, 이후 매일 09:00 KST 자동 수집)
python main.py

# 스크래퍼 단독 테스트
python -c "from scrapers.wanted import fetch_jobs; jobs = fetch_jobs(); print(len(jobs))"
python -c "from scrapers.linkedin import fetch_jobs; jobs = fetch_jobs(); print(len(jobs))"

# DB 쿼리
sqlite3 jobs.db
jupyter notebook explore.ipynb
```

## Architecture

**데이터 흐름:** `scrapers/*.py` → `db.save_jobs()` → `jobs.db`

- **`scrapers/wanted.py`** — 원티드 API(`/api/v4/jobs`) 호출. `tag_type_ids=656`(데이터 분석가 카테고리), `links.next` 유무로 페이지네이션 종료 판단.
- **`scrapers/naver.py`** — 네이버 채용 검색 API(`/p/c/career/search.naver`, `api_type=1`) 호출. JSON 응답 안에 HTML이 포함된 구조로, BeautifulSoup으로 파싱. 헤드헌팅사가 공고를 등록하는 구조라 company 필드가 실제 회사가 아닌 헤드헌팅사일 수 있음. id는 URL의 MD5 해시.
- **`scrapers/linkedin.py`** — LinkedIn Guest API(`/jobs-guest/jobs/api/seeMoreJobPostings/search`) HTML 파싱. `start` 파라미터로 25건씩 페이지네이션. 403/429 응답 시 수집 중단. 0건 반환 시 HTML 구조 변경 의심.
- **`db.py`** — `init_db()`는 `save_jobs()` 호출 시 자동 실행. `INSERT OR IGNORE`로 중복 제거 (PK: `id`).
- **`main.py`** — 실행 시 즉시 수집 후 APScheduler `BlockingScheduler`로 매일 09:00(Asia/Seoul) 반복. `SCRAPERS` 리스트에 스크래퍼 추가하면 자동으로 포함됨.

## DB 스키마

```
jobs(id TEXT PK, title, company, url, location, source, collected_at)
```

- `id` 형식: `wanted_{숫자}`, `linkedin_{숫자}`, `naver_{md5해시12자리}`
- `source`: `"wanted"` | `"linkedin"` | `"naver"`

## 새 스크래퍼 추가 방법

1. `scrapers/{source}.py` 작성 — `fetch_jobs() -> list[dict]` 인터페이스 구현 (반환 키: `id`, `title`, `company`, `url`, `location`, `source`)
2. `main.py`의 `SCRAPERS` 리스트에 추가

## 주의사항

- LinkedIn 스크래퍼는 HTML 파싱 방식이라 LinkedIn 프론트엔드 변경 시 0건 반환 가능 → `scrapers/linkedin.py`의 CSS 클래스명 확인 필요
- 원티드 `tag_type_ids=656`은 원티드 사이트 `/wdlist/507/656` 카테고리 ID. `query` 파라미터 방식은 30건으로 제한됨
