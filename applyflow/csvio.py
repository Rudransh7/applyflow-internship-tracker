"""Bounded CSV parsing with row errors and a spreadsheet-safe export."""
from __future__ import annotations

import csv
import io

from pydantic import ValidationError

from .models import ApplicationInput
from .repository import FIELDS

MAX_ROWS = 500
MAX_BYTES = 1_000_000
METADATA = {"id", "created_at", "updated_at"}


def safe_cell(value):
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def export_csv(rows: list[dict]) -> str:
    output = io.StringIO(newline="")
    columns = ("id", *FIELDS, "created_at", "updated_at")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: safe_cell(value) for key, value in row.items()})
    return output.getvalue()


def parse_csv(raw: bytes) -> list[dict]:
    if len(raw) > MAX_BYTES:
        raise ValueError("CSV must be no larger than 1 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must use UTF-8 encoding") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column headings")
        if not {"company", "role"} <= set(headers):
            raise ValueError("CSV needs company and role column headings")
        if unknown := set(headers) - set(FIELDS) - METADATA:
            raise ValueError("Unknown CSV columns: " + ", ".join(sorted(unknown)))
        rows, errors = [], []
        for number, row in enumerate(reader, start=2):
            if number > MAX_ROWS + 1:
                raise ValueError(f"CSV may contain at most {MAX_ROWS} data rows")
            if None in row or any(value is None for value in row.values()):
                errors.append({"row": number, "message": "Column count does not match the header"})
                continue
            fields = {key: value for key, value in row.items() if key in FIELDS}
            for key in ("url", "deadline"):
                if not fields.get(key, "").strip():
                    fields[key] = None
            if not fields.get("status", "").strip():
                fields["status"] = "Saved"
            try:
                rows.append(ApplicationInput.model_validate(fields).model_dump(mode="json"))
            except ValidationError as exc:
                for error in exc.errors(include_url=False, include_input=False):
                    errors.append({"row": number, "field": str(error["loc"][0]), "message": error["msg"]})
        if errors:
            raise CSVValidationError(errors)
        if not rows:
            raise ValueError("CSV has no application rows")
        return rows
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc


class CSVValidationError(ValueError):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("CSV validation failed; nothing was imported")
