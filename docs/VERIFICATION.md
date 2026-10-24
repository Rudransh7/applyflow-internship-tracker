# Verification record

## Executed checks on 24 October 2026

Source commit: `fb6dc7b195fd4cf9b670cb08b855723dc2f43784`.
[GitHub Actions run 40079241869](https://github.com/Rudransh7/applyflow-internship-tracker/actions/runs/40079241869) completed successfully.

| Check | Evidence |
|---|---|
| Python 3.12 API/database suite | 62 passed, 5 subtests passed; job 120829133081 |
| Python 3.13 API/database suite | Successful; job 120829133109 |
| Python syntax compilation | Successful on both CI versions |
| Chromium workflow | Successful; job 120829132904 |
| Desktop/mobile visual review | Actual CI screenshots inspected at 1440px and 390px widths; readable layouts, responsive table/cards and no observed clipping |
| Dependency setup | Requirements installed successfully on clean CI runners |

The API suite includes real temporary SQLite databases, duplicate writes, atomic imports, persistence, literal search/SQL-shaped input, pagination, conflicts, deadline boundaries, migration preservation/rollback and future-schema rejection. Backup tests verify snapshot contents, integrity and overwrite refusal. Fixtures are fictional.

The browser script creates/edits/removes applications, reloads saved records, imports sample CSV, initiates export, searches, opens a dialog by keyboard and dismisses it with Escape. It checks horizontal page overflow at both viewport widths and captures JavaScript errors. Export-content safety and invalid CSV are verified by API tests, not by the download smoke assertion alone. Browser reload persistence is distinct from the database suite's connection/restart checks.

A first Chromium run found that the Status select's accessible label was ambiguous. The explicit label/select association fixed it; the subsequent run above passed. This was an observed regression and fix, not a claim of exhaustive accessibility certification.

The retained [desktop](images/desktop.png) and [mobile](images/mobile.png) images are genuine CI captures. No simulated screenshot is used. Automated Chromium execution and screenshot review do not replace testing with assistive technology or on physical devices.

## Remaining checks and known limits

- Screen-reader audit, Firefox/WebKit and physical-device testing remain outstanding.
- No authentication or database encryption: bind only to loopback for single-user local use. No public deployment with private data is provided.
- ASCII-only case-insensitive uniqueness; one record per company/role.
- Concurrent edits from different tabs use last-write-wins; no version conflict token.
- Direct dependencies are pinned; no complete transitive lock or completed vulnerability scan.
- Deadline counts use the server calendar.
- CSV validation identifies bad input rows; duplicate constraints report a batch conflict rather than the exact duplicate row. CSV is not a lossless backup.

Earlier local execution was limited by a Python 3.9 host and blocked serving. That restriction did not prevent the later clean CI runs recorded above; it is no longer presented as the current verification status.
