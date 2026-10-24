"""ApplyFlow: an internship-application tracker with a documented REST API."""
from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "applications.db"


class Status(str, Enum):
    SAVED = "Saved"
    APPLIED = "Applied"
    ASSESSMENT = "Assessment"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"


class ApplicationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    company: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=160)
    location: str = Field(default="", max_length=120)
    url: HttpUrl | None = None
    deadline: date | None = None
    status: Status = Status.SAVED
    notes: str = Field(default="", max_length=2000)

    @field_validator("company", "role")
    @classmethod
    def no_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Cannot be blank")
        return value


class ApplicationPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    company: str | None = Field(default=None, min_length=2, max_length=120)
    role: str | None = Field(default=None, min_length=2, max_length=160)
    location: str | None = Field(default=None, max_length=120)
    url: HttpUrl | None = None
    deadline: date | None = None
    status: Status | None = None
    notes: str | None = Field(default=None, max_length=2000)


COLS = "id, company, role, location, url, deadline, status, notes, created_at, updated_at"


@contextmanager
def db_connection(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_app(db_path: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="ApplyFlow API", version="1.0.0", description="Track internship applications and deadlines.")
    database = Path(db_path) if db_path is not None else Path(os.environ.get("APPLYFLOW_DB", DEFAULT_DB))
    with db_connection(database) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL, role TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
            url TEXT, deadline TEXT, status TEXT NOT NULL DEFAULT 'Saved',
            notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(company COLLATE NOCASE, role COLLATE NOCASE)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_deadline ON applications(deadline)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")

    def item(row: sqlite3.Row) -> dict:
        return dict(row)

    @app.get("/api/applications")
    def get_applications(q: str = Query(default="", max_length=150), status: Status | None = None):
        sql = f"SELECT {COLS} FROM applications WHERE 1=1"
        args: list[str] = []
        if q:
            sql += " AND (company LIKE ? OR role LIKE ? OR location LIKE ?)"
            args.extend([f"%{q}%"] * 3)
        if status:
            sql += " AND status = ?"
            args.append(status.value)
        sql += " ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline, id DESC"
        with db_connection(database) as conn:
            return [item(x) for x in conn.execute(sql, args)]

    @app.post("/api/applications", status_code=201)
    def add_application(payload: ApplicationInput):
        fields = payload.model_dump(mode="json")
        stamp = now_iso()
        try:
            with db_connection(database) as conn:
                cursor = conn.execute("""INSERT INTO applications
                    (company,role,location,url,deadline,status,notes,created_at,updated_at)
                    VALUES (:company,:role,:location,:url,:deadline,:status,:notes,:created_at,:updated_at)""",
                    {**fields, "created_at": stamp, "updated_at": stamp})
                return item(conn.execute(f"SELECT {COLS} FROM applications WHERE id=?", (cursor.lastrowid,)).fetchone())
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An application for this company and role already exists")

    @app.patch("/api/applications/{application_id}")
    def update_application(application_id: int, payload: ApplicationPatch):
        updates = payload.model_dump(mode="json", exclude_unset=True)
        if any(k in updates and updates[k] is None for k in ("company", "role", "status", "location", "notes")):
            raise HTTPException(422, "This field cannot be null")
        updates["updated_at"] = now_iso()
        clause = ", ".join(f"{k} = ?" for k in updates)
        try:
            with db_connection(database) as conn:
                result = conn.execute(f"UPDATE applications SET {clause} WHERE id = ?", (*updates.values(), application_id))
                if not result.rowcount:
                    raise HTTPException(404, "Application not found")
                return item(conn.execute(f"SELECT {COLS} FROM applications WHERE id=?", (application_id,)).fetchone())
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An application for this company and role already exists")

    @app.delete("/api/applications/{application_id}", status_code=204)
    def remove_application(application_id: int):
        with db_connection(database) as conn:
            result = conn.execute("DELETE FROM applications WHERE id=?", (application_id,))
            if not result.rowcount:
                raise HTTPException(404, "Application not found")
        return Response(status_code=204)

    @app.get("/api/stats")
    def get_stats():
        with db_connection(database) as conn:
            counts = {row["status"]: row["count"] for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM applications GROUP BY status")}
            today, upcoming = date.today(), date.today() + timedelta(days=7)
            due_soon = conn.execute("""SELECT COUNT(*) FROM applications WHERE deadline BETWEEN ? AND ?
                                    AND status NOT IN ('Offer','Rejected')""", (today.isoformat(), upcoming.isoformat())).fetchone()[0]
            overdue = conn.execute("""SELECT COUNT(*) FROM applications WHERE deadline < ?
                                    AND status = 'Saved'""", (today.isoformat(),)).fetchone()[0]
            return {"total": sum(counts.values()), "by_status": {s.value: counts.get(s.value, 0) for s in Status},
                    "due_soon": due_soon, "overdue": overdue}

    @app.get("/api/export.csv")
    def export_csv():
        with db_connection(database) as conn:
            rows = [dict(r) for r in conn.execute(f"SELECT {COLS} FROM applications ORDER BY id")]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=COLS.split(", "))
        writer.writeheader()
        # Defend against spreadsheet formula injection when users open the CSV.
        for row in rows:
            for key, value in row.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    row[key] = "'" + value
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="applyflow-applications.csv"'})

    @app.get("/", include_in_schema=False)
    def homepage():
        return FileResponse(ROOT / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
