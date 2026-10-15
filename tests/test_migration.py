import time

from fastapi.testclient import TestClient

from app.auth import token_hash
from app.database import get_connection, init_db
from app.main import app


def test_original_database_upgrade_preserves_data_and_sessions():
    # Start with the original schema, before manager permissions existed.
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO app_metadata VALUES ('schema_version', '1'), ('starter', 'preserved');
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
            INSERT INTO users VALUES (1, 'alice', 'existing-password-hash');
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at INTEGER NOT NULL);
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                description TEXT NOT NULL, expense_date TEXT NOT NULL, amount_pence INTEGER NOT NULL,
                submitted_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Submitted'
            );
            INSERT INTO expenses VALUES (1, 1, 'Old claim', '2025-01-01', 1234, '2025-01-02T12:00:00+00:00', 'Submitted');
            INSERT INTO expenses VALUES (2, 1, 'Reviewed claim', '2025-01-01', 9900, '2025-01-02T12:00:00+00:00', 'Approved');
        """)
        connection.execute("INSERT INTO sessions VALUES (?, 1, ?)", (token_hash("existing-session"), int(time.time()) + 3600))
        before = [dict(row) for row in connection.execute("SELECT * FROM expenses ORDER BY id")]
    init_db()
    init_db()
    with TestClient(app) as client:
        client.cookies.set("expense_session", "existing-session")
        assert client.get("/api/auth/me").json() == {"id": 1, "username": "alice", "is_manager": False}
        assert client.get("/api/reviews").status_code == 403
        assert client.get("/api/expenses/1").json()["amount"] == "12.34"
        assert len(client.get("/api/expenses").json()) == 2
    with get_connection() as connection:
        assert [dict(row) for row in connection.execute("SELECT * FROM expenses ORDER BY id")] == before
        assert dict(connection.execute("SELECT * FROM users").fetchone()) == {
            "id": 1, "username": "alice", "password_hash": "existing-password-hash", "is_manager": 0,
        }
        metadata = dict(connection.execute("SELECT key, value FROM app_metadata").fetchall())
        assert metadata == {"schema_version": "2", "starter": "preserved"}
