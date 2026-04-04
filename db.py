import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", "jobs.db")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            company      TEXT NOT NULL,
            url          TEXT NOT NULL,
            location     TEXT,
            source       TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "canonical_id" in cols:
        conn.execute("ALTER TABLE jobs DROP COLUMN canonical_id")
    if "company_size" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN company_size TEXT")
    if "industry" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN industry TEXT")
    if "description" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN description TEXT")
    if "req_skills" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN req_skills TEXT")
    if "req_experience" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN req_experience TEXT")
    if "preferred" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN preferred TEXT")
    conn.commit()


def save_jobs(jobs: list[dict]) -> int:
    """Insert new jobs, skip duplicates. Returns count of newly inserted rows."""
    if not jobs:
        return 0

    collected_at = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            job["id"],
            job["title"],
            job["company"],
            job["url"],
            job.get("location", ""),
            job["source"],
            collected_at,
        )
        for job in jobs
    ]

    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)
        cursor = conn.executemany(
            """
            INSERT OR IGNORE INTO jobs (id, title, company, url, location, source, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        return cursor.rowcount
