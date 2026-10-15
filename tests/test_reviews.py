from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.database import get_connection
from app.main import app
from app.manage import update_status


def register_manager(client, username="manager", **changes):
    return client.post("/api/auth/register-manager", json={
        "username": username, "password": "manager-password", "verification_code": "1234", **changes,
    })


def submit(client, **changes):
    response = client.post("/api/expenses", json={
        "description": "Train to client", "expense_date": datetime.now(timezone.utc).date().isoformat(),
        "amount": "12.34", **changes,
    })
    assert response.status_code == 201
    return response.json()


def test_manager_registration_and_login(client):
    response = register_manager(client, username="MANAGER")
    assert response.status_code == 201
    manager = response.json()
    assert manager["username"] == "manager"
    assert manager["is_manager"] is True
    assert "verification_code" not in manager
    assert client.get("/api/auth/me").json() == manager
    assert client.get("/api/reviews").json() == []
    assert register_manager(client).status_code == 409
    client.post("/api/auth/logout")
    response = client.post("/api/auth/login", json={"username": "MANAGER", "password": "manager-password"})
    assert response.json() == manager
    with get_connection() as connection:
        assert set(connection.execute("SELECT * FROM users").fetchone().keys()) == {
            "id", "username", "password_hash", "is_manager",
        }


@pytest.mark.parametrize("code, expected", [("wrong", 403), ("", 422), (None, 422), (1234, 422)])
def test_invalid_manager_code_creates_no_account_or_session(client, code, expected):
    response = register_manager(client, verification_code=code)
    assert response.status_code == expected
    assert "set-cookie" not in response.headers
    assert client.get("/api/auth/me").status_code == 401
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_missing_and_configurable_manager_code(client, monkeypatch):
    credentials = {"username": "manager", "password": "manager-password"}
    assert client.post("/api/auth/register-manager", json=credentials).status_code == 422
    monkeypatch.setenv("EXPENSE_MANAGER_CODE", "custom-secret")
    assert register_manager(client).status_code == 403
    assert register_manager(client, verification_code="custom-secret").status_code == 201
    monkeypatch.setenv("EXPENSE_MANAGER_CODE", "")
    assert register_manager(client, username="other", verification_code="1234").status_code == 403


def test_regular_registration_cannot_assign_manager_role(client):
    response = client.post("/api/auth/register", json={
        "username": "alice", "password": "a-long-password", "is_manager": True,
        "role": "manager", "verification_code": "1234",
    })
    assert response.status_code == 201
    assert response.json()["is_manager"] is False
    assert client.get("/api/auth/me").json()["is_manager"] is False
    assert client.get("/api/reviews").status_code == 403
    # Manager registration cannot upgrade or replace an existing ordinary account.
    assert register_manager(client, username="alice").status_code == 409
    assert client.get("/api/auth/me").json()["is_manager"] is False


def assert_review_access_denied(client, claim_id, status):
    assert client.get("/api/reviews").status_code == status
    assert client.get(f"/api/reviews/{claim_id}").status_code == status
    for decision in ("Approved", "Rejected"):
        assert client.post(f"/api/reviews/{claim_id}", json={"status": decision}).status_code == status


def test_ordinary_users_and_anonymous_requests_cannot_review(client, account):
    claim = submit(client)
    assert_review_access_denied(client, claim["id"], 403)
    client.post("/api/auth/logout")
    assert_review_access_denied(client, claim["id"], 401)
    client.post("/api/auth/register", json={"username": "bob", "password": "another-password"})
    assert_review_access_denied(client, claim["id"], 403)
    assert client.get(f"/api/expenses/{claim['id']}").status_code == 404
    with get_connection() as connection:
        assert connection.execute("SELECT status FROM expenses").fetchone()[0] == "Submitted"


