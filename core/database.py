import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "ab_testing.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS experiments (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,
        hypothesis  TEXT,
        metric      TEXT NOT NULL,
        split       REAL NOT NULL DEFAULT 0.5,
        min_samples INTEGER NOT NULL DEFAULT 100,
        status      TEXT NOT NULL DEFAULT 'running',
        created_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS experiment_events (
        id              TEXT PRIMARY KEY,
        experiment_id   TEXT NOT NULL REFERENCES experiments(id),
        user_id         TEXT NOT NULL,
        variant         TEXT NOT NULL,
        event           TEXT NOT NULL,
        value           REAL DEFAULT 1.0,
        timestamp       TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_events_exp
        ON experiment_events(experiment_id);
    CREATE INDEX IF NOT EXISTS idx_events_user
        ON experiment_events(user_id, experiment_id);
    """)
    conn.commit()
    conn.close()


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.utcnow().isoformat()
