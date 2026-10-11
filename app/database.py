import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("EXPENSE_DB_PATH", "expenses.db"))


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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
