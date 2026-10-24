"""Database operations independent of HTTP; all writes use transactions."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .database import COLUMNS, connection

FIELDS = ("company", "role", "location", "url", "deadline", "status", "notes")
STATUSES = ("Saved", "Applied", "Assessment", "Interview", "Offer", "Rejected")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _insert(conn, fields: dict) -> dict:
    stamp = now()
    cursor = conn.execute("""INSERT INTO applications
        (company,role,location,url,deadline,status,notes,created_at,updated_at)
        VALUES (:company,:role,:location,:url,:deadline,:status,:notes,:created_at,:updated_at)""",
        {**fields, "created_at": stamp, "updated_at": stamp})
    return dict(conn.execute(f"SELECT {COLUMNS} FROM applications WHERE id=?", (cursor.lastrowid,)).fetchone())


class ApplicationRepository:
    def __init__(self, path: Path):
        self.path = path

    def list(self, q: str = "", status: str | None = None, deadline: str | None = None,
             limit: int = 50, offset: int = 0, today: date | None = None) -> dict:
        today = today or date.today()
        where, args = ["1=1"], []
        if q.strip():
            # Treat wildcard characters as literal user text, not SQL patterns.
            pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where.append("(company LIKE ? ESCAPE '\\' OR role LIKE ? ESCAPE '\\' OR location LIKE ? ESCAPE '\\')")
            args.extend([pattern] * 3)
        if status:
            where.append("status = ?")
            args.append(status)
        if deadline == "overdue":
            where.append("status = 'Saved' AND deadline < ?")
            args.append(today.isoformat())
        elif deadline == "soon":
            where.append("status = 'Saved' AND deadline BETWEEN ? AND ?")
            args.extend([today.isoformat(), (today + timedelta(days=6)).isoformat()])
        clause = " AND ".join(where)
        with connection(self.path) as conn:
            conn.execute("BEGIN")  # Count and page see one consistent read snapshot.
            total = conn.execute(f"SELECT COUNT(*) FROM applications WHERE {clause}", args).fetchone()[0]
            items = conn.execute(f"""SELECT {COLUMNS} FROM applications WHERE {clause}
                ORDER BY deadline IS NULL, deadline, id DESC LIMIT ? OFFSET ?""", [*args, limit, offset])
            return {"items": [dict(row) for row in items], "total": total, "limit": limit, "offset": offset}

    def get(self, application_id: int) -> dict | None:
        with connection(self.path) as conn:
            row = conn.execute(f"SELECT {COLUMNS} FROM applications WHERE id=?", (application_id,)).fetchone()
            return dict(row) if row else None

    def create(self, fields: dict) -> dict:
        with connection(self.path) as conn:
            return _insert(conn, fields)

    def update(self, application_id: int, updates: dict) -> dict | None:
        if not updates or not set(updates) <= set(FIELDS):
            raise ValueError("Invalid update fields")
        updates = {**updates, "updated_at": now()}
        clause = ", ".join(f"{name}=?" for name in updates)
        with connection(self.path) as conn:
            result = conn.execute(f"UPDATE applications SET {clause} WHERE id=?", [*updates.values(), application_id])
            if not result.rowcount:
                return None
            return dict(conn.execute(f"SELECT {COLUMNS} FROM applications WHERE id=?", (application_id,)).fetchone())

    def delete(self, application_id: int) -> bool:
        with connection(self.path) as conn:
            return bool(conn.execute("DELETE FROM applications WHERE id=?", (application_id,)).rowcount)

    def stats(self, today: date | None = None) -> dict:
        today = today or date.today()
        with connection(self.path) as conn:
            conn.execute("BEGIN")
            counts = dict(conn.execute("SELECT status, COUNT(*) FROM applications GROUP BY status"))
            due_soon = conn.execute("""SELECT COUNT(*) FROM applications WHERE status='Saved'
                AND deadline BETWEEN ? AND ?""", (today.isoformat(), (today + timedelta(days=6)).isoformat())).fetchone()[0]
            overdue = conn.execute("SELECT COUNT(*) FROM applications WHERE status='Saved' AND deadline < ?",
                                   (today.isoformat(),)).fetchone()[0]
        return {"total": sum(counts.values()), "by_status": {s: counts.get(s, 0) for s in STATUSES},
                "due_soon": due_soon, "overdue": overdue, "today": today.isoformat()}

    def export(self) -> list[dict]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute(f"SELECT {COLUMNS} FROM applications ORDER BY id")]

    def import_rows(self, rows: list[dict]) -> int:
        with connection(self.path) as conn:
            for row in rows:
                _insert(conn, row)
        return len(rows)
