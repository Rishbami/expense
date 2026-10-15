import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("EXPENSE_DB_PATH", "expenses.db"))


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        connection.execute(
            "INSERT OR IGNORE INTO app_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "0"),
        )
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                description TEXT NOT NULL,
                expense_date TEXT NOT NULL,
                amount_pence INTEGER NOT NULL CHECK (amount_pence > 0),
                submitted_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted'
                    CHECK (status IN ('Submitted', 'Approved', 'Rejected'))
            );
            CREATE INDEX IF NOT EXISTS expenses_user_id ON expenses(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            UPDATE app_metadata SET value = '1' WHERE key = 'schema_version';
        """)
