"""
공고 description에서 요구 기술 스택, 요구 경력, 우대 사항을 Claude API로 추출.
classify.py와 동일한 패턴으로 배치 처리.
"""
import json
import logging
import sqlite3

import anthropic
from dotenv import load_dotenv

load_dotenv()

from db import DB_PATH, init_db

logger = logging.getLogger(__name__)

BATCH_SIZE = 8  # description이 길어서 작게 설정
MAX_DESC_CHARS = 2000  # 너무 긴 description은 잘라서 전송

EXPERIENCE_LABELS = ("신입", "1년 이상", "3년 이상", "5년 이상", "무관")

PROMPT_TEMPLATE = """\
다음 데이터 분석가 채용공고 {n}건에서 요구사항을 분석해줘.

추출 항목:
- req_skills: 공고에서 요구하거나 우대하는 기술/도구 목록 (예: ["Python", "SQL", "Tableau", "A/B테스트"])
  - 일반적인 소프트스킬(커뮤니케이션 등)은 제외
  - 기술 이름은 원문 그대로 (SQL, Python, 등)
- req_experience: 최소 요구 경력을 아래 중 하나로 표준화
  - "신입" (경력 무관 또는 신입 가능)
  - "1년 이상"
  - "3년 이상"
  - "5년 이상"
  - "무관" (명시 없음)
- preferred: 우대 사항 키워드 목록 (최대 5개, 핵심적인 것만)
  예: ["석사/박사 우대", "핀테크 경험", "스타트업 경험", "빅데이터 플랫폼"]

공고 목록:
{postings}

JSON 배열로만 응답 (다른 텍스트 없이):
[
  {{"id": "job_id", "req_skills": [...], "req_experience": "...", "preferred": [...]}},
  ...
]"""


def _analyze_batch(client: anthropic.Anthropic, jobs: list[tuple[str, str]]) -> dict[str, dict]:
    """jobs: list of (id, description)"""
    postings = []
    for job_id, desc in jobs:
        truncated = desc[:MAX_DESC_CHARS] if len(desc) > MAX_DESC_CHARS else desc
        postings.append(f"id: {job_id}\n내용:\n{truncated}")

    prompt = PROMPT_TEMPLATE.format(n=len(jobs), postings="\n---\n".join(postings))
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    results = json.loads(text)
    return {r["id"]: {
        "req_skills": json.dumps(r.get("req_skills", []), ensure_ascii=False),
        "req_experience": r.get("req_experience", "무관"),
        "preferred": json.dumps(r.get("preferred", []), ensure_ascii=False),
    } for r in results}


def analyze_all() -> None:
    """description 있고 req_skills 없는 공고를 배치 분석하여 DB 업데이트"""
    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        rows = conn.execute(
            "SELECT id, description FROM jobs WHERE description IS NOT NULL AND req_skills IS NULL"
        ).fetchall()

    if not rows:
        logger.info("분석할 공고 없음 (전부 완료)")
        return

    logger.info("공고 분석 시작: %d건", len(rows))
    client = anthropic.Anthropic()
    analyzed = {}

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        try:
            result = _analyze_batch(client, batch)
            analyzed.update(result)
            logger.info("배치 완료: %d/%d", min(i + BATCH_SIZE, len(rows)), len(rows))
        except Exception as e:
            logger.error("배치 분석 오류: %s", e)

    with sqlite3.connect(DB_PATH) as conn:
        for job_id, info in analyzed.items():
            conn.execute(
                "UPDATE jobs SET req_skills=?, req_experience=?, preferred=? WHERE id=?",
                (info["req_skills"], info["req_experience"], info["preferred"], job_id),
            )
        conn.commit()

    logger.info("분석 완료: %d건 업데이트", len(analyzed))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    analyze_all()
