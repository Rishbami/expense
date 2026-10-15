import hashlib
import hmac
import os
import secrets
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from .database import get_connection

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
SESSION_SECONDS = 7 * 24 * 60 * 60
COOKIE_NAME = "expense_session"
ITERATIONS = 600_000


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        return value.lower()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"{salt}:{digest.hex()}"


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with get_connection() as connection:
            user = connection.execute(
                "SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id "
                "WHERE token_hash = ? AND expires_at > ?",
                (token_hash(token), int(time.time())),
            ).fetchone()
        if user:
            return dict(user)
    raise HTTPException(401, "Please log in to continue.")


def create_session(response, user_id):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash(token), user_id, now + SESSION_SECONDS),
        )
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True, samesite="strict",
        secure=os.environ.get("EXPENSE_SECURE_COOKIES", "0") == "1",
    )


@router.post("/register", status_code=201)
def register(credentials: Credentials, response: Response):
    password_hash = hash_password(credentials.password)
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (credentials.username, password_hash),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That username is already registered.")
    create_session(response, user_id)
    return {"id": user_id, "username": credentials.username}


@router.post("/login")
def login(credentials: Credentials, response: Response):
    with get_connection() as connection:
        user = connection.execute("SELECT * FROM users WHERE username = ?", (credentials.username,)).fetchone()
    # Perform the same expensive hash for unknown usernames.
    stored_hash = user["password_hash"] if user else "00" * 16 + ":" + "00" * 32
    salt = stored_hash.split(":")[0]
    if not hmac.compare_digest(hash_password(credentials.password, salt), stored_hash) or not user:
        raise HTTPException(401, "Incorrect username or password.")
    create_session(response, user["id"])
    return {"id": user["id"], "username": user["username"]}


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with get_connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
    response.delete_cookie(COOKIE_NAME)
