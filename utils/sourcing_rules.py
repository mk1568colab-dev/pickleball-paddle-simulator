"""Opt-in shipping rules for new classrooms; existing games stay unchanged."""

from dataclasses import dataclass
import secrets

from utils.database import get_connection


@dataclass(frozen=True)
class DeliveryPolicy:
    seed: str
    order_fee: float = 300.0
    version: int = 2
    additional_supplier_fee: float = 75.0


def load_delivery_policy():
    with get_connection() as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='delivery_policy'"
        ).fetchone():
            return None
        row = connection.execute("SELECT * FROM delivery_policy WHERE singleton=1").fetchone()
        if row and row['version'] not in (1, 2):
            raise ValueError("Unsupported delivery policy version.")
        if not row:
            return None
        values = dict(row)
        values.pop('singleton')
        return DeliveryPolicy(**values)


def initialize_delivery_policy():
    """Setup-only entry point. Never opt an in-progress game into new rules."""
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for table in ('round_results', 'team_decisions', 'demand_commitments'):
            if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                raise ValueError("Shipping rules must be enabled before the new game begins.")
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='delivery_policy'").fetchone():
            return
        connection.execute("""CREATE TABLE IF NOT EXISTS delivery_policy (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            version INTEGER NOT NULL, seed TEXT NOT NULL, order_fee REAL NOT NULL,
            additional_supplier_fee REAL NOT NULL
        )""")
        connection.execute("INSERT INTO delivery_policy VALUES (1,2,?,300,75)",
                           (secrets.token_hex(32),))
