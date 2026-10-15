from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_connection, init_db
from app import expenses
from app.main import app
from app.manage import update_status


def submission(**changes):
    return {"description": "Train to client", "expense_date": datetime.now(timezone.utc).date().isoformat(), "amount": "12.34", **changes}


def test_submission_list_detail_and_persistence(client, account):
    assert client.get("/api/expenses").json() == []
    response = client.post("/api/expenses", json=submission())
    assert response.status_code == 201
    claim = response.json()
    assert claim["amount_pence"] == 1234
    assert claim["amount"] == "12.34"
    assert claim["currency"] == "GBP"
    assert claim["status"] == "Submitted"
    assert claim["user_id"] == account["id"]
    assert datetime.fromisoformat(claim["submitted_at"]).tzinfo is not None
    assert client.get(f"/api/expenses/{claim['id']}").json() == claim
    second = client.post("/api/expenses", json=submission(amount="0.01")).json()
    assert [row["id"] for row in client.get("/api/expenses").json()] == [second["id"], claim["id"]]
    init_db()
    with TestClient(app) as restarted:
        restarted.cookies.update(client.cookies)
        assert len(restarted.get("/api/expenses").json()) == 2


@pytest.mark.parametrize("changes", [
    {"description": "  "}, {"description": "x" * 501}, {"description": None},
    {"amount": "0"}, {"amount": "-1"}, {"amount": "0.001"},
    {"amount": "1000000"}, {"amount": "NaN"}, {"amount": "Infinity"},
    {"expense_date": "invalid"},
    {"expense_date": (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()},
])
def test_invalid_submission(client, account, changes):
    assert client.post("/api/expenses", json=submission(**changes)).status_code == 422
    assert client.get("/api/expenses").json() == []


def test_required_fields_and_status_cannot_be_set(client, account):
    assert client.post("/api/expenses", json={}).status_code == 422
    claim = client.post("/api/expenses", json=submission(status="Approved", user_id=999)).json()
    assert claim["status"] == "Submitted"
    assert claim["user_id"] == account["id"]


def test_user_isolation(client, account):
    claim = client.post("/api/expenses", json=submission()).json()
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"username": "bob", "password": "another-password"})
    assert client.get("/api/expenses").json() == []
    assert client.get(f"/api/expenses/{claim['id']}").status_code == 404
    assert client.get("/api/expenses/9999").status_code == 404


@pytest.mark.parametrize("status", ["Approved", "Rejected"])
def test_review_status(client, account, status):
    claim = client.post("/api/expenses", json=submission()).json()
    update_status(claim["id"], status)
    assert client.get(f"/api/expenses/{claim['id']}").json()["status"] == status
    assert client.get("/api/expenses").json()[0]["status"] == status
    with pytest.raises(ValueError, match="Only Submitted"):
        update_status(claim["id"], "Rejected" if status == "Approved" else "Approved")
    assert client.patch(f"/api/expenses/{claim['id']}", json={"status": "Submitted"}).status_code == 405


def test_review_invalid_claim_or_status(client):
    with pytest.raises(ValueError, match="not found"):
        update_status(9999, "Approved")
    with pytest.raises(ValueError, match="Status must"):
        update_status(1, "Something else")


def test_no_plaintext_passwords_or_session_tokens(client, account):
    with get_connection() as connection:
        password_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
        session = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert "a-long-password" not in password_hash
    assert session != client.cookies["expense_session"]


@pytest.mark.parametrize("today, cutoff", [
    (date(2026, 10, 15), date(2025, 10, 15)),
    (date(2024, 2, 29), date(2023, 2, 28)),
    (date(2025, 2, 28), date(2024, 2, 28)),
    (date(2025, 3, 1), date(2024, 3, 1)),
    (date(2026, 1, 1), date(2025, 1, 1)),
])
def test_one_year_submission_window(client, account, monkeypatch, today, cutoff):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(today.year, today.month, today.day, tzinfo=timezone.utc)

    monkeypatch.setattr(expenses, "datetime", FixedDatetime)
    for accepted in (cutoff, cutoff + timedelta(days=1), today):
        response = client.post("/api/expenses", json=submission(expense_date=accepted.isoformat()))
        assert response.status_code == 201
    for rejected in (cutoff - timedelta(days=1), today + timedelta(days=1)):
        response = client.post("/api/expenses", json=submission(expense_date=rejected.isoformat()))
        assert response.status_code == 422
    assert "past calendar year" in client.post(
        "/api/expenses", json=submission(expense_date=(cutoff - timedelta(days=1)).isoformat())
    ).text
    assert len(client.get("/api/expenses").json()) == 3
    # Ageing claims remain readable after the submission window moves on.
    monkeypatch.setattr(expenses, "datetime", datetime)
    assert client.get("/api/expenses").status_code == 200
    assert len(client.get("/api/expenses").json()) == 3
