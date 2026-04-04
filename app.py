import os
import sqlite3

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request

from db import DB_PATH, init_db
from main import collect

app = Flask(__name__)

# 백그라운드 스케줄러: 매일 09:00 KST(UTC 00:00) 수집
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(collect, "cron", hour=0, minute=0)
scheduler.start()


@app.route("/collect")
def trigger_collect():
    secret = request.args.get("secret", "")
    if secret != os.getenv("COLLECT_SECRET", ""):
        return "Unauthorized", 401
    import threading
    threading.Thread(target=collect).start()
    return "수집 시작됨", 200


@app.route("/")
def index():
    source = request.args.get("source", "")
    keyword = request.args.get("keyword", "")
    location = request.args.get("location", "")
    company_size = request.args.get("company_size", "")
    industry = request.args.get("industry", "")

    query = """
        SELECT id, title, company, url, location, source, collected_at, company_size, industry
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

    query += " ORDER BY collected_at DESC"

    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        conn.row_factory = sqlite3.Row
        jobs = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    return render_template(
        "index.html",
        jobs=jobs,
        total=total,
        source=source,
        keyword=keyword,
        location=location,
        company_size=company_size,
        industry=industry,
    )



if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(debug=False, host="0.0.0.0", port=port)
