# Ownership and interview preparation

## What existed before this review

The AI-assisted starter contained one Python application module, SQLite CRUD, a dashboard, a company/role uniqueness constraint, CSV export and eight API tests. Its original source is preserved in the first local commit and the task's original archive.

This task added the application factory and modules, strict contracts, transactional migration/import, deadline semantics, pagination, backup utility, local-browser protections, revised interface and broader tests. These changes were implemented by an AI coding assistant at the student's request. They must not be presented as independently authored student work. No claim of production use or measured business impact is made.

## Explain the architecture

An action in `static/app.js` sends an HTTP request. `api.py` validates the request through Pydantic models and delegates data operations to the repository. The repository opens a short-lived SQLite connection through `database.py`, uses bound parameters, and commits on success or rolls back on exception. The response updates the dashboard using text-safe DOM operations. The application factory supplies a database path, which lets tests isolate their data.

CSV import validates the entire bounded file before attempting inserts. One transaction contains the inserts, so a conflict cannot leave a partially imported batch. The database still enforces uniqueness because two callers can pass a pre-check simultaneously. Schema upgrades also run transactionally so a failed conversion leaves the old table intact.

## Interview questions and model explanations

**Why SQLite rather than PostgreSQL?** A local personal tracker has one user and modest writes. SQLite avoids a separate service and makes backups simple. Multiple hosted users would change requirements for access control, concurrency and operations; switching databases alone would not solve those concerns.

**Why validate in both Pydantic and SQLite?** Request validation gives clear errors. Database constraints protect integrity from concurrent requests and other writers. They cover different boundaries.

**What does atomic import mean?** Either every validated row is committed or none is. Validation errors happen before writes; an integrity error during insertion rolls the transaction back.

**How do you prevent SQL injection?** Values use SQLite placeholders. The editable column names come from a fixed allowlist rather than user input. Search escapes `%` and `_` because users expect literal search, which is a separate concern from injection.

**Why no login?** The documented deployment is loopback-only for one OS user. Host/origin/custom-header checks reduce malicious website requests but are not authentication. Public hosting requires identity, row ownership, HTTPS and private storage.

**What happens if two tabs edit the same record?** The current design is last-write-wins. Optimistic concurrency is a useful future change; it is not implemented.

**Why is CSV not a backup?** Export escaping can change spreadsheet-sensitive strings and import regenerates IDs/timestamps. The SQLite backup utility preserves the database.

## Personal coding exercises

1. Add an `updated_at` or integer revision precondition to PATCH. Write a test with two clients reading the same version: the first succeeds, the stale update returns 409, and its data is unchanged. Decide how the UI helps the user resolve it.
2. Add a date-range filter without string-building SQL. Test exact boundaries, no matches and interaction with pagination. Explain why inclusive/exclusive endpoints matter.
3. Improve duplicate CSV errors to identify the logical row while retaining atomicity. Test both duplicates inside a batch and conflicts with existing rows.

Complete one exercise without asking AI to implement it. Record your design, failing test, fix and limitations in a real commit/PR. Only then add a CV bullet describing that personal contribution.

## Run, debug and demonstrate

Follow the README with a temporary database and fictional CSV. Create one application, edit its status, search for it and reload to show persistence. Import a duplicate batch and show that the total is unchanged. Explain a transaction and a failing validation response in OpenAPI. Show tests actually running, not just a badge.

For debugging, reproduce the smallest request, inspect the HTTP response in browser developer tools, run the relevant API or persistence test, and examine a disposable database. Do not log private application notes. Demonstrate only workflows that have passed browser verification; consult `VERIFICATION.md` first.
