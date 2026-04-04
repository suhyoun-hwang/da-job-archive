"""
회사명 기반으로 규모(company_size)와 업종(industry)을 Claude API로 분류.
이미 분류된 회사는 건너뜀.
"""
import json
import logging
import sqlite3

import anthropic
from dotenv import load_dotenv

load_dotenv()

from db import DB_PATH, init_db

logger = logging.getLogger(__name__)

BATCH_SIZE = 30

SIZE_LABELS = ("대기업", "중견기업", "스타트업", "기타")
INDUSTRY_LABELS = ("IT/SW", "금융/핀테크", "커머스/유통", "게임", "미디어/콘텐츠", "제조/화학", "컨설팅/리서치", "교육", "헬스케어", "기타")

PROMPT_TEMPLATE = """\
아래 한국 회사 목록의 각 회사에 대해 company_size와 industry를 분류해줘.

company_size 기준:
- 대기업: 삼성, LG, 현대, SK, 롯데, 카카오, 네이버, 쿠팡 등 대형 그룹사 및 계열사
- 중견기업: 매출 1000억~1조 수준의 안정적인 기업, 코스피/코스닥 상장사 다수 포함
- 스타트업: 설립 10년 이내이거나 벤처캐피탈 투자 중심의 성장 단계 기업
- 기타: 판단 불가

industry 기준 (하나만 선택):
IT/SW, 금융/핀테크, 커머스/유통, 게임, 미디어/콘텐츠, 제조/화학, 컨설팅/리서치, 교육, 헬스케어, 기타

회사 목록:
{companies}

JSON 배열로만 응답해. 다른 텍스트 없이:
[
  {{"name": "회사명", "company_size": "대기업|중견기업|스타트업|기타", "industry": "업종"}},
  ...
]"""


def _classify_batch(client: anthropic.Anthropic, companies: list[str]) -> dict[str, dict]:
    prompt = PROMPT_TEMPLATE.format(companies="\n".join(f"- {c}" for c in companies))
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    # JSON 블록 추출
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    results = json.loads(text)
    return {r["name"]: {"company_size": r["company_size"], "industry": r["industry"]} for r in results}


def classify_all():
    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        # 이미 분류된 회사의 신규 공고는 API 없이 DB에서 바로 복사
        conn.execute("""
            UPDATE jobs
            SET
                company_size = (SELECT company_size FROM jobs j2
                                WHERE j2.company = jobs.company AND j2.company_size IS NOT NULL LIMIT 1),
                industry     = (SELECT industry     FROM jobs j2
                                WHERE j2.company = jobs.company AND j2.industry     IS NOT NULL LIMIT 1)
            WHERE company_size IS NULL
              AND company IN (SELECT DISTINCT company FROM jobs WHERE company_size IS NOT NULL)
        """)
        conn.commit()
        # 진짜 신규 회사만 추출
        rows = conn.execute(
            "SELECT DISTINCT company FROM jobs WHERE company != '' AND company_size IS NULL"
        ).fetchall()

    companies = [r[0] for r in rows]
    if not companies:
        logger.info("분류할 신규 회사 없음")
        return

    logger.info("분류 시작: %d개 회사", len(companies))
    client = anthropic.Anthropic()
    classified = {}

    for i in range(0, len(companies), BATCH_SIZE):
        batch = companies[i:i + BATCH_SIZE]
        try:
            result = _classify_batch(client, batch)
            classified.update(result)
            logger.info("배치 완료: %d/%d", min(i + BATCH_SIZE, len(companies)), len(companies))
        except Exception as e:
            logger.error("배치 분류 오류: %s", e)

    with sqlite3.connect(DB_PATH) as conn:
        for company, info in classified.items():
            conn.execute(
                "UPDATE jobs SET company_size=?, industry=? WHERE company=?",
                (info["company_size"], info["industry"], company),
            )
        conn.commit()

    logger.info("분류 완료: %d개 회사 업데이트", len(classified))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    classify_all()
