"""Typed data structures used by the simulator."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


PRODUCT_SLOT_NAMES = ("A", "B", "C")
PROJECT_SLOT_NAMES = ("P1", "P2")
TARGET_SEGMENTS = ("premium", "mid", "beginner")
LIFECYCLE_STAGES = ("launch", "growth", "maturity", "decline")
PROJECT_STATUSES = (
    "concept",
    "development",
    "pilot",
    "launch_ready",
    "launched",
    "canceled",
)
MIN_TECH_GENERATION = 1
MAX_TECH_GENERATION = 4

LEGACY_CAPACITY_EXPANSION_MAP = {
    "Reduce": 0,
    "Maintain": 0,
    "Expand": 80,
    "Selective Expansion": 40,
}

LEGACY_OVERTIME_MAP = {
    "Reduce": 0,
    "Maintain": 0,
    "Expand": 10,
    "Selective Expansion": 20,
}

LEGACY_BACKORDER_MAP = {
    "Lost Sales": 0,
    "Backorder": 150,
}

LEGACY_SUPPLIER_MIX_MAP = {
    "Offshore Value": (100.0, 0.0, 0.0),
    "Balanced Source": (0.0, 100.0, 0.0),
    "Premium Reliable": (0.0, 0.0, 100.0),
}

LEGACY_EXPEDITED_MAP = {
    "Standard": 0.0,
    "Expedited": 100.0,
}


def _payload_has_value(payload: dict[str, Any], key: str) -> bool:
    """Return whether a payload field should be treated as provided."""
    value = payload.get(key)
    return value not in (None, "")


def _optional_int(value: Any) -> int | None:
    """Return an optional integer from a loose payload value."""
    if value in (None, ""):
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    """Return an optional string from a loose payload value."""
    if value in (None, ""):
        return None
    return str(value)


def build_product_id(team_name: str, slot_name: str) -> str:
    """Build a stable product identifier from team and slot."""
    normalized_team = "".join(
        character.lower() if character.isalnum() else "_"
        for character in team_name.strip()
    ).strip("_")
    return f"{normalized_team}_{slot_name.upper()}"


def build_project_id(team_name: str, project_slot_name: str) -> str:
    """Build a stable project identifier from team and project slot."""
    normalized_team = "".join(
        character.lower() if character.isalnum() else "_"
        for character in team_name.strip()
    ).strip("_")
    return f"{normalized_team}_{project_slot_name.upper()}"


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
    current_market_generation: int = 2
    technology_shift_rate: float = 0.15
    premium_tech_adoption: float = 0.75
    mid_market_tech_adoption: float = 0.55
    beginner_price_pressure: float = 0.60

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
            current_market_generation=max(
                MIN_TECH_GENERATION,
                min(
                    int(payload.get("current_market_generation", 2)),
                    MAX_TECH_GENERATION,
                ),
            ),
            technology_shift_rate=float(payload.get("technology_shift_rate", 0.15)),
            premium_tech_adoption=float(payload.get("premium_tech_adoption", 0.75)),
            mid_market_tech_adoption=float(payload.get("mid_market_tech_adoption", 0.55)),
            beginner_price_pressure=float(payload.get("beginner_price_pressure", 0.60)),
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
class ClassroomRoundStatus:
    """Instructor-controlled submission status for a round."""

    round_number: int
    submissions_open: bool = True
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClassroomRoundStatus":
        """Create round status from a SQLite row or dictionary."""
        return cls(
            round_number=int(payload.get("round_number", 1)),
            submissions_open=bool(payload.get("submissions_open", True)),
            notes=str(payload.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize round status into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class ProductTemplate:
    """Archetype-level default template for one product slot."""

    slot_name: str
    product_name: str
    is_active: bool
    target_segment: str
    lifecycle_stage: str
    age_in_rounds: int
    base_defect_rate_modifier: float
    base_demand_fit_modifier: float
    suggested_selling_price_per_unit: float
    suggested_planned_production_units: int
    suggested_qc_budget_per_unit: float
    suggested_target_finished_goods_inventory: int
    tech_generation: int = 1
    cannibalization_group: str = ""
    launch_round: int = 0
    retirement_flag: bool = False
    retired_round: int | None = None
    replacement_project_id: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProductTemplate":
        """Create a product template from stored JSON or dict payload."""
        return cls(
            slot_name=str(payload.get("slot_name", "A")).upper(),
            product_name=str(payload.get("product_name", "Product")),
            is_active=bool(payload.get("is_active", True)),
            target_segment=str(payload.get("target_segment", "mid")).lower(),
            lifecycle_stage=str(payload.get("lifecycle_stage", "launch")).lower(),
            age_in_rounds=int(payload.get("age_in_rounds", 0)),
            base_defect_rate_modifier=float(
                payload.get("base_defect_rate_modifier", 0.0)
            ),
            base_demand_fit_modifier=float(
                payload.get("base_demand_fit_modifier", 1.0)
            ),
            suggested_selling_price_per_unit=float(
                payload.get("suggested_selling_price_per_unit", 130.0)
            ),
            suggested_planned_production_units=int(
                payload.get("suggested_planned_production_units", 100)
            ),
            suggested_qc_budget_per_unit=float(
                payload.get("suggested_qc_budget_per_unit", 3.0)
            ),
            suggested_target_finished_goods_inventory=int(
                payload.get("suggested_target_finished_goods_inventory", 25)
            ),
            tech_generation=max(
                MIN_TECH_GENERATION,
                min(int(payload.get("tech_generation", 1)), MAX_TECH_GENERATION),
            ),
            cannibalization_group=str(payload.get("cannibalization_group", "")),
            launch_round=int(payload.get("launch_round", 0)),
            retirement_flag=bool(payload.get("retirement_flag", False)),
            retired_round=_optional_int(payload.get("retired_round")),
            replacement_project_id=_optional_str(
                payload.get("replacement_project_id")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the product template into JSON-friendly form."""
        return asdict(self)


