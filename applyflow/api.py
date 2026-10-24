"""HTTP layer. Intended for a single user on a loopback interface only."""
from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .csvio import MAX_BYTES, CSVValidationError, export_csv, parse_csv
from .database import initialise
from .models import Application, ApplicationInput, ApplicationPage, ApplicationPatch, ImportResult, Statistics, Status
from .repository import ApplicationRepository

ROOT = Path(__file__).resolve().parent.parent


def create_app(db_path: Path | str | None = None, *, allowed_hosts: list[str] | None = None) -> FastAPI:
    database = Path(db_path) if db_path is not None else Path(os.environ.get("APPLYFLOW_DB", ROOT / "data/applications.db"))
    repo = ApplicationRepository(database)

    @asynccontextmanager
    async def lifespan(_app):
        await run_in_threadpool(initialise, database)
        yield

    app = FastAPI(title="ApplyFlow API", version="2.0.0", lifespan=lifespan,
                  description="Single-user, local-only internship application tracker. Mutations require X-ApplyFlow-Request: 1.")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def local_browser_boundary(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            expected = urlsplit(str(request.base_url))
            try:
                actual = urlsplit(origin) if origin else None
            except ValueError:
                return JSONResponse({"detail": "Invalid Origin header"}, status_code=403)
            if (actual and (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc)) or request.headers.get("x-applyflow-request") != "1":
                return JSONResponse({"detail": "Use the local dashboard or send X-ApplyFlow-Request: 1 from the same origin"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(_request, _exc):
        return JSONResponse({"detail": "Company and role must be unique and all fields must satisfy database constraints. Nothing was saved."}, status_code=409)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(_request, _exc):
        return JSONResponse({"detail": "Database is temporarily unavailable. Please retry."}, status_code=503, headers={"Retry-After": "1"})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/applications", response_model=ApplicationPage)
    def list_applications(q: str = Query("", max_length=150), status: Status | None = None,
                          deadline: Literal["soon", "overdue"] | None = None,
                          limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return repo.list(q, status.value if status else None, deadline, limit, offset)

    @app.get("/api/applications/{application_id}", response_model=Application)
    def get_application(application_id: int):
        result = repo.get(application_id)
        if result is None:
            raise HTTPException(404, "Application not found")
        return result

    @app.post("/api/applications", status_code=201, response_model=Application)
    def create_application(payload: ApplicationInput, response: Response):
        result = repo.create(payload.model_dump(mode="json"))
        response.headers["Location"] = f"/api/applications/{result['id']}"
        return result

    @app.patch("/api/applications/{application_id}", response_model=Application)
    def update_application(application_id: int, payload: ApplicationPatch):
        result = repo.update(application_id, payload.model_dump(mode="json", exclude_unset=True))
        if result is None:
            raise HTTPException(404, "Application not found")
        return result

    @app.delete("/api/applications/{application_id}", status_code=204)
    def delete_application(application_id: int):
        if not repo.delete(application_id):
            raise HTTPException(404, "Application not found")
        return Response(status_code=204)

    @app.get("/api/stats", response_model=Statistics)
    def statistics():
        return repo.stats()

    @app.get("/api/export.csv")
    def download_csv():
        return Response(export_csv(repo.export()), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="applyflow-applications.csv"'})

    @app.post("/api/import.csv", status_code=201, response_model=ImportResult)
    async def upload_csv(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].strip() != "text/csv":
            raise HTTPException(415, "Send the CSV as a text/csv request body")
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, "CSV must be no larger than 1 MB")
            raw.extend(chunk)
        try:
            rows = await run_in_threadpool(parse_csv, bytes(raw))
        except CSVValidationError as exc:
            return JSONResponse({"detail": str(exc), "errors": exc.errors}, status_code=422)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        count = await run_in_threadpool(repo.import_rows, rows)
        return {"imported": count}

    @app.get("/", include_in_schema=False)
    def homepage():
        return FileResponse(ROOT / "static/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app
