import sqlite3
from pathlib import Path


class Store:
    """The lookup table: real value <-> stand-in.

    SQLite rather than a JSON file because the numbering has to survive restarts
    ([Person 4] tomorrow is the same person as today) and two processes writing a
    JSON file at once would lose rows. This file is the one thing that must never
    leave your machine: it's the key to every stand-in.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS pseudonyms (
                               real       TEXT NOT NULL,
                               real_lower TEXT NOT NULL UNIQUE,
                               kind       TEXT NOT NULL,
                               token      TEXT NOT NULL)""")
        self.db.commit()

    def rows(self):
        return self.db.execute("SELECT real, token, kind FROM pseudonyms ORDER BY rowid").fetchall()

    def get_or_add(self, real, kind, label):
        row = self.db.execute("SELECT token FROM pseudonyms WHERE real_lower = ?", (real.lower(),)).fetchone()
        if row:
            return row[0]
        # numbered per label, so the third clinic is [Clinic 3] whatever else came before it
        n = self.db.execute("SELECT count(*) FROM pseudonyms WHERE token LIKE ?", (f"[{label} %",)).fetchone()[0]
        token = f"[{label} {n + 1}]"
        self.db.execute("INSERT INTO pseudonyms (real, real_lower, kind, token) VALUES (?, ?, ?, ?)",
                        (real, real.lower(), kind, token))
        self.db.commit()
        return token

    def close(self):
        self.db.close()
