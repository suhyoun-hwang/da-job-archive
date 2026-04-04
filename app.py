import os
import sqlite3

from flask import Flask, render_template, request

from db import DB_PATH

app = Flask(__name__)


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
