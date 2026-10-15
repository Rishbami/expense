"""Manager-only claim queue and final review decisions."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from .auth import current_manager
from .database import get_connection
from .expenses import expense_response

router = APIRouter(prefix="/api/reviews", tags=["Manager reviews"])
CLAIM_SELECT = (
    "SELECT expenses.*, users.username AS claimant_username "
    "FROM expenses JOIN users ON users.id = expenses.user_id "
)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Approved", "Rejected"]


@router.get("")
def list_reviews(manager=Depends(current_manager)):
    with get_connection() as connection:
        rows = connection.execute(
            CLAIM_SELECT + "WHERE expenses.status = 'Submitted' AND expenses.user_id != ? "
            "ORDER BY expenses.id DESC", (manager["id"],)
        ).fetchall()
    return [expense_response(row) for row in rows]


@router.get("/{expense_id}")
def get_review(expense_id: int, manager=Depends(current_manager)):
    with get_connection() as connection:
        row = connection.execute(CLAIM_SELECT + "WHERE expenses.id = ?", (expense_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Claim not found.")
    return expense_response(row)


@router.post("/{expense_id}")
def review_expense(expense_id: int, decision: ReviewDecision, manager=Depends(current_manager)):
    with get_connection() as connection:
        # The conditional write ensures that only one competing decision can succeed.
        result = connection.execute(
            "UPDATE expenses SET status = ? "
            "WHERE id = ? AND status = 'Submitted' AND user_id != ?",
            (decision.status, expense_id, manager["id"]),
        )
        row = connection.execute(CLAIM_SELECT + "WHERE expenses.id = ?", (expense_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Claim not found.")
        if row["user_id"] == manager["id"]:
            raise HTTPException(403, "You cannot review your own claim.")
        if result.rowcount != 1:
            raise HTTPException(409, "This claim has already been reviewed. Refresh the queue.")
    return expense_response(row)
