# Verification record — 24 October 2026

This record separates execution evidence from intended behaviour.

| Check | Result |
|---|---|
| Source audit | All starter source, HTML/CSS/JS, tests and configuration inspected before edits |
| Original API tests | Not run here: host Python 3.9.6 is below supported application runtime and dependencies are absent |
| SQLite integration suite | **10 passed** using actual temporary SQLite databases |
| SQLite backup suite | **2 passed**; verifies snapshot contents, integrity, missing-source behaviour and overwrite refusal |
| Python syntax compilation | Passed for application, scripts and tests; not a substitute for imports/execution |
| JavaScript syntax | Passed with Node 24.21.0 |
| HTML references | No duplicate IDs or missing literal JS/label targets in static check |
| Expanded HTTP suite | Written, **not executed**; requires installed FastAPI/Pydantic/HTTPX/pytest on Python 3.12/3.13 |
| Browser suite | Written, **not executed** |
| Manual desktop/mobile browser review | **Blocked**; loopback bind denied and local-file browser navigation disallowed |
| Dependency installation | **Blocked** by local network restrictions; direct versions checked against official PyPI |
| GitHub Actions | Workflow configured, **no run yet** |
| Publication/deployment | **Pending** GitHub browser sign-in and creation of the new repository |

## Executed persistence coverage

Concurrent duplicate creates (exactly one commit), database-level validation, all-or-nothing imports, restart persistence, search wildcard escaping, SQL injection-shaped input, paging/order, conflicting patch rollback, deadline boundaries, migration preservation, failed migration rollback and rejection of a future schema. All fixtures are temporary and fictional.

## Browser acceptance checklist (pending)

- Create/edit/delete through the dashboard; verify refresh persistence.
- Test invalid/duplicate entries, cleared nullable fields and long notes.
- Import valid CSV, invalid CSV and duplicate CSV; confirm no partial write.
- Export and inspect formula escaping.
- Search/filter, paginate, delete the final item on a page and recover from a failed request.
- At 1440×1000 and 390×844, inspect text wrapping, focus outlines, card/table layout and dialog scrolling.
- Use Tab, Shift+Tab, Enter and Escape; confirm visible focus and focus restoration.
- Check console errors, network failures and reduced-motion behaviour; perform a screen-reader review separately.

The prepared Chromium smoke test covers a useful subset and creates screenshots. Its assertions alone do not certify accessibility or visual quality. No screenshot or animated demonstration has been fabricated.

## Known risks

No authentication/encryption; local-only. ASCII-only case-insensitive uniqueness. One record per company/role. No lost-update/version check for two tabs editing simultaneously. No full transitive lock or completed dependency vulnerability scan. Date counts use the server calendar. CSV errors identify validation rows; uniqueness conflicts currently identify the failed batch, not the exact duplicate row. Manual browser QA remains a release gate.
