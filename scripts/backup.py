"""Create a consistent SQLite snapshot without overwriting another backup."""
from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def backup(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("Backup destination must differ from the database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve a new path; an existing backup must never be replaced implicitly.
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup integrity check failed")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source", type=Path, default=Path(os.environ.get("APPLYFLOW_DB", Path(__file__).resolve().parents[1] / "data/applications.db")))
    args = parser.parse_args()
    backup(args.source, args.destination)
    print(f"Verified SQLite backup created: {args.destination}")
