import json
import os
import sqlite3
from collections import Counter

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request

from db import DB_PATH, init_db
from main import collect

app = Flask(__name__)

# 백그라운드 스케줄러: 매일 09:00 KST(UTC 00:00) 수집
# scheduler = BackgroundScheduler(timezone="UTC")
# scheduler.add_job(collect, "cron", hour=0, minute=0)
# scheduler.start()


@app.route("/collect")
def trigger_collect():
    secret = request.args.get("secret", "")
    if secret != os.getenv("COLLECT_SECRET", ""):
        return "Unauthorized", 401
    import threading
    threading.Thread(target=collect).start()
    return "수집 시작됨", 200


def compute_insights(jobs) -> dict:
    """필터된 jobs 목록에서 req_skills, req_experience, preferred 집계 → insights dict 반환"""
    analyzed_count = sum(1 for j in jobs if j["req_skills"] is not None)
    if analyzed_count == 0:
        return {"analyzed_count": 0}

    skills_counter: Counter = Counter()
    exp_counter: Counter = Counter()
    preferred_counter: Counter = Counter()

    for job in jobs:
        if job["req_skills"]:
            try:
                for skill in json.loads(job["req_skills"]):
                    if skill:
                        skills_counter[skill] += 1
            except (json.JSONDecodeError, TypeError):
                pass
        if job["req_experience"]:
            exp_counter[job["req_experience"]] += 1
        if job["preferred"]:
            try:
                for kw in json.loads(job["preferred"]):
                    if kw:
                        preferred_counter[kw] += 1
            except (json.JSONDecodeError, TypeError):
                pass

    total = analyzed_count
    return {
        "analyzed_count": analyzed_count,
        "top_skills": [(skill, cnt, round(cnt / total * 100)) for skill, cnt in skills_counter.most_common(10)],
        "experience": [(exp, cnt, round(cnt / total * 100)) for exp, cnt in exp_counter.most_common()],
        "top_preferred": [(kw, cnt, round(cnt / total * 100)) for kw, cnt in preferred_counter.most_common(8)],
    }


@app.route("/")
def index():
    source = request.args.get("source", "")
    keyword = request.args.get("keyword", "")
    location = request.args.get("location", "")
    company_size = request.args.get("company_size", "")
    industry = request.args.get("industry", "")
    req_experience = request.args.get("req_experience", "")

    query = """
        SELECT id, title, company, url, location, source, collected_at,
               company_size, industry, req_skills, req_experience, preferred
        FROM jobs WHERE 1=1
    """
    params = []

    if source:
        query += " AND source = ?"
        params.append(source)
    if keyword:
        query += " AND (title LIKE ? OR company LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    if company_size:
        query += " AND company_size = ?"
        params.append(company_size)
    if industry:
        query += " AND industry = ?"
        params.append(industry)
    if req_experience:
        query += " AND req_experience = ?"
        params.append(req_experience)

    query += " ORDER BY collected_at DESC"

    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        conn.row_factory = sqlite3.Row
        jobs = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        last_updated = conn.execute("SELECT MAX(collected_at) FROM jobs").fetchone()[0]

    insights = compute_insights(jobs)

    return render_template(
        "index.html",
        jobs=jobs,
        total=total,
        source=source,
        keyword=keyword,
        location=location,
        company_size=company_size,
        industry=industry,
        req_experience=req_experience,
        last_updated=last_updated[:10] if last_updated else "",
        insights=insights,
    )



if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)
