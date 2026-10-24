# API contract

Base URL: `http://127.0.0.1:8000`. JSON bodies use `Content-Type: application/json`. Every mutation also requires `X-ApplyFlow-Request: 1`. Browser requests must originate from the same scheme and host/port as the server. The header is a CSRF boundary, **not an authentication secret**.

| Method and path | Result |
|---|---|
| `GET /api/health` | Process readiness response; does not perform a database integrity check |
| `GET /api/applications` | `{items, total, limit, offset}`; query: `q`, `status`, `deadline=soon|overdue`, `limit=1..100`, `offset>=0` |
| `GET /api/applications/{id}` | One record, or 404 |
| `POST /api/applications` | 201, complete record and `Location` header |
| `PATCH /api/applications/{id}` | 200, changed record; an empty or unknown-field patch is rejected |
| `DELETE /api/applications/{id}` | 204 without body, or 404 |
| `GET /api/stats` | Total, count for every stage, `due_soon`, `overdue`, server-local `today` |
| `GET /api/export.csv` | All applications, including metadata; attachment with formula-like cells escaped |
| `POST /api/import.csv` | Raw UTF-8 CSV (`text/csv`); 201 `{imported: n}`; all-or-nothing |

Example:

```bash
curl -i http://127.0.0.1:8000/api/applications \
  -H 'Content-Type: application/json' \
  -H 'X-ApplyFlow-Request: 1' \
  -d '{"company":"Example Labs","role":"Software Intern","status":"Saved"}'

curl http://127.0.0.1:8000/api/import.csv \
  -H 'Content-Type: text/csv' \
  -H 'X-ApplyFlow-Request: 1' \
  --data-binary @examples/applications.csv
```

The dashboard supplies the mutation header. If using Swagger's generated curl examples, add the header yourself; it is enforced by middleware rather than a Swagger API-key scheme.

## Fields and validation

Required: company (2–120 characters), role (2–160). Optional: location (up to 120), HTTP(S) job URL without embedded credentials (up to 2,048), ISO deadline (`YYYY-MM-DD`), notes (up to 2,000) and status. Status is one of Saved, Applied, Assessment, Interview, Offer, Rejected; default Saved. Whitespace is trimmed. Unknown fields and control characters other than tab/newline/carriage return are rejected. Dates/URLs may be explicitly cleared with `null`; required text, location, notes and status may not.

The database rejects duplicate company/role pairs using SQLite `NOCASE`. This is ASCII case-insensitive, not complete Unicode case folding. One company/role pair represents one application; separate cycles or identical titles in different locations need distinct role labels until a future schema adds those concepts.

Lists sort by non-null deadline first, then deadline ascending, then ID descending. Wildcard characters `%` and `_` in search are treated literally. Pagination is offset based and a page/count pair shares one read snapshot. Changes between page requests can still move items.

## Date semantics

`due_soon` means **Saved** applications with deadlines from today through today + 6 days, inclusive. `overdue` means **Saved** with deadline before today. Submitted, interview and terminal records are excluded: an application deadline is not an assessment/interview date. Dates use the local server's calendar; this is a single-user app, not a multi-timezone service.

## CSV semantics

Maximum 1,000,000 bytes and 500 data records. BOM is accepted. Required headers are `company,role`; optional input headers match the fields above. Exported `id,created_at,updated_at` are accepted but ignored during import. Duplicate/unknown headers, wrong column counts, malformed CSV, invalid dates or fields are rejected. Row numbers are logical CSV records, including a header at row 1; quoted multiline fields do not count as extra records.

All rows are validated before any insert. Inserts share one SQLite transaction; a duplicate against the file or database returns 409 and rolls back earlier inserts. Validation errors return 422 with row/field messages. No partial-import mode is implemented. Formula-escaped exports keep the apostrophe on reimport; use SQLite backup for exact round trips.

## Error responses

422: invalid request or CSV rows; 404: missing application; 409: uniqueness/constraint conflict; 413: CSV too large; 415: wrong import media type; 403: missing mutation header or disallowed Origin; 400: untrusted Host; 503: database operational failure, with retry hint. Database errors do not expose SQL or local paths.
