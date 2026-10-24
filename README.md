# ApplyFlow — internship application manager

A local-first internship tracker with a FastAPI REST API, SQLite persistence and responsive browser dashboard. Developed as an **AI-assisted learning project**: review, test and extend it before representing it as your own independent engineering work.

## What it does

- Create, search, update and delete applications
- Track application stages (Saved → Applied → Assessment → Interview → Offer / Rejected)
- Record deadlines, company, location, job URL and notes
- Show live totals, upcoming deadlines and overdue saved applications
- Export records to CSV (with protection against spreadsheet formula injection)
- Validate requests, reject duplicate company/role pairs and document endpoints via OpenAPI
- Run backend tests in GitHub Actions

## Run locally

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app:app --reload
```

Visit **http://127.0.0.1:8000**. For auto-generated API documentation visit **http://127.0.0.1:8000/docs**.

```bash
pytest -q
```

Data is stored in `data/applications.db` by default and excluded from version control. To use another database path set `APPLYFLOW_DB`.

## Engineering notes

The API uses parameterised SQLite queries and Pydantic validation. Database connections have explicit commit/rollback/close semantics. Duplicate checks are enforced by a database UNIQUE constraint, not only the UI. CSV output escapes spreadsheet formulas. The frontend inserts user text using `textContent` rather than `innerHTML`.

This is a **single-user local development prototype**, not a production SaaS application. It does not implement authentication, user accounts, backups or hosted deployment; do not expose it directly to the public internet.

## Next engineering challenges (recommended for the student)

1. Add a migration system and an API integration test for conflicting concurrent requests.
2. Design authentication and per-user ownership (do not merely store a username field).
3. Add a deadline reminder background job, with idempotent notifications.
4. Implement CSV import with row-level validation and detailed error reporting.
5. Containerise and deploy with a managed database.

## CV talking points (only after you can demonstrate and explain them)

- Built a FastAPI/SQLite application tracker with CRUD endpoints, filtering, deadline statistics and CSV export.
- Added Pydantic input validation, database uniqueness rules, and automated tests in GitHub Actions.
- Designed a responsive browser interface that interacts with a JSON REST API.
