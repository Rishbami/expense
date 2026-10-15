# Expense Claims

A small FastAPI + SQLite application for submitting and tracking expense claims.
The browser interface uses plain HTML, CSS, and JavaScript; no frontend build is required.

## Run locally

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and create an account. Usernames are case insensitive,
3–40 letters, numbers, underscores or hyphens. Passwords are 10–128 characters.
Registration signs you in immediately. Sessions expire after seven days; logging
out invalidates the current session.

Submit an expense with a description, date, and GBP amount. Dates must be within
the past calendar year, including the cutoff date and today (using UTC). For
example, on 15 October 2026 the earliest accepted date is 15 October 2025.
On 29 February the cutoff is 28 February of the previous year. This rule applies
to new submissions; existing claims remain visible. Amounts must be £0.01–£999,999.99 with at most
two decimal places. Claims appear newest first with their submission time and
status. Click **Refresh** to see status updates. Each user can see only their
own claims. Submitted claims cannot be edited or deleted.

## Review a claim locally

Use the claim number shown in the interface. From the project directory, with
the same environment and database path as the server:

```bash
python -m app.manage 1 Approved
python -m app.manage 2 Rejected
```

Only **Submitted** claims can become **Approved** or **Rejected**. A completed
review cannot be reversed. Missing claims and repeat reviews exit with an error.
This command is for the local operator with access to the database; there is no
browser reviewer role or public status update endpoint.

## Storage and configuration

SQLite creates its tables on startup and preserves accounts and claims across
restarts. The existing starter metadata table is preserved. Database connections
are closed after each operation. Amounts are stored as integer pennies.

- `EXPENSE_DB_PATH`: database file path, default `expenses.db` relative to the
  working directory. Use an absolute path when running from different directories.
- `EXPENSE_SECURE_COOKIES=1`: require HTTPS for session cookies when hosting
  behind HTTPS. Leave unset for local HTTP development. A reverse proxy must
  forward the original host and scheme correctly for same-origin checks.

Passwords use salted PBKDF2-SHA256 hashes; only session token hashes are stored
in the database. Cookies are HttpOnly and SameSite=Strict. Cross-origin writes
are rejected and API responses are marked no-store. Keep the database private.
This scope does not include password recovery, public-service login rate limiting,
receipt uploads, multiple currencies, reports, or notifications.

API documentation: http://127.0.0.1:8000/docs. Health check: `/health`.
The session cookie authenticates the expense API; register/login first in the
browser or API documentation to use protected endpoints.

## Verification

```bash
pytest -q
node --check app/static/app.js  # optional, requires Node.js
```

Tests use isolated temporary databases, including the health test, and do not
write to your application database. They cover authentication, cookie settings,
expired/revoked sessions, user isolation, validation, exact amounts, persistence,
status transitions, cross-origin protection, and serving the interface.

For a manual browser check:

1. Create an account and submit a claim. Check its amount, date, and Submitted status.
2. Reload the page and confirm the claim remains.
3. Run the review command for that claim, then click Refresh and confirm its status.
4. Log out, create another account, and confirm its list starts empty.
5. Log back into the first account and confirm its claim is still present.
6. Check the layout at a narrow mobile width and try invalid form values.
