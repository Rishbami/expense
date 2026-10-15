from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .auth import current_user
from .database import get_connection

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])


class ExpenseSubmission(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    expense_date: date
    amount: Decimal = Field(gt=0, le=Decimal("999999.99"), max_digits=8, decimal_places=2)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a description.")
        return value

    @field_validator("expense_date")
    @classmethod
    def validate_date(cls, value):
        today = datetime.now(timezone.utc).date()
        # February 29 uses February 28 as the previous year's anniversary.
        earliest = today.replace(
            year=today.year - 1,
            day=min(today.day, monthrange(today.year - 1, today.month)[1]),
        )
        if value < earliest:
            raise ValueError("Expense date must be within the past calendar year.")
        if value > today:
            raise ValueError("Expense date cannot be in the future.")
        return value


def expense_response(row):
    return {**dict(row), "amount": f"{Decimal(row['amount_pence']) / 100:.2f}", "currency": "GBP"}


@router.post("", status_code=201)
def submit_expense(expense: ExpenseSubmission, user=Depends(current_user)):
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO expenses (user_id, description, expense_date, amount_pence, submitted_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user["id"], expense.description, expense.expense_date.isoformat(),
             int(expense.amount * 100), datetime.now(timezone.utc).isoformat()),
        )
        row = connection.execute("SELECT * FROM expenses WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return expense_response(row)


@router.get("")
def list_expenses(user=Depends(current_user)):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC", (user["id"],)
        ).fetchall()
    return [expense_response(row) for row in rows]


@router.get("/{expense_id}")
def get_expense(expense_id: int, user=Depends(current_user)):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user["id"])
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Claim not found.")
    return expense_response(row)
