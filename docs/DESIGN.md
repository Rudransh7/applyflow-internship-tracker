# Design decisions and limitations

## Data integrity over optimistic UI

The server is authoritative. The dashboard waits for successful writes, then refreshes its page and statistics. It uses request sequence numbers to discard stale search responses. Double submissions are blocked while saving. A database UNIQUE constraint handles the race between simultaneous create requests; a browser duplicate check alone would not.

Each request uses its own SQLite connection. `connection()` commits on success, rolls back on failure and always closes. Reads of a page/count or multiple statistics occur in one read transaction. SQLite's five-second busy timeout accommodates short writes; operational failures become a generic 503. This does not provide high-volume multi-user throughput.

## Migration strategy

Version 0 is the starter schema. During initialisation, `BEGIN IMMEDIATE` serialises migration, copies records into a constrained v1 table, replaces the old table and sets `PRAGMA user_version=1`. IDs and timestamps are retained. If any old record violates new constraints, the transaction rolls back and startup fails; it does not silently discard data. Back up first and repair invalid legacy records deliberately.

A schema from a newer version is rejected. This deliberately small migration is suitable for one version of one table; more versions would justify explicit numbered migration files.

## Security choices

- Local use avoids introducing an incomplete authentication system or public storage of personal application notes.
- Trusted Host filtering limits DNS-rebinding exposure. An explicit same-origin check plus a custom mutation header protects against ordinary cross-site form submissions. No permissive CORS configuration is installed.
- SQLite values are parameterised. Dynamic update column names are restricted to a fixed field set.
- Pydantic validates request boundaries; SQLite independently checks key invariants.
- User-provided strings become text nodes, not HTML. Job links accept HTTP(S) only, reject embedded credentials and open with `noopener noreferrer`.
- Dashboard CSP restricts executable resources to the same origin. Responses use nosniff, no-referrer, frame denial and no-store. Swagger docs are separate and load their usual external assets.
- CSV imports are bounded and atomic. Exports prefix spreadsheet formula triggers; this intentionally trades lossless CSV round trips for safer spreadsheet opening.
- Local malware, another OS user with file access, browser extensions and deliberate API clients are outside the authentication boundary. The custom header is public and is not an API key.

## What is deliberately absent

No login, public hosting, reminder service, cloud sync, status-history analytics or multi-user sharing. No ORM, Redis, task queue, microservices or container orchestration. The project should demonstrate decisions and reliable behaviour, not infrastructure volume.

No automatic lifecycle ordering is enforced: users can correct a status or move backwards. All six stages are explicit categories, not proof of completed historical transitions. Statistics are current counts, not conversion rates.

## Dependency policy

Direct dependencies are pinned to releases checked on official PyPI on 24 October 2026: FastAPI, Pydantic, Uvicorn, pytest, HTTPX and optional Playwright. Transitive versions have not been resolved and locked in this restricted environment. The package install and full suite still need verification; do not mistake explicit versions for a tested dependency lock. Dependabot is configured for monthly reviews.

Sources: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [Pydantic](https://pydantic.dev/), [Python SQLite](https://docs.python.org/3/library/sqlite3.html), [FastAPI releases](https://fastapi.tiangolo.com/release-notes/), [GitHub Actions Python](https://docs.github.com/actions/guides/building-and-testing-python).
