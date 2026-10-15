"""Local operator command: python -m app.manage CLAIM_ID Approved|Rejected."""
import argparse

from .database import get_connection, init_db


def update_status(claim_id, status):
    if status not in ("Approved", "Rejected"):
        raise ValueError("Status must be Approved or Rejected.")
    with get_connection() as connection:
        row = connection.execute("SELECT status FROM expenses WHERE id = ?", (claim_id,)).fetchone()
        if row is None:
            raise ValueError("Claim not found.")
        if row["status"] != "Submitted":
            raise ValueError("Only Submitted claims can be reviewed.")
        result = connection.execute(
            "UPDATE expenses SET status = ? WHERE id = ? AND status = 'Submitted'", (status, claim_id)
        )
        if result.rowcount != 1:
            raise ValueError("This claim has already been reviewed.")


def main():
    parser = argparse.ArgumentParser(description="Approve or reject a submitted expense claim.")
    parser.add_argument("claim_id", type=int)
    parser.add_argument("status", choices=["Approved", "Rejected"])
    args = parser.parse_args()
    init_db()
    try:
        update_status(args.claim_id, args.status)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(f"Claim #{args.claim_id}: {args.status}")


if __name__ == "__main__":
    main()
