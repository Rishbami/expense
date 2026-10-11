# Expense Tracker — Starter Repository

A deliberately minimal Python FastAPI + SQLite foundation for an AI-agent coursework exercise.

## What exists
- FastAPI application with `GET /health`.
- SQLite connection helper and a minimal `app_metadata` table, created on startup.
- A basic health endpoint test.

## What does **not** exist
There is no expense data model, expense CRUD API, validation, totals, filters, or user interface. Those are intentionally left for the delegated agent task. The starter does not prescribe how to implement them.

## Run locally
Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for API documentation or `http://127.0.0.1:8000/health` for the health check.

## Test
```bash
pytest -q
```

## Suggested coursework workflow
1. Unzip this project and commit it to a **new Git repository** as the starting point.
2. Record the repository URL and starting commit SHA for Section 2.
3. Write your own outcome-focused specification and preserve the **exact** prompt you give Claude Code.
4. Ask the agent to produce its plan before making code changes; capture that original plan.
5. Record implementation and genuine observe/adjust behaviour; supervise permissions and interventions.
6. Verify the final code independently and compare it with the starting commit.

Do not claim any agent activity has occurred in this starter: none has.
