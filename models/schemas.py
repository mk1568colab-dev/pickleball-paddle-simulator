"""Typed data structures used by the simulator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MarketReport:
    """Public market conditions shared with all teams."""

    round_number: int
    total_demand: int
    premium_share: float
    mid_share: float
    beginner_share: float
    material_cost_index: float
    supply_risk: str
    quality_sensitivity: float
    event: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MarketReport":
        """Create a market report from stored JSON with safe defaults."""
        return cls(
            round_number=int(payload.get("round_number", 1)),
            total_demand=int(payload.get("total_demand", 0)),
            premium_share=float(payload.get("premium_share", 0.33)),
            mid_share=float(payload.get("mid_share", 0.34)),
            beginner_share=float(payload.get("beginner_share", 0.33)),
            material_cost_index=float(payload.get("material_cost_index", 1.0)),
            supply_risk=str(payload.get("supply_risk", "Moderate")),
            quality_sensitivity=float(payload.get("quality_sensitivity", 0.5)),
            event=str(payload.get("event", "")),
        )

    def share_total(self) -> float:
        """Return the raw total of the demand shares."""
        return self.premium_share + self.mid_share + self.beginner_share

    def normalized_shares(self) -> dict[str, float]:
        """Return demand shares normalized for round calculations."""
        total = self.share_total()
        if total <= 0:
            return {
                "premium": 1 / 3,
                "mid": 1 / 3,
                "beginner": 1 / 3,
            }

        return {
            "premium": self.premium_share / total,
            "mid": self.mid_share / total,
            "beginner": self.beginner_share / total,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the market report into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class AppUser:
    """Authenticated application user."""

    user_id: int
    username: str
    role: str
    team_name: str | None = None
    is_active: bool = True
    password_hash: str = field(default="", repr=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppUser":
        """Create a user object from database or session payloads."""
        return cls(
            user_id=int(payload.get("user_id", 0)),
            username=str(payload.get("username", "")),
            role=str(payload.get("role", "")),
            team_name=(
                str(payload["team_name"])
                if payload.get("team_name") not in (None, "")
                else None
            ),
            is_active=bool(payload.get("is_active", True)),
            password_hash=str(payload.get("password_hash", "")),
        )

    def to_dict(self, include_password_hash: bool = False) -> dict[str, Any]:
        """Serialize the user into a JSON-friendly dictionary."""
        payload = asdict(self)
        if not include_password_hash:
            payload.pop("password_hash", None)
        return payload


@dataclass
class TeamArchetype:
    """Reference profile that describes a team's operating baseline."""

    name: str
    description: str
    default_price_level: str
    default_capacity_plan: str
    default_quality_level: str
    default_inventory_posture: str
    base_cost: float
    base_capacity: int
    base_reputation: float
    base_defect_rate: float
    premium_fit: float
    mid_fit: float
    beginner_fit: float

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamArchetype":
        """Create an archetype from stored JSON with migration-friendly defaults."""
        return cls(
            name=str(payload.get("name", "Generic Team")),
            description=str(payload.get("description", "")),
            default_price_level=str(payload.get("default_price_level", "Mid")),
            default_capacity_plan=str(payload.get("default_capacity_plan", "Maintain")),
            default_quality_level=str(payload.get("default_quality_level", "Standard")),
            default_inventory_posture=str(
                payload.get("default_inventory_posture", "Balanced")
            ),
            base_cost=float(payload.get("base_cost", 70.0)),
            base_capacity=int(payload.get("base_capacity", 300)),
            base_reputation=float(payload.get("base_reputation", 50.0)),
            base_defect_rate=float(payload.get("base_defect_rate", 0.05)),
            premium_fit=float(payload.get("premium_fit", 0.34)),
            mid_fit=float(payload.get("mid_fit", 0.33)),
            beginner_fit=float(payload.get("beginner_fit", 0.33)),
        )

    def fit_for_segment(self, segment: str) -> float:
        """Return the configured fit for a demand segment."""
        return {
            "premium": self.premium_fit,
            "mid": self.mid_fit,
            "beginner": self.beginner_fit,
        }[segment]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the archetype into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class TeamDecision:
    """Operational choices submitted by a team for a round."""

    team_name: str
    archetype: str
    price_level: str
    production_quantity: int
    capacity_plan: str
    quality_level: str
    inventory_posture: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamDecision":
        """Create a decision from stored JSON."""
        return cls(
            team_name=str(payload.get("team_name", "")).strip(),
            archetype=str(payload.get("archetype", "")),
            price_level=str(payload.get("price_level", "Mid")),
            production_quantity=int(payload.get("production_quantity", 0)),
            capacity_plan=str(payload.get("capacity_plan", "Maintain")),
            quality_level=str(payload.get("quality_level", "Standard")),
            inventory_posture=str(payload.get("inventory_posture", "Balanced")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the team decision into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class RoundResult:
    """Round-level operating and financial output for one team."""

    round_number: int
    team_name: str
    archetype: str
    demand_allocated: float = 0.0
    sales_units: int = 0
    stockout_units: int = 0
    ending_inventory: int = 0
    fill_rate: float = 1.0
    unit_price: float = 0.0
    revenue: float = 0.0
    production_cost: float = 0.0
    holding_cost: float = 0.0
    warranty_cost: float = 0.0
    expansion_cost: float = 0.0
    total_cost: float = 0.0
    profit: float = 0.0
    defect_rate: float = 0.0
    available_capacity: int = 0
    good_units_produced: int = 0
    reputation_after_round: float = 0.0
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RoundResult":
        """Create a round result from stored JSON, including legacy placeholder rows."""
        notes = str(payload.get("notes", ""))
        placeholder_status = payload.get("placeholder_status")
        if placeholder_status:
            notes = f"{notes} Legacy status: {placeholder_status}.".strip()

        return cls(
            round_number=int(payload.get("round_number", 0)),
            team_name=str(payload.get("team_name", "")),
            archetype=str(payload.get("archetype", "")),
            demand_allocated=float(payload.get("demand_allocated", 0.0)),
            sales_units=int(payload.get("sales_units", 0)),
            stockout_units=int(payload.get("stockout_units", 0)),
            ending_inventory=int(payload.get("ending_inventory", 0)),
            fill_rate=float(payload.get("fill_rate", 1.0)),
            unit_price=float(payload.get("unit_price", 0.0)),
            revenue=float(payload.get("revenue", 0.0)),
            production_cost=float(payload.get("production_cost", 0.0)),
            holding_cost=float(payload.get("holding_cost", 0.0)),
            warranty_cost=float(payload.get("warranty_cost", 0.0)),
            expansion_cost=float(payload.get("expansion_cost", 0.0)),
            total_cost=float(payload.get("total_cost", 0.0)),
            profit=float(payload.get("profit", 0.0)),
            defect_rate=float(payload.get("defect_rate", 0.0)),
            available_capacity=int(payload.get("available_capacity", 0)),
            good_units_produced=int(payload.get("good_units_produced", 0)),
            reputation_after_round=float(payload.get("reputation_after_round", 0.0)),
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the round result into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class PersistentTeamState:
    """Team state that is preserved across rounds."""

    team_name: str
    archetype: str
    cash_balance: float = 0.0
    inventory_units: int = 0
    capacity_units: int = 0
    reputation_score: float = 50.0
    completed_rounds: list[int] = field(default_factory=list)
    last_decision: dict[str, Any] = field(default_factory=dict)
    cumulative_profit: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersistentTeamState":
        """Create persistent team state from stored JSON with safe defaults."""
        return cls(
            team_name=str(payload.get("team_name", "")),
            archetype=str(payload.get("archetype", "")),
            cash_balance=float(payload.get("cash_balance", 0.0)),
            inventory_units=int(payload.get("inventory_units", 0)),
            capacity_units=int(payload.get("capacity_units", 0)),
            reputation_score=float(payload.get("reputation_score", 50.0)),
            completed_rounds=[
                int(round_number)
                for round_number in payload.get("completed_rounds", [])
            ],
            last_decision=dict(payload.get("last_decision", {})),
            cumulative_profit=float(payload.get("cumulative_profit", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the persistent team state into a JSON-friendly dictionary."""
        return asdict(self)
