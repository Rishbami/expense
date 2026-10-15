from app.database import get_connection


def test_auth_lifecycle(client, account):
    assert client.get("/api/auth/me").json() == account
    cookie = client.cookies["expense_session"]
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("expense_session", cookie)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"username": "ALICE", "password": "a-long-password"}).status_code == 200
    assert client.get("/api/auth/me").json() == account


def test_duplicate_invalid_and_incorrect_credentials(client, account):
    assert client.post("/api/auth/register", json={"username": "ALICE", "password": "a-long-password"}).status_code == 409
    for username, password in [("x", "a-long-password"), ("bad name", "a-long-password"), ("alice", "short")]:
        assert client.post("/api/auth/register", json={"username": username, "password": password}).status_code == 422
    for username in ("alice", "unknown"):
        assert client.post("/api/auth/login", json={"username": username, "password": "wrong-password"}).status_code == 401


def test_auth_required_and_expired_sessions(client, account):
    with get_connection() as connection:
        connection.execute("UPDATE sessions SET expires_at = 0")
    for path in ("/api/auth/me", "/api/expenses", "/api/expenses/1"):
        assert client.get(path).status_code == 401
    assert client.post("/api/expenses", json={"description": "Test", "expense_date": "2025-01-01", "amount": "1"}).status_code == 401
    client.cookies.set("expense_session", "forged")
    assert client.get("/api/expenses").status_code == 401


def test_cookie_security_and_cross_origin_protection(client, monkeypatch):
    response = client.post("/api/auth/register", json={"username": "alice", "password": "a-long-password"})
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    assert client.post("/api/auth/logout", headers={"Origin": "https://other.example"}).status_code == 403
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout", headers={"Origin": "http://testserver"}).status_code == 204
    monkeypatch.setenv("EXPENSE_SECURE_COOKIES", "1")
    response = client.post("/api/auth/login", json={"username": "alice", "password": "a-long-password"})
    assert "Secure" in response.headers["set-cookie"]


def test_interface_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="expense-form"' in response.text
    for path, mime in (("/static/app.js", "javascript"), ("/static/styles.css", "text/css")):
        asset = client.get(path)
        assert asset.status_code == 200
        assert mime in asset.headers["content-type"]
    assert "default-src 'self'" in response.headers["content-security-policy"]
    # The docs use CDN assets and inline scripts, unlike the application UI.
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "content-security-policy" not in docs.headers
