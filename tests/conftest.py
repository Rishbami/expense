import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "expenses.db")
    monkeypatch.delenv("EXPENSE_MANAGER_CODE", raising=False)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def account(client):
    response = client.post("/api/auth/register", json={"username": "alice", "password": "a-long-password"})
    assert response.status_code == 201
    return response.json()