@pytest.mark.parametrize("status", ["Approved", "Rejected"])
def test_manager_review_and_claimant_tracking(client, account, status):
    claim = submit(client)
    second = submit(client, description="Hotel", amount="100.01")
    register_manager(client)
    own = submit(client, description="Manager's own claim")
    queue = client.get("/api/reviews").json()
    assert [row["id"] for row in queue] == [second["id"], claim["id"]]
    assert queue[1] == {**claim, "claimant_username": "alice"}
    assert client.get(f"/api/reviews/{claim['id']}").json() == queue[1]
    assert client.get(f"/api/expenses/{claim['id']}").status_code == 404
    assert [row["id"] for row in client.get("/api/expenses").json()] == [own["id"]]
    response = client.post(f"/api/reviews/{claim['id']}", json={"status": status})
    assert response.status_code == 200
    assert response.json() == {**claim, "claimant_username": "alice", "status": status}
    for repeat in ("Approved", "Rejected"):
        assert client.post(f"/api/reviews/{claim['id']}", json={"status": repeat}).status_code == 409
    assert [row["id"] for row in client.get("/api/reviews").json()] == [second["id"]]
    client.post("/api/auth/login", json={"username": "alice", "password": "a-long-password"})
    assert client.get(f"/api/expenses/{claim['id']}").json()["status"] == status
    assert client.get("/api/expenses").json()[1]["status"] == status


def test_manager_cannot_review_own_claim(client):
    register_manager(client)
    claim = submit(client)
    assert client.get("/api/reviews").json() == []
    for status in ("Approved", "Rejected"):
        assert client.post(f"/api/reviews/{claim['id']}", json={"status": status}).status_code == 403
    assert client.get(f"/api/expenses/{claim['id']}").json()["status"] == "Submitted"


def test_invalid_missing_and_locally_reviewed_claims(client, account):
    claim = submit(client)
    register_manager(client)
    for decision in ({}, {"status": "Submitted"}, {"status": "approved"}, {"status": None},
                     {"status": "Approved", "user_id": 999}):
        assert client.post(f"/api/reviews/{claim['id']}", json=decision).status_code == 422
    assert client.get(f"/api/reviews/{claim['id']}").json()["status"] == "Submitted"
    assert client.get("/api/reviews/9999").status_code == 404
    assert client.post("/api/reviews/9999", json={"status": "Approved"}).status_code == 404
    update_status(claim["id"], "Approved")
    assert client.get("/api/reviews").json() == []
    assert client.post(f"/api/reviews/{claim['id']}", json={"status": "Rejected"}).status_code == 409


def test_manager_permissions_checked_on_every_request(client, account):
    claim = submit(client)
    manager = register_manager(client).json()
    with get_connection() as connection:
        connection.execute("UPDATE users SET is_manager = 0 WHERE id = ?", (manager["id"],))
    assert client.get("/api/auth/me").json()["is_manager"] is False
    assert_review_access_denied(client, claim["id"], 403)
    with get_connection() as connection:
        connection.execute("UPDATE users SET is_manager = 1 WHERE id = ?", (manager["id"],))
        connection.execute("UPDATE sessions SET expires_at = 0")
    assert_review_access_denied(client, claim["id"], 401)


def test_cross_origin_manager_registration_and_review(client, account):
    claim = submit(client)
    response = client.post("/api/auth/register-manager", headers={"Origin": "https://other.example"},
                           json={"username": "manager", "password": "manager-password", "verification_code": "1234"})
    assert response.status_code == 403
    register_manager(client)
    response = client.post(f"/api/reviews/{claim['id']}", json={"status": "Approved"},
                           headers={"Origin": "https://other.example"})
    assert response.status_code == 403
    assert client.get(f"/api/reviews/{claim['id']}").json()["status"] == "Submitted"
    assert client.get("/api/reviews").headers["cache-control"] == "no-store"
    assert client.post(f"/api/reviews/{claim['id']}", json={"status": "Approved"},
                       headers={"Origin": "http://testserver"}).status_code == 200


def test_competing_manager_decisions_only_one_succeeds(client, account):
    claim = submit(client)
    barrier = Barrier(2)
    with TestClient(app) as first, TestClient(app) as second:
        assert register_manager(first, username="first").status_code == 201
        assert register_manager(second, username="second").status_code == 201

        def decide(manager_client, status):
            barrier.wait(timeout=10)
            return manager_client.post(f"/api/reviews/{claim['id']}", json={"status": status})

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(decide, first, "Approved"), executor.submit(decide, second, "Rejected")]
            responses = [future.result(timeout=15) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json()["status"] for response in responses if response.status_code == 200)
    assert client.get(f"/api/expenses/{claim['id']}").json()["status"] == winner
