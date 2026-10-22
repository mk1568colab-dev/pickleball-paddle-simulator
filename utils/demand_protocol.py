"""Public outlook and instructor-only demand commitment for each round."""
from dataclasses import replace

from utils.bootstrap import ensure_app_storage
from utils.database import get_connection


def demand_status(round_number):
    ensure_app_storage()
    with get_connection() as db:
        row = db.execute("SELECT * FROM demand_commitments WHERE round_number = ?", (round_number,)).fetchone()
    return dict(row) if row else None


def save_outlook(round_number, low, high):
    if low < 0 or high <= low:
        raise ValueError("Outlook upper bound must exceed its nonnegative lower bound.")
    ensure_app_storage()
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT locked_at FROM demand_commitments WHERE round_number = ?", (round_number,)).fetchone()
        if row and row[0]:
            raise ValueError("This round is locked. Closing submissions does not unlock it.")
        db.execute("""INSERT INTO demand_commitments(round_number, outlook_low, outlook_high)
            VALUES (?, ?, ?) ON CONFLICT(round_number) DO UPDATE SET
            outlook_low=excluded.outlook_low, outlook_high=excluded.outlook_high""", (round_number, low, high))


def public_market_row(report):
    row = report.to_dict()
    row.pop("total_demand", None)
    status = demand_status(report.round_number)
    row["demand_outlook_low"] = status["outlook_low"] if status else "Not published"
    row["demand_outlook_high"] = status["outlook_high"] if status else "Not published"
    if status and status["completed_at"]:
        row["actual_total_demand"] = status["actual_demand"]
    return row


def planning_market_report(report):
    """Never allow private realized demand to affect student planning previews."""
    status = demand_status(report.round_number)
    midpoint = round((status["outlook_low"] + status["outlook_high"]) / 2) if status else 0
    return replace(report, total_demand=midpoint)


def committed_report(report):
    status = demand_status(report.round_number)
    if not status or not status["locked_at"] or status["completed_at"]:
        raise ValueError("Open and close submissions before running an unfinished round.")
    return replace(report, total_demand=status["actual_demand"])


def complete_demand_round(round_number):
    with get_connection() as db:
        db.execute("UPDATE demand_commitments SET completed_at=CURRENT_TIMESTAMP WHERE round_number=? AND locked_at IS NOT NULL", (round_number,))


def revealed_demands():
    ensure_app_storage()
    with get_connection() as db:
        return [dict(r) for r in db.execute("""SELECT round_number, outlook_low, outlook_high,
            actual_demand FROM demand_commitments WHERE completed_at IS NOT NULL ORDER BY round_number""")]