@dataclass
class TeamArchetype:
    """Reference profile that describes a team's operating baseline."""

    name: str
    description: str
    base_cost: float
    base_capacity: int
    base_reputation: float
    base_defect_rate: float
    premium_fit: float
    mid_fit: float
    beginner_fit: float
    suggested_overtime_capacity_units: int
    suggested_capacity_expansion_units: int
    suggested_max_backorder_units: int
    suggested_raw_material_order_qty: int
    suggested_supplier_mix_offshore_pct: float
    suggested_supplier_mix_balanced_pct: float
    suggested_supplier_mix_premium_pct: float
    suggested_expedited_order_share_pct: float
    suggested_product_templates: list[ProductTemplate] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamArchetype":
        """Create an archetype from stored JSON with migration-friendly defaults."""
        suggested_product_templates_payload = payload.get(
            "suggested_product_templates",
            payload.get("suggested_product_templates_json", "[]"),
        )
        if isinstance(suggested_product_templates_payload, str):
            try:
                suggested_product_templates_payload = json.loads(
                    suggested_product_templates_payload
                )
            except json.JSONDecodeError:
                suggested_product_templates_payload = []

        return cls(
            name=str(payload.get("name", "Generic Team")),
            description=str(payload.get("description", "")),
            base_cost=float(payload.get("base_cost", 70.0)),
            base_capacity=int(payload.get("base_capacity", 300)),
            base_reputation=float(payload.get("base_reputation", 50.0)),
            base_defect_rate=float(payload.get("base_defect_rate", 0.05)),
            premium_fit=float(payload.get("premium_fit", 0.34)),
            mid_fit=float(payload.get("mid_fit", 0.33)),
            beginner_fit=float(payload.get("beginner_fit", 0.33)),
            suggested_overtime_capacity_units=int(
                payload.get("suggested_overtime_capacity_units", 0)
            ),
            suggested_capacity_expansion_units=int(
                payload.get("suggested_capacity_expansion_units", 0)
            ),
            suggested_max_backorder_units=int(
                payload.get("suggested_max_backorder_units", 100)
            ),
            suggested_raw_material_order_qty=int(
                payload.get("suggested_raw_material_order_qty", 300)
            ),
            suggested_supplier_mix_offshore_pct=float(
                payload.get("suggested_supplier_mix_offshore_pct", 0.0)
            ),
            suggested_supplier_mix_balanced_pct=float(
                payload.get("suggested_supplier_mix_balanced_pct", 100.0)
            ),
            suggested_supplier_mix_premium_pct=float(
                payload.get("suggested_supplier_mix_premium_pct", 0.0)
            ),
            suggested_expedited_order_share_pct=float(
                payload.get("suggested_expedited_order_share_pct", 0.0)
            ),
            suggested_product_templates=[
                ProductTemplate.from_dict(item)
                for item in suggested_product_templates_payload
            ],
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
        payload = asdict(self)
        payload["suggested_product_templates"] = [
            item.to_dict() for item in self.suggested_product_templates
        ]
        return payload


@dataclass
class ProductLine:
    """Persistent product slot state for one team."""

    product_id: str
    team_name: str
    product_name: str
    slot_name: str
    is_active: bool
    target_segment: str
    lifecycle_stage: str
    age_in_rounds: int
    base_defect_rate_modifier: float
    base_demand_fit_modifier: float
    tech_generation: int = 1
    cannibalization_group: str = ""
    launch_round: int = 0
    retirement_flag: bool = False
    retired_round: int | None = None
    replacement_project_id: str | None = None
    inventory_units: int = 0
    backlog_units: int = 0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProductLine":
        """Create a product line from stored JSON or SQLite rows."""
        team_name = str(payload.get("team_name", "")).strip()
        slot_name = str(payload.get("slot_name", "A")).upper()
        return cls(
            product_id=str(
                payload.get("product_id", build_product_id(team_name, slot_name))
            ),
            team_name=team_name,
            product_name=str(payload.get("product_name", f"Product {slot_name}")),
            slot_name=slot_name,
            is_active=bool(payload.get("is_active", True)),
            target_segment=str(payload.get("target_segment", "mid")).lower(),
            lifecycle_stage=str(payload.get("lifecycle_stage", "launch")).lower(),
            age_in_rounds=int(payload.get("age_in_rounds", 0)),
            base_defect_rate_modifier=float(
                payload.get("base_defect_rate_modifier", 0.0)
            ),
            base_demand_fit_modifier=float(
                payload.get("base_demand_fit_modifier", 1.0)
            ),
            tech_generation=max(
                MIN_TECH_GENERATION,
                min(int(payload.get("tech_generation", 1)), MAX_TECH_GENERATION),
            ),
            cannibalization_group=str(payload.get("cannibalization_group", "")),
            launch_round=int(payload.get("launch_round", 0)),
            retirement_flag=bool(payload.get("retirement_flag", False)),
            retired_round=_optional_int(payload.get("retired_round")),
            replacement_project_id=_optional_str(
                payload.get("replacement_project_id")
            ),
            inventory_units=int(payload.get("inventory_units", 0)),
            backlog_units=int(payload.get("backlog_units", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the product line into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class TeamDecision:
    """Firm-level shared decisions submitted by a team for a round."""

    team_name: str
    archetype: str
    overtime_capacity_units: int
    capacity_expansion_units: int
    raw_material_order_qty: int
    supplier_mix_offshore_pct: float
    supplier_mix_balanced_pct: float
    supplier_mix_premium_pct: float
    expedited_order_share_pct: float
    max_backorder_units: int
    planned_borrowing_amount: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamDecision":
        """Create a firm-level decision from stored JSON with legacy fallbacks."""
        overtime_capacity_units = int(payload.get("overtime_capacity_units", 0))
        if overtime_capacity_units <= 0 and _payload_has_value(payload, "capacity_plan"):
            overtime_capacity_units = LEGACY_OVERTIME_MAP.get(
                str(payload.get("capacity_plan", "Maintain")),
                0,
            )

        capacity_expansion_units = int(payload.get("capacity_expansion_units", 0))
        if (
            capacity_expansion_units <= 0
            and _payload_has_value(payload, "capacity_plan")
        ):
            capacity_expansion_units = LEGACY_CAPACITY_EXPANSION_MAP.get(
                str(payload.get("capacity_plan", "Maintain")),
                0,
            )

        max_backorder_units = int(payload.get("max_backorder_units", 0))
        if max_backorder_units <= 0 and _payload_has_value(payload, "service_policy"):
            max_backorder_units = LEGACY_BACKORDER_MAP.get(
                str(payload.get("service_policy", "Lost Sales")),
                0,
            )

        legacy_supplier_choice = str(payload.get("supplier_choice", "Balanced Source"))
        legacy_supplier_mix = LEGACY_SUPPLIER_MIX_MAP.get(
            legacy_supplier_choice,
            LEGACY_SUPPLIER_MIX_MAP["Balanced Source"],
        )
        offshore_pct = float(payload.get("supplier_mix_offshore_pct", 0.0))
        balanced_pct = float(payload.get("supplier_mix_balanced_pct", 0.0))
        premium_pct = float(payload.get("supplier_mix_premium_pct", 0.0))
        if (
            offshore_pct + balanced_pct + premium_pct <= 0
            and _payload_has_value(payload, "supplier_choice")
        ):
            offshore_pct, balanced_pct, premium_pct = legacy_supplier_mix

        expedited_order_share_pct = float(
            payload.get("expedited_order_share_pct", 0.0)
        )
        if (
            expedited_order_share_pct <= 0
            and _payload_has_value(payload, "order_priority")
        ):
            expedited_order_share_pct = LEGACY_EXPEDITED_MAP.get(
                str(payload.get("order_priority", "Standard")),
                0.0,
            )

        return cls(
            team_name=str(payload.get("team_name", "")).strip(),
            archetype=str(payload.get("archetype", "")),
            overtime_capacity_units=max(overtime_capacity_units, 0),
            capacity_expansion_units=max(capacity_expansion_units, 0),
            raw_material_order_qty=max(int(payload.get("raw_material_order_qty", 0)), 0),
            supplier_mix_offshore_pct=offshore_pct,
            supplier_mix_balanced_pct=balanced_pct,
            supplier_mix_premium_pct=premium_pct,
            expedited_order_share_pct=max(expedited_order_share_pct, 0.0),
            max_backorder_units=max(max_backorder_units, 0),
            planned_borrowing_amount=max(
                float(payload.get("planned_borrowing_amount", 0.0)),
                0.0,
            ),
        )

    def supplier_mix_total(self) -> float:
        """Return the raw total of the supplier mix percentages."""
        return (
            self.supplier_mix_offshore_pct
            + self.supplier_mix_balanced_pct
            + self.supplier_mix_premium_pct
        )

    def supplier_mix_valid(self, tolerance: float = 0.5) -> bool:
        """Return whether supplier mix percentages sum close to 100."""
        return abs(self.supplier_mix_total() - 100.0) <= tolerance

    def normalized_supplier_mix(self) -> dict[str, float]:
        """Return supplier shares normalized to 0-1 weights."""
        total = self.supplier_mix_total()
        if total <= 0:
            return {
                "offshore": 0.0,
                "balanced": 1.0,
                "premium": 0.0,
            }

        return {
            "offshore": self.supplier_mix_offshore_pct / total,
            "balanced": self.supplier_mix_balanced_pct / total,
            "premium": self.supplier_mix_premium_pct / total,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the team decision into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class ProductDecision:
    """One product slot's round decision."""

    product_id: str
    team_name: str
    slot_name: str
    product_name: str
    is_active: bool
    target_segment: str
    selling_price_per_unit: float
    planned_production_units: int
    qc_budget_per_unit: float
    target_finished_goods_inventory: int
    forecast_units: int = 0
    retire_flag: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProductDecision":
        """Create a product decision from stored JSON or SQLite rows."""
        team_name = str(payload.get("team_name", "")).strip()
        slot_name = str(payload.get("slot_name", "A")).upper()
        return cls(
            product_id=str(
                payload.get("product_id", build_product_id(team_name, slot_name))
            ),
            team_name=team_name,
            slot_name=slot_name,
            product_name=str(payload.get("product_name", f"Product {slot_name}")),
            is_active=bool(payload.get("is_active", True)),
            target_segment=str(payload.get("target_segment", "mid")).lower(),
            selling_price_per_unit=max(
                float(payload.get("selling_price_per_unit", 0.0)),
                0.0,
            ),
            planned_production_units=max(
                int(payload.get("planned_production_units", 0)),
                0,
            ),
            qc_budget_per_unit=max(float(payload.get("qc_budget_per_unit", 0.0)), 0.0),
            target_finished_goods_inventory=max(
                int(payload.get("target_finished_goods_inventory", 0)),
                0,
            ),
            forecast_units=max(
                int(
                    payload.get(
                        "forecast_units",
                        payload.get("planned_production_units", 0),
                    )
                ),
                0,
            ),
            retire_flag=bool(payload.get("retire_flag", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the product decision into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class ProductDevelopmentProject:
    """Persistent development-project state for one team."""

    project_id: str
    team_name: str
    project_slot_name: str
    project_name: str
    target_segment: str
    target_tech_generation: int
    intended_slot_name: str
    required_investment: float
    cumulative_investment: float
    investment_this_round: float
    testing_intensity: float
    launch_readiness_score: float
    planned_launch_round: int
    earliest_launch_round: int
    status: str
    cannibalization_group: str
    projected_base_defect_modifier: float
    projected_demand_fit_modifier: float
    created_round: int
    launched_round: int | None = None
    canceled_round: int | None = None
    launch_now: bool = False
    cancel_now: bool = False
    replaced_product_name: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProductDevelopmentProject":
        """Create a development project from stored JSON or SQLite rows."""
        team_name = str(payload.get("team_name", "")).strip()
        project_slot_name = str(payload.get("project_slot_name", "P1")).upper()
        return cls(
            project_id=str(
                payload.get("project_id", build_project_id(team_name, project_slot_name))
            ),
            team_name=team_name,
            project_slot_name=project_slot_name,
            project_name=str(payload.get("project_name", "")),
            target_segment=str(payload.get("target_segment", "mid")).lower(),
            target_tech_generation=max(
                MIN_TECH_GENERATION,
                min(int(payload.get("target_tech_generation", 1)), MAX_TECH_GENERATION),
            ),
            intended_slot_name=str(payload.get("intended_slot_name", "A")).upper(),
            required_investment=float(payload.get("required_investment", 0.0)),
            cumulative_investment=float(payload.get("cumulative_investment", 0.0)),
            investment_this_round=max(float(payload.get("investment_this_round", 0.0)), 0.0),
            testing_intensity=max(float(payload.get("testing_intensity", 0.0)), 0.0),
            launch_readiness_score=float(payload.get("launch_readiness_score", 0.0)),
            planned_launch_round=int(payload.get("planned_launch_round", 1)),
            earliest_launch_round=int(payload.get("earliest_launch_round", 1)),
            status=str(payload.get("status", "concept")).lower(),
            cannibalization_group=str(payload.get("cannibalization_group", "")),
            projected_base_defect_modifier=float(
                payload.get("projected_base_defect_modifier", 0.0)
            ),
            projected_demand_fit_modifier=float(
                payload.get("projected_demand_fit_modifier", 1.0)
            ),
            created_round=int(payload.get("created_round", 1)),
            launched_round=_optional_int(payload.get("launched_round")),
            canceled_round=_optional_int(payload.get("canceled_round")),
            launch_now=bool(payload.get("launch_now", False)),
            cancel_now=bool(payload.get("cancel_now", False)),
            replaced_product_name=_optional_str(payload.get("replaced_product_name")),
        )

    def is_defined(self) -> bool:
        """Return whether the project slot contains a real project."""
        return bool(self.project_name.strip())

    def is_pipeline_active(self) -> bool:
        """Return whether the project is still part of the active pipeline."""
        return self.is_defined() and self.status not in {"launched", "canceled"}

    def is_launch_ready(self, round_number: int) -> bool:
        """Return whether the project is eligible to launch."""
        return (
            self.is_defined()
            and self.status == "launch_ready"
            and round_number >= self.earliest_launch_round
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the development project into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class OpenMaterialOrder:
    """Inbound raw-material order that arrives in a future round."""

    quantity: int
    arrival_round: int
    placed_round: int
    weighted_material_unit_cost: float
    weighted_lead_time: float

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OpenMaterialOrder":
        """Create an inbound raw-material order from stored JSON."""
        return cls(
            quantity=int(payload.get("quantity", 0)),
            arrival_round=int(payload.get("arrival_round", 0)),
            placed_round=int(payload.get("placed_round", 0)),
            weighted_material_unit_cost=float(
                payload.get("weighted_material_unit_cost", 0.0)
            ),
            weighted_lead_time=float(payload.get("weighted_lead_time", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the inbound raw-material order into JSON-friendly form."""
        return asdict(self)


@dataclass
class ProductForecast:
    """Saved per-product forecast for a round."""

    round_number: int
    team_name: str
    product_id: str
    slot_name: str
    product_name: str
    forecast_units: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProductForecast":
        """Create a product forecast from stored JSON or SQLite rows."""
        team_name = str(payload.get("team_name", "")).strip()
        slot_name = str(payload.get("slot_name", "A")).upper()
        return cls(
            round_number=int(payload.get("round_number", 0)),
            team_name=team_name,
            product_id=str(
                payload.get("product_id", build_product_id(team_name, slot_name))
            ),
            slot_name=slot_name,
            product_name=str(payload.get("product_name", f"Product {slot_name}")),
            forecast_units=max(int(payload.get("forecast_units", 0)), 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the product forecast into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class ForecastAccuracyResult:
    """Per-product forecast-vs-actual diagnostic result."""

    round_number: int
    team_name: str
    product_id: str
    slot_name: str
    product_name: str
    forecast_units: int
    actual_demand_units: float
    actual_sales_units: int
    forecast_error_units: float
    absolute_error_units: float
    forecast_bias_pct: float
    mape_or_wape_value: float

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ForecastAccuracyResult":
        """Create a forecast-accuracy result from stored JSON or SQLite rows."""
        team_name = str(payload.get("team_name", "")).strip()
        slot_name = str(payload.get("slot_name", "A")).upper()
        return cls(
            round_number=int(payload.get("round_number", 0)),
            team_name=team_name,
            product_id=str(
                payload.get("product_id", build_product_id(team_name, slot_name))
            ),
            slot_name=slot_name,
            product_name=str(payload.get("product_name", f"Product {slot_name}")),
            forecast_units=max(int(payload.get("forecast_units", 0)), 0),
            actual_demand_units=float(payload.get("actual_demand_units", 0.0)),
            actual_sales_units=max(int(payload.get("actual_sales_units", 0)), 0),
            forecast_error_units=float(payload.get("forecast_error_units", 0.0)),
            absolute_error_units=float(payload.get("absolute_error_units", 0.0)),
            forecast_bias_pct=float(payload.get("forecast_bias_pct", 0.0)),
            mape_or_wape_value=float(payload.get("mape_or_wape_value", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the forecast accuracy result into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class ProductRoundResult:
    """Round-level product result for one team product slot."""

    round_number: int
    team_name: str
    product_id: str
    product_name: str
    slot_name: str
    target_segment: str
    lifecycle_stage: str
    age_in_rounds: int
    tech_generation: int = 1
    cannibalization_group: str = ""
    selling_price_per_unit: float = 0.0
    forecast_units: int = 0
    planned_production_units: int = 0
    actual_production_units: int = 0
    defect_rate: float = 0.0
    good_units_produced: int = 0
    demand_allocated: float = 0.0
    actual_demand_units: float = 0.0
    sales_units: int = 0
    lost_sales_units: int = 0
    ending_inventory: int = 0
    fill_rate: float = 1.0
    forecast_error_units: float = 0.0
    absolute_error_units: float = 0.0
    forecast_bias_pct: float = 0.0
    mape_or_wape_value: float = 0.0
    revenue: float = 0.0
    production_cost: float = 0.0
    holding_cost: float = 0.0
    warranty_cost: float = 0.0
    allocated_procurement_cost: float = 0.0
    allocated_backlog_cost: float = 0.0
    allocated_expansion_cost: float = 0.0
    contribution_margin_per_unit: float = 0.0
    profit_contribution: float = 0.0
    beginning_inventory: int = 0
    backlog_units_start: int = 0
    backlog_units_end: int = 0
    tech_gap_to_market: int = 0
    tech_attractiveness_adjustment: float = 1.0
    cannibalization_in_units: float = 0.0
    cannibalization_out_units: float = 0.0
    launched_this_round: bool = False
    launch_event: str = ""
    retired_this_round: bool = False
    retirement_liquidation_revenue: float = 0.0
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProductRoundResult":
        """Create a product round result from stored JSON or SQLite rows."""
        return cls(
            round_number=int(payload.get("round_number", 0)),
            team_name=str(payload.get("team_name", "")),
            product_id=str(payload.get("product_id", "")),
            product_name=str(payload.get("product_name", "")),
            slot_name=str(payload.get("slot_name", "A")).upper(),
            target_segment=str(payload.get("target_segment", "mid")).lower(),
            lifecycle_stage=str(payload.get("lifecycle_stage", "launch")).lower(),
            age_in_rounds=int(payload.get("age_in_rounds", 0)),
            tech_generation=max(
                MIN_TECH_GENERATION,
                min(int(payload.get("tech_generation", 1)), MAX_TECH_GENERATION),
            ),
            cannibalization_group=str(payload.get("cannibalization_group", "")),
            selling_price_per_unit=float(payload.get("selling_price_per_unit", 0.0)),
            forecast_units=int(payload.get("forecast_units", 0)),
            planned_production_units=int(payload.get("planned_production_units", 0)),
            actual_production_units=int(payload.get("actual_production_units", 0)),
            defect_rate=float(payload.get("defect_rate", 0.0)),
            good_units_produced=int(payload.get("good_units_produced", 0)),
            demand_allocated=float(payload.get("demand_allocated", 0.0)),
            actual_demand_units=float(
                payload.get(
                    "actual_demand_units",
                    payload.get("demand_allocated", 0.0),
                )
            ),
            sales_units=int(payload.get("sales_units", 0)),
            lost_sales_units=int(payload.get("lost_sales_units", 0)),
            ending_inventory=int(payload.get("ending_inventory", 0)),
            fill_rate=float(payload.get("fill_rate", 1.0)),
            forecast_error_units=float(payload.get("forecast_error_units", 0.0)),
            absolute_error_units=float(payload.get("absolute_error_units", 0.0)),
            forecast_bias_pct=float(payload.get("forecast_bias_pct", 0.0)),
            mape_or_wape_value=float(payload.get("mape_or_wape_value", 0.0)),
            revenue=float(payload.get("revenue", 0.0)),
            production_cost=float(payload.get("production_cost", 0.0)),
            holding_cost=float(payload.get("holding_cost", 0.0)),
            warranty_cost=float(payload.get("warranty_cost", 0.0)),
            allocated_procurement_cost=float(
                payload.get("allocated_procurement_cost", 0.0)
            ),
            allocated_backlog_cost=float(payload.get("allocated_backlog_cost", 0.0)),
            allocated_expansion_cost=float(payload.get("allocated_expansion_cost", 0.0)),
            contribution_margin_per_unit=float(
                payload.get("contribution_margin_per_unit", 0.0)
            ),
            profit_contribution=float(payload.get("profit_contribution", 0.0)),
            beginning_inventory=int(payload.get("beginning_inventory", 0)),
            backlog_units_start=int(payload.get("backlog_units_start", 0)),
            backlog_units_end=int(payload.get("backlog_units_end", 0)),
            tech_gap_to_market=int(payload.get("tech_gap_to_market", 0)),
            tech_attractiveness_adjustment=float(
                payload.get("tech_attractiveness_adjustment", 1.0)
            ),
            cannibalization_in_units=float(
                payload.get("cannibalization_in_units", 0.0)
            ),
            cannibalization_out_units=float(
                payload.get("cannibalization_out_units", 0.0)
            ),
            launched_this_round=bool(payload.get("launched_this_round", False)),
            launch_event=str(payload.get("launch_event", "")),
            retired_this_round=bool(payload.get("retired_this_round", False)),
            retirement_liquidation_revenue=float(
                payload.get("retirement_liquidation_revenue", 0.0)
            ),
            notes=str(payload.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the product round result into a JSON-friendly dictionary."""
        return asdict(self)


@dataclass
class RoundResult:
    """Round-level operating and financial output for one team."""

    round_number: int
    team_name: str
    archetype: str
    active_product_count: int = 0
    active_project_count: int = 0
    launch_ready_project_count: int = 0
    launched_project_count: int = 0
    retired_product_count: int = 0
    total_forecast_units: int = 0
    total_actual_demand_units: float = 0.0
    forecast_error_units: float = 0.0
    absolute_forecast_error_units: float = 0.0
    forecast_wape: float = 0.0
    service_gap_units: float = 0.0
    weighted_average_selling_price: float = 0.0
    planned_production_units: int = 0
    actual_production_units: int = 0
    effective_capacity_units: int = 0
    utilization_pct: float = 0.0
    weighted_material_unit_cost: float = 0.0
    defect_rate: float = 0.0
    good_units_produced: int = 0
    demand_allocated: float = 0.0
    sales_units: int = 0
    lost_sales_units: int = 0
    backlog_units_end: int = 0
    ending_inventory: int = 0
    ending_raw_material_inventory: int = 0
    fill_rate: float = 1.0
    revenue: float = 0.0
    procurement_cost: float = 0.0
    production_cost: float = 0.0
    holding_cost: float = 0.0
    warranty_cost: float = 0.0
    backlog_cost: float = 0.0
    expansion_cost: float = 0.0
    innovation_investment: float = 0.0
    interest_expense: float = 0.0
    working_capital_requirement: float = 0.0
    planned_borrowing_amount: float = 0.0
    automatic_borrowing_amount: float = 0.0
    ending_cash_balance: float = 0.0
    short_term_debt_balance: float = 0.0
    liquidity_stress_flag: bool = False
    total_cost: float = 0.0
    profit: float = 0.0
    contribution_margin_per_unit: float = 0.0
    reputation_after_round: float = 0.0
    average_portfolio_tech_generation: float = 0.0
    cannibalized_demand_units: float = 0.0
    beginning_finished_goods_inventory: int = 0
    beginning_raw_material_inventory: int = 0
    raw_material_units_received: int = 0
    raw_material_units_consumed: int = 0
    raw_material_order_qty: int = 0
    backlog_units_start: int = 0
    launch_events_text: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RoundResult":
        """Create a round result from stored JSON, including legacy rows."""
        return cls(
            round_number=int(payload.get("round_number", 0)),
            team_name=str(payload.get("team_name", "")),
            archetype=str(payload.get("archetype", "")),
            active_product_count=int(payload.get("active_product_count", 0)),
            active_project_count=int(payload.get("active_project_count", 0)),
            launch_ready_project_count=int(
                payload.get("launch_ready_project_count", 0)
            ),
            launched_project_count=int(payload.get("launched_project_count", 0)),
            retired_product_count=int(payload.get("retired_product_count", 0)),
            total_forecast_units=int(payload.get("total_forecast_units", 0)),
            total_actual_demand_units=float(
                payload.get(
                    "total_actual_demand_units",
                    payload.get("demand_allocated", 0.0),
                )
            ),
            forecast_error_units=float(payload.get("forecast_error_units", 0.0)),
            absolute_forecast_error_units=float(
                payload.get("absolute_forecast_error_units", 0.0)
            ),
            forecast_wape=float(payload.get("forecast_wape", 0.0)),
            service_gap_units=float(
                payload.get(
                    "service_gap_units",
                    payload.get("lost_sales_units", 0),
                )
            ),
            weighted_average_selling_price=float(
                payload.get(
                    "weighted_average_selling_price",
                    payload.get("selling_price_per_unit", 0.0),
                )
            ),
            planned_production_units=int(payload.get("planned_production_units", 0)),
            actual_production_units=int(
                payload.get(
                    "actual_production_units",
                    payload.get("good_units_produced", 0),
                )
            ),
            effective_capacity_units=int(payload.get("effective_capacity_units", 0)),
            utilization_pct=float(payload.get("utilization_pct", 0.0)),
            weighted_material_unit_cost=float(
                payload.get("weighted_material_unit_cost", 0.0)
            ),
            defect_rate=float(payload.get("defect_rate", 0.0)),
            good_units_produced=int(payload.get("good_units_produced", 0)),
            demand_allocated=float(payload.get("demand_allocated", 0.0)),
            sales_units=int(payload.get("sales_units", 0)),
            lost_sales_units=int(payload.get("lost_sales_units", 0)),
            backlog_units_end=int(payload.get("backlog_units_end", 0)),
            ending_inventory=int(payload.get("ending_inventory", 0)),
            ending_raw_material_inventory=int(
                payload.get("ending_raw_material_inventory", 0)
            ),
            fill_rate=float(payload.get("fill_rate", 1.0)),
            revenue=float(payload.get("revenue", 0.0)),
            procurement_cost=float(payload.get("procurement_cost", 0.0)),
            production_cost=float(payload.get("production_cost", 0.0)),
            holding_cost=float(payload.get("holding_cost", 0.0)),
            warranty_cost=float(payload.get("warranty_cost", 0.0)),
            backlog_cost=float(payload.get("backlog_cost", 0.0)),
            expansion_cost=float(payload.get("expansion_cost", 0.0)),
            innovation_investment=float(payload.get("innovation_investment", 0.0)),
            interest_expense=float(payload.get("interest_expense", 0.0)),
            working_capital_requirement=float(
                payload.get("working_capital_requirement", 0.0)
            ),
            planned_borrowing_amount=float(
                payload.get("planned_borrowing_amount", 0.0)
            ),
            automatic_borrowing_amount=float(
                payload.get("automatic_borrowing_amount", 0.0)
            ),
            ending_cash_balance=float(payload.get("ending_cash_balance", 0.0)),
            short_term_debt_balance=float(
                payload.get("short_term_debt_balance", 0.0)
            ),
            liquidity_stress_flag=bool(payload.get("liquidity_stress_flag", False)),
            total_cost=float(payload.get("total_cost", 0.0)),
            profit=float(payload.get("profit", 0.0)),
            contribution_margin_per_unit=float(
                payload.get("contribution_margin_per_unit", 0.0)
            ),
            reputation_after_round=float(payload.get("reputation_after_round", 0.0)),
            average_portfolio_tech_generation=float(
                payload.get("average_portfolio_tech_generation", 0.0)
            ),
            cannibalized_demand_units=float(
                payload.get("cannibalized_demand_units", 0.0)
            ),
            beginning_finished_goods_inventory=int(
                payload.get("beginning_finished_goods_inventory", 0)
            ),
            beginning_raw_material_inventory=int(
                payload.get("beginning_raw_material_inventory", 0)
            ),
            raw_material_units_received=int(
                payload.get("raw_material_units_received", 0)
            ),
            raw_material_units_consumed=int(
                payload.get("raw_material_units_consumed", 0)
            ),
            raw_material_order_qty=int(payload.get("raw_material_order_qty", 0)),
            backlog_units_start=int(payload.get("backlog_units_start", 0)),
            launch_events_text=str(payload.get("launch_events_text", "")),
            notes=str(payload.get("notes", "")),
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
    raw_material_inventory: int = 0
    backlog_units: int = 0
    capacity_units: int = 0
    reputation_score: float = 50.0
    completed_rounds: list[int] = field(default_factory=list)
    last_decision: dict[str, Any] = field(default_factory=dict)
    open_material_orders: list[OpenMaterialOrder] = field(default_factory=list)
    cumulative_profit: float = 0.0
    short_term_debt_balance: float = 0.0
    interest_expense_last_round: float = 0.0
    liquidity_warning_flag: bool = False
    working_capital_stress_score: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PersistentTeamState":
        """Create persistent team state from stored JSON with safe defaults."""
        open_orders_payload = payload.get("open_material_orders", [])
        open_orders = []
        for order in open_orders_payload:
            if isinstance(order, OpenMaterialOrder):
                open_orders.append(order)
            else:
                open_orders.append(OpenMaterialOrder.from_dict(dict(order)))

        return cls(
            team_name=str(payload.get("team_name", "")),
            archetype=str(payload.get("archetype", "")),
            cash_balance=float(payload.get("cash_balance", 0.0)),
            inventory_units=int(payload.get("inventory_units", 0)),
            raw_material_inventory=int(payload.get("raw_material_inventory", 0)),
            backlog_units=int(payload.get("backlog_units", 0)),
            capacity_units=int(payload.get("capacity_units", 0)),
            reputation_score=float(payload.get("reputation_score", 50.0)),
            completed_rounds=[
                int(round_number)
                for round_number in payload.get("completed_rounds", [])
            ],
            last_decision=dict(payload.get("last_decision", {})),
            open_material_orders=open_orders,
            cumulative_profit=float(payload.get("cumulative_profit", 0.0)),
            short_term_debt_balance=float(
                payload.get("short_term_debt_balance", 0.0)
            ),
            interest_expense_last_round=float(
                payload.get("interest_expense_last_round", 0.0)
            ),
            liquidity_warning_flag=bool(
                payload.get("liquidity_warning_flag", False)
            ),
            working_capital_stress_score=float(
                payload.get("working_capital_stress_score", 0.0)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the persistent team state into a JSON-friendly dictionary."""
        return {
            "team_name": self.team_name,
            "archetype": self.archetype,
            "cash_balance": self.cash_balance,
            "inventory_units": self.inventory_units,
            "raw_material_inventory": self.raw_material_inventory,
            "backlog_units": self.backlog_units,
            "capacity_units": self.capacity_units,
            "reputation_score": self.reputation_score,
            "completed_rounds": list(self.completed_rounds),
            "last_decision": dict(self.last_decision),
            "open_material_orders": [
                order.to_dict() for order in self.open_material_orders
            ],
            "cumulative_profit": self.cumulative_profit,
            "short_term_debt_balance": self.short_term_debt_balance,
            "interest_expense_last_round": self.interest_expense_last_round,
            "liquidity_warning_flag": self.liquidity_warning_flag,
            "working_capital_stress_score": self.working_capital_stress_score,
        }
