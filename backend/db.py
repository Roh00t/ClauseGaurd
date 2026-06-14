"""
backend/db.py
Single-file SQLite for ClauseGuard v2 — one data/data.db, three tables.

All connections use check_same_thread=False + timeout=10 so concurrent
requests under uvicorn don't hit "database is locked" (PM7). Every query
elsewhere must use parameterised statements (RT8).
"""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "data.db"


def get_conn() -> sqlite3.Connection:
    """Return a SQLite connection safe to use from FastAPI worker threads."""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Idempotent DB initialisation. Safe to call on every startup (PM10).

    This is the FINAL schema. On a fresh DB it creates every column at once;
    on an existing DB `CREATE TABLE IF NOT EXISTS` is a no-op and data is kept.
    No ALTER TABLE here — see migrate_db() for upgrading old DBs.
    """
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS regulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                content TEXT,
                category TEXT,
                scraped_at TEXT
            );
            -- DEPRECATED (Phase 2): session writes moved to client IndexedDB.
            -- Server no longer INSERTs here; table kept (not dropped) for safe
            -- migration. Read endpoints return 410 Gone.
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                filenames TEXT,
                context_filenames TEXT,
                doc_count INTEGER,
                context_doc_count INTEGER,
                overall_severity TEXT,
                verdict TEXT,
                analysis TEXT,
                judgment TEXT,
                regulation_source TEXT
            );
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                status TEXT,
                method TEXT,
                chars INTEGER,
                scraped_at TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


def migrate_db() -> None:
    """Add columns missing from an old-schema sessions table. Call AFTER init_db().

    Only the specific "duplicate column" OperationalError is swallowed (the
    expected no-op when a column already exists). Any other DB error is re-raised
    rather than silently eaten (PM4).
    """
    conn = get_conn()
    migrations = [
        "ALTER TABLE sessions ADD COLUMN judgment TEXT",
        "ALTER TABLE sessions ADD COLUMN context_filenames TEXT",
        "ALTER TABLE sessions ADD COLUMN context_doc_count INTEGER",
        "ALTER TABLE sessions ADD COLUMN verdict TEXT",
    ]
    try:
        for sql in migrations:
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    pass  # column already exists — expected
                else:
                    raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    migrate_db()
    print(f"DB ok -> {DB_PATH}")
