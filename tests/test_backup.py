import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backup import backup


class BackupTests(unittest.TestCase):
    def test_snapshot_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / 'data.db', Path(directory) / 'backup.db'
            conn = sqlite3.connect(source)
            self.addCleanup(conn.close)
            conn.execute('CREATE TABLE sample (value TEXT)')
            conn.execute("INSERT INTO sample VALUES ('original')")
            conn.commit()
            backup(source, destination)
            with sqlite3.connect(destination) as copied:
                self.assertEqual(copied.execute('SELECT value FROM sample').fetchone()[0], 'original')
                self.assertEqual(copied.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            copied.close()
            before = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                backup(source, destination)
            self.assertEqual(before, destination.read_bytes())
            with self.assertRaises(ValueError):
                backup(source, source)

    def test_missing_source_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'backup.db'
            with self.assertRaises(FileNotFoundError):
                backup(Path(directory) / 'missing.db', target)
            self.assertFalse(target.exists())
