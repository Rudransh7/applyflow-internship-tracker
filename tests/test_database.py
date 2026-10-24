"""Standard-library integration tests, also discovered by pytest."""
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from applyflow.database import connection, initialise
from applyflow.repository import ApplicationRepository


def example(**changes):
    return {"company": "Example Labs", "role": "Software Intern", "location": "Leeds", "url": None,
            "deadline": None, "status": "Saved", "notes": "", **changes}


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested/test.db"
        initialise(self.path)
        self.repo = ApplicationRepository(self.path)

    def test_restart_preserves_data(self):
        original = self.repo.create(example())
        initialise(self.path)
        self.assertEqual(ApplicationRepository(self.path).get(original["id"]), original)

    def test_concurrent_duplicates_only_one_commit(self):
        def create(_):
            try:
                self.repo.create(example())
                return "created"
            except sqlite3.IntegrityError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create, range(4)))
        self.assertEqual(results.count("created"), 1)
        self.assertEqual(results.count("conflict"), 3)
        self.assertEqual(self.repo.stats()["total"], 1)

    def test_import_rolls_back_on_conflict(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.import_rows([example(), example(company="EXAMPLE LABS")])
        self.assertEqual(self.repo.stats()["total"], 0)

    def test_constraints_are_enforced_below_api(self):
        for changes in [{"status": "Invalid"}, {"company": " "}, {"role": "x"}, {"location": None}, {"notes": "x" * 2001}]:
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                self.repo.create(example(**changes))
        self.assertEqual(self.repo.stats()["total"], 0)

    def test_deadline_boundaries_exclude_submitted_and_terminal(self):
        for i, (deadline, status) in enumerate([
            ("2026-10-23", "Saved"), ("2026-10-24", "Saved"), ("2026-10-30", "Saved"),
            ("2026-10-31", "Saved"), ("2026-10-24", "Applied"), ("2026-10-23", "Interview"),
            ("2026-10-24", "Offer"), ("2026-10-24", "Rejected"), (None, "Saved"),
        ]):
            self.repo.create(example(company=f"Company {i}", deadline=deadline, status=status))
        stats = self.repo.stats(date(2026, 10, 24))
        self.assertEqual(stats["due_soon"], 2)
        self.assertEqual(stats["overdue"], 1)
        self.assertEqual(stats["total"], 9)
        self.assertEqual(self.repo.list(deadline="soon", today=date(2026, 10, 24))["total"], 2)
        self.assertEqual(self.repo.list(deadline="overdue", today=date(2026, 10, 24))["total"], 1)

    def test_sql_injection_wildcards_and_empty_results(self):
        self.repo.create(example(company="100%_Labs"))
        self.assertEqual(self.repo.list(q="%_")["total"], 1)
        self.assertEqual(self.repo.list(q="' OR 1=1 --")["total"], 0)
        self.assertIsNone(self.repo.get(100))
        self.assertFalse(self.repo.delete(100))
        self.assertIsNone(self.repo.update(100, {"notes": "hi"}))
        with self.assertRaises(ValueError):
            self.repo.update(1, {"status = 'Offer'; DROP TABLE applications; --": "anything"})

    def test_order_pagination_and_conflicting_update(self):
        a = self.repo.create(example(company="First", deadline="2027-03-10"))
        b = self.repo.create(example(company="Second", deadline="2027-01-10"))
        self.repo.create(example(company="Third"))
        self.assertEqual(self.repo.list(limit=1)["items"][0]["id"], b["id"])
        self.assertEqual(self.repo.list(limit=1, offset=1)["items"][0]["id"], a["id"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.update(b["id"], {"company": "First"})
        self.assertEqual(self.repo.get(b["id"])["company"], "Second")

    def test_migrate_original_schema_preserves_rows(self):
        old = Path(self.temp.name) / "legacy.db"
        with connection(old) as conn:
            conn.execute("""CREATE TABLE applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, role TEXT, location TEXT,
                url TEXT, deadline TEXT, status TEXT, notes TEXT, created_at TEXT, updated_at TEXT)""")
            conn.execute("INSERT INTO applications VALUES(7,'Legacy Ltd','Intern','Leeds',NULL,NULL,'Saved','','2026-01-01','2026-01-01')")
        initialise(old)
        self.assertEqual(ApplicationRepository(old).get(7)["company"], "Legacy Ltd")
        with connection(old) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertGreater(ApplicationRepository(old).create(example())["id"], 7)

    def test_failed_migration_is_atomic(self):
        old = Path(self.temp.name) / "invalid-legacy.db"
        with connection(old) as conn:
            conn.execute("""CREATE TABLE applications (
                id INTEGER PRIMARY KEY, company TEXT, role TEXT, location TEXT,
                url TEXT, deadline TEXT, status TEXT, notes TEXT, created_at TEXT, updated_at TEXT)""")
            conn.execute("INSERT INTO applications VALUES(1,'Legacy','Intern','',NULL,NULL,'Typo','','x','x')")
        with self.assertRaises(sqlite3.IntegrityError):
            initialise(old)
        with connection(old) as conn:
            self.assertEqual(conn.execute("SELECT status FROM applications").fetchone()[0], "Typo")
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='applications_v1'").fetchone())

    def test_future_schema_is_rejected(self):
        with connection(self.path) as conn:
            conn.execute("PRAGMA user_version = 99")
        with self.assertRaises(RuntimeError):
            initialise(self.path)


if __name__ == "__main__":
    unittest.main()
