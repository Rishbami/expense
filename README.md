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
own claims through the personal claims list. Submitted claims cannot be edited or deleted.

## Manager accounts and approvals

On the sign-in screen, choose **Create manager account**, enter a new username
and password, and supply the manager verification code. The default testing code
is **1234**. Registration signs the manager in immediately. Existing managers use
the normal login form; they do not need to enter the code again.

Set `EXPENSE_MANAGER_CODE` on the server to replace the testing code. Anyone who
knows this shared code can register a manager account, so replace it before
deployment and share it only with authorised managers. An explicitly empty value
disables manager registration. Changing the code does not change existing accounts.
Ordinary registration never grants manager access, and existing accounts remain
ordinary users after the database upgrade. Manager registration requires a new,
unused username; it cannot upgrade an existing account.

Managers see a **Manager approval dashboard** below their personal claims. The
queue contains Submitted claims from other users, newest first, with the claimant,
description, GBP amount, expense date, and submission time. Choose **Approve** or
**Reject** and confirm the final decision. The queue refreshes after review;
**Refresh queue** retrieves other managers' latest changes. Claimants can click
**Refresh** in their personal list to see the result.

Managers can still submit and track their own expenses, but cannot approve or
reject their own claims. Ordinary users cannot access the review API or make
decisions. All permissions are enforced by the server on each request. Competing
reviews allow only one decision; the other request receives a conflict.

Manager registration uses `POST /api/auth/register-manager` with `username`,
`password`, and `verification_code`. The protected review API is
`GET /api/reviews`, `GET /api/reviews/{claim_id}`, and
`POST /api/reviews/{claim_id}` with `{"status": "Approved"}` or
`{"status": "Rejected"}`. Personal expense endpoints remain restricted to the owner.

## Review a claim locally

Use the claim number shown in the interface. From the project directory, with
the same environment and database path as the server:

```bash
python -m app.manage 1 Approved
python -m app.manage 2 Rejected
```

Only **Submitted** claims can become **Approved** or **Rejected**. A completed
review cannot be reversed. Missing claims and repeat reviews exit with an error.
This command remains available to the trusted local operator with direct database
access. Application manager permissions apply to the authenticated review API.

## Storage and configuration

SQLite creates its tables on startup and preserves accounts and claims across
restarts. The existing starter metadata table is preserved. Database connections
are closed after each operation. Amounts are stored as integer pennies.
Startup automatically adds manager permissions to existing databases, preserving
accounts, password hashes, sessions, claims, statuses, and other metadata.

- `EXPENSE_DB_PATH`: database file path, default `expenses.db` relative to the
  working directory. Use an absolute path when running from different directories.
- `EXPENSE_SECURE_COOKIES=1`: require HTTPS for session cookies when hosting
  behind HTTPS. Leave unset for local HTTP development. A reverse proxy must
  forward the original host and scheme correctly for same-origin checks.
- `EXPENSE_MANAGER_CODE`: shared manager registration code, default `1234` for
  testing. Set a private code for deployment, or an empty value to disable new
  manager registration.

Passwords use salted PBKDF2-SHA256 hashes; only session token hashes are stored
in the database. Cookies are HttpOnly and SameSite=Strict. Cross-origin writes
are rejected and API responses are marked no-store. Keep the database private.
This scope does not include password recovery, public-service login rate limiting,
receipt uploads, multiple currencies, reports, or notifications.

API documentation: http://127.0.0.1:8000/docs. Health check: `/health`.
The session cookie authenticates the expense API; register/login first in the
browser or API documentation to use protected endpoints.

## Verification

From the project directory, activate the virtual environment created in the
setup steps, then run the tests:

```bash
source .venv/bin/activate
python -m pytest -q
node --check app/static/app.js  # optional, requires Node.js
```

Use `python -m pytest` so the tests run with the active Python environment and
can import the local `app` package. For individual test results and only the
manager and database upgrade tests:

```bash
python -m pytest -v tests/test_reviews.py tests/test_migration.py
```

Tests use isolated temporary databases, including the health test, and do not
write to your application database. They cover authentication, cookie settings,
expired/revoked sessions, user isolation, validation, exact amounts, persistence,
status transitions, cross-origin protection, and serving the interface. Manager
coverage includes code validation, privilege escalation attempts, self-review
prevention, role revocation, competing decisions, and original-schema upgrades.

For a manual browser check:

1. Create an account and submit a claim. Check its amount, date, and Submitted status.
2. Reload the page and confirm the claim remains.
3. Log out and choose **Create manager account**. Try an incorrect code, then
   register with `1234` (or your configured code).
4. Confirm the personal list starts empty and the manager queue shows the first
   user's claim with its details. Approve it and confirm it leaves the queue.
5. Submit a claim as the manager and confirm it stays out of their review queue.
6. Log back into the first account, confirm its claim is Approved, and confirm
   the manager dashboard is hidden. Submit another claim and repeat with rejection.
7. Check confirmation cancellation, refresh, session persistence after reload,
   invalid form values, and the layout at a narrow mobile width.
8. Optionally verify that the existing local review command still works.
