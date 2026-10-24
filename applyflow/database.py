"""Small versioned SQLite schema; no ORM needed for one table."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

COLUMNS = "id, company, role, location, url, deadline, status, notes, created_at, updated_at"
SCHEMA = """CREATE TABLE applications_v1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL CHECK(length(trim(company)) BETWEEN 2 AND 120),
    role TEXT NOT NULL CHECK(length(trim(role)) BETWEEN 2 AND 160),
    location TEXT NOT NULL DEFAULT '' CHECK(length(location) <= 120),
    url TEXT CHECK(url IS NULL OR length(url) <= 2048),
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'Saved'
        CHECK(status IN ('Saved','Applied','Assessment','Interview','Offer','Rejected')),
    notes TEXT NOT NULL DEFAULT '' CHECK(length(notes) <= 2000),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company COLLATE NOCASE, role COLLATE NOCASE)
)"""


@contextmanager
def connection(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialise(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as conn:
        # Serialise initialisation and migrate the original unversioned table atomically.
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("Database was created by a newer ApplyFlow version")
        if version == 0:
            conn.execute(SCHEMA)
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='applications'").fetchone():
                conn.execute(f"INSERT INTO applications_v1 ({COLUMNS}) SELECT {COLUMNS} FROM applications")
                conn.execute("DROP TABLE applications")
            conn.execute("ALTER TABLE applications_v1 RENAME TO applications")
            conn.execute("CREATE INDEX idx_applications_deadline ON applications(deadline)")
            conn.execute("CREATE INDEX idx_applications_status ON applications(status)")
            conn.execute("PRAGMA user_version = 1")
