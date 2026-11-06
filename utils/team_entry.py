"""Classroom-specific starting reputation for newly initialized teams."""

from dataclasses import dataclass
from math import isfinite
import sqlite3

from data.classroom_start import COMMON_PROFILE
from utils.bootstrap import ensure_app_storage
from utils.database import get_connection

LATE_ENTRY_REPUTATION_DEDUCTION = 10.0


@dataclass(frozen=True)
class EntryReputation:
    score: float
    round_number: int | None
    team_count: int
    benchmark_score: float | None = None


def load_entry_reputation(connection: sqlite3.Connection | None = None) -> EntryReputation:
    """Freeze a discounted, capped entry score from this classroom's results."""
    if connection is None:
        ensure_app_storage()
        with get_connection() as connection:
            return load_entry_reputation(connection)

    # Old classrooms may have results from before demand commitments existed.
    completed_round = connection.execute(
        """
        SELECT MAX(r.round_number)
        FROM round_results AS r
        LEFT JOIN demand_commitments AS d ON d.round_number = r.round_number
        WHERE d.completed_at IS NOT NULL
           OR (d.round_number IS NULL AND r.round_number <
               (SELECT MAX(round_number) FROM market_reports))
        """
    ).fetchone()[0]
    scores = []
    if completed_round is not None:
        rows = connection.execute(
            """
            SELECT r.reputation_after_round
            FROM round_results AS r
            WHERE r.round_number = ?
              AND EXISTS (
                  SELECT 1 FROM users AS u
                  WHERE u.team_name = r.team_name COLLATE NOCASE
                    AND u.role = 'team_leader' AND u.is_active = 1
              )
            """,
            (completed_round,),
        ).fetchall()
        scores = sorted(float(row[0]) for row in rows
                        if row[0] is not None and isfinite(float(row[0]))
                        and 0 <= float(row[0]) <= 100)
    if not scores:
        score = COMMON_PROFILE.base_reputation
        if completed_round is not None:
            score = max(0.0, score - LATE_ENTRY_REPUTATION_DEDUCTION)
        return EntryReputation(score, completed_round, 0)

    # Linear interpolation: position 0.2 * (n - 1), not 20% of a score.
    position = 0.2 * (len(scores) - 1)
    lower = int(position)
    upper = min(lower + 1, len(scores) - 1)
    benchmark = scores[lower] + (position - lower) * (scores[upper] - scores[lower])
    score = max(0.0, min(benchmark, COMMON_PROFILE.base_reputation) - LATE_ENTRY_REPUTATION_DEDUCTION)
    return EntryReputation(round(score, 2), completed_round, len(scores), round(benchmark, 2))
