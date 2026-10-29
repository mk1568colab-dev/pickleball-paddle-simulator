"""Page for capturing Stage B firm, product, and development-project decisions."""

from __future__ import annotations

import base64
from dataclasses import replace
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from engine.config import (
    STARTING_RAW_MATERIAL_COVERAGE,
    SUPPLIER_NAMES,
)
from engine.sourcing import material_order_timing
from engine.sourcing import sourcing_quote, public_incoming_orders, ordering_fee_description
from utils.sourcing_rules import load_delivery_policy
from engine.simulator import estimate_development_project, preview_team_decision, project_ready_at_round_start
from models.schemas import (
    MAX_TECH_GENERATION,
    MIN_TECH_GENERATION,
    PRODUCT_SLOT_NAMES,
    PROJECT_SLOT_NAMES,
    TARGET_SEGMENTS,
    ProductDecision,
    ProductDevelopmentProject,
    ProductForecast,
    ProductLine,
    TeamArchetype,
    TeamDecision,
    build_project_id,
)
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.demand_protocol import planning_market_report
from utils.repository import (
    ensure_development_projects_for_team,
    ensure_product_lines_for_team,
    load_market_report,
    load_product_decisions,
    load_product_development_projects,
    load_product_lines,
    load_round_status,
    load_team_archetypes,
    load_team_decision,
    load_team_decisions,
    load_team_states,
    load_users,
    save_product_decisions,
    save_product_forecasts,
    save_product_development_projects,
    save_product_lines,
    save_team_decision,
)


SESSION_CONTEXT_KEY = "stage_b_decision_editor_context"
ARCHETYPE_KEY = "stage_b_archetype_name"
SUBMIT_WARNING_CONTEXT_KEY = "stage_b_submit_warning_context"
SUBMIT_WARNING_MESSAGES_KEY = "stage_b_submit_warning_messages"
SUBMIT_SUCCESS_MESSAGE_KEY = "stage_b_submit_success_message"
APP_ROOT = Path(__file__).resolve().parents[1]
KIKI_CHECKLIST_MASCOT_DIR = APP_ROOT / "assets" / "kiki_checklist_mascots"

FIRM_WIDGET_KEYS = {
    "overtime_capacity_units": "stage_b_overtime_capacity_units",
    "capacity_expansion_units": "stage_b_capacity_expansion_units",
    "raw_material_order_qty": "stage_b_raw_material_order_qty",
    "supplier_mix_offshore_pct": "stage_b_supplier_mix_offshore_pct",
    "supplier_mix_balanced_pct": "stage_b_supplier_mix_balanced_pct",
    "supplier_mix_premium_pct": "stage_b_supplier_mix_premium_pct",
    "max_backorder_units": "stage_b_max_backorder_units",
    "planned_borrowing_amount": "stage_b_planned_borrowing_amount",
}

PRODUCT_FIELDS = (
    "product_name",
    "is_active",
    "target_segment",
    "selling_price_per_unit",
    "forecast_units",
    "planned_production_units",
    "qc_budget_per_unit",
    "target_finished_goods_inventory",
    "retire_flag",
)

PROJECT_FIELDS = (
    "project_name",
    "target_segment",
    "target_tech_generation",
    "intended_slot_name",
    "planned_launch_round",
    "investment_this_round",
    "testing_intensity",
    "launch_now",
    "cancel_now",
    "cannibalization_group",
    "projected_base_defect_modifier",
    "projected_demand_fit_modifier",
)

PROJECT_FIXED_FIELDS = (
    "project_name",
    "target_segment",
    "target_tech_generation",
    "intended_slot_name",
    "planned_launch_round",
    "cannibalization_group",
    "projected_base_defect_modifier",
    "projected_demand_fit_modifier",
)


def _product_widget_key(slot_name: str, field_name: str) -> str:
    """Return the widget key for a product slot field."""
    return f"stage_b_product_{slot_name}_{field_name}"


def _project_widget_key(project_slot_name: str, field_name: str) -> str:
    """Return the widget key for a development-project field."""
    return f"stage_b_project_{project_slot_name}_{field_name}"


def _inject_compact_decision_css() -> None:
    """Apply compact page styling without changing decision logic."""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            min-width: 12rem !important;
            width: 12rem !important;
        }
        section[data-testid="stSidebar"] img {
            max-width: 80px !important;
        }
        div[data-testid="stSidebarContent"] {
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        div[data-testid="stSidebarContent"] p,
        div[data-testid="stSidebarContent"] a,
        div[data-testid="stSidebarContent"] span {
            font-size: 0.82rem;
        }
        .block-container {
            max-width: 96rem;
            padding-top: 1.7rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d7e0ec;
            border-radius: 0.45rem;
            padding: 0.55rem 0.65rem;
            min-height: 4.0rem;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.76rem;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.04rem;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.55rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.55rem;
        }
        div[data-testid="stNumberInput"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stSlider"] label {
            font-size: 0.76rem;
        }
        .kiki-row-card {
            border: 1px solid #d7e0ec;
            border-radius: 0.45rem;
            background: #ffffff;
            padding: 0.65rem 0.75rem;
            margin-bottom: 0.45rem;
        }
        .kiki-row-header {
            font-weight: 700;
            font-size: 0.95rem;
            margin-bottom: 0.15rem;
        }
        .kiki-chip {
            display: inline-block;
            border-radius: 999px;
            padding: 0.12rem 0.45rem;
            margin: 0 0.2rem 0.2rem 0;
            background: #edf3fa;
            color: #163153;
            font-weight: 700;
            font-size: 0.72rem;
            white-space: nowrap;
        }
        .kiki-chip-green { background: #dcf5e7; color: #087342; }
        .kiki-chip-amber { background: #fff0d2; color: #935c00; }
        .kiki-chip-red { background: #ffe1e1; color: #b42318; }
        .kiki-chip-blue { background: #e2edff; color: #225eaf; }
        .kiki-section-note {
            color: #5a667a;
            font-size: 0.82rem;
            margin-top: 0.25rem;
        }
        .kiki-submit-check {
            border: 1px solid #cfdae8;
            border-radius: 0.7rem;
            background: #ffffff;
            padding: 0.85rem 0.95rem 0.95rem 0.95rem;
            margin-top: 0.25rem;
        }
        .kiki-submit-check-title {
            font-weight: 800;
            font-size: 1.02rem;
            color: #111827;
            margin-bottom: 0.08rem;
        }
        .kiki-submit-check-note {
            color: #66758a;
            font-size: 0.78rem;
            margin-bottom: 0.8rem;
        }
        .kiki-submit-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
        }
        .kiki-submit-card {
            border: 1px solid #d8e1ec;
            border-top: 0.25rem solid var(--kiki-accent);
            border-radius: 0.55rem;
            background: #fbfdff;
            min-height: 5.3rem;
            display: grid;
            grid-template-columns: 4.7rem minmax(0, 1fr);
            gap: 0.6rem;
            padding: 0.5rem 0.55rem;
        }
        .kiki-submit-card img {
            width: 4.35rem;
            height: 4.35rem;
            object-fit: cover;
            border-radius: 0.55rem;
        }
        .kiki-submit-card-heading {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.35rem;
        }
        .kiki-submit-card-name {
            font-weight: 800;
            color: #111827;
            font-size: 0.9rem;
            line-height: 1.1;
        }
        .kiki-submit-card-role {
            color: #64748b;
            font-size: 0.68rem;
            margin-top: 0.1rem;
        }
        .kiki-submit-status {
            border-radius: 999px;
            padding: 0.1rem 0.42rem;
            font-size: 0.62rem;
            font-weight: 800;
            white-space: nowrap;
        }
        .kiki-submit-status-ready {
            background: #dcfce7;
            color: #166534;
        }
        .kiki-submit-status-caution {
            background: #fef3c7;
            color: #92400e;
        }
        .kiki-submit-status-review {
            background: #fee2e2;
            color: #b91c1c;
        }
        .kiki-submit-items {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.18rem 0.5rem;
            margin-top: 0.32rem;
        }
        .kiki-submit-item {
            display: flex;
            align-items: center;
            gap: 0.28rem;
            min-width: 0;
            color: #374151;
            font-size: 0.66rem;
            line-height: 1.15;
        }
        .kiki-submit-dot {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.0rem;
            height: 1.0rem;
            border-radius: 999px;
            color: #ffffff;
            font-size: 0.52rem;
            font-weight: 900;
            flex: 0 0 auto;
        }
        .kiki-submit-dot-ok {
            background: #16a34a;
        }
        .kiki-submit-dot-warn {
            background: #f59e0b;
        }
        .kiki-submit-dot-miss {
            background: #dc2626;
        }
        @media (max-width: 900px) {
            .kiki-submit-grid {
                grid-template-columns: 1fr;
            }
            .kiki-submit-card {
                grid-template-columns: 4.2rem minmax(0, 1fr);
            }
            .kiki-submit-card img {
                width: 3.95rem;
                height: 3.95rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_option_index(options: list[str], value: str) -> int:
    """Return a valid selectbox index for persisted values."""
    return options.index(value) if value in options else 0


def _chip(text: str, tone: str = "") -> str:
    """Return a compact HTML chip."""
    suffix = f" kiki-chip-{tone}" if tone else ""
    return f'<span class="kiki-chip{suffix}">{text}</span>'


@lru_cache(maxsize=8)
def _image_data_uri(path_text: str) -> str:
    """Return an image data URI for compact Streamlit HTML cards."""
    path = Path(path_text)
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _submit_check_item(label: str, state: str, message: str = "") -> dict[str, str]:
    """Build a compact checklist item."""
    return {"label": label, "state": state, "message": message}


def _submit_section_state(items: list[dict[str, str]]) -> str:
    """Summarize a section as ready, caution, or needs review."""
    states = {item["state"] for item in items}
    if "miss" in states:
        return "needs review"
    if "warn" in states:
        return "caution"
    return "ready"


def _build_kiki_submit_checklist(
    candidate_firm_decision: TeamDecision,
    candidate_product_decisions: list[ProductDecision],
    candidate_projects: list[ProductDevelopmentProject],
    preview,
    current_round: int,
) -> list[dict[str, object]]:
    """Build the four pre-submit OM checklist sections shown near Save."""
    active_products = [decision for decision in candidate_product_decisions if decision.is_active]
    total_forecast = int(getattr(preview, "total_forecast_units", 0) or 0)
    total_planned = int(getattr(preview, "total_planned_production_units", 0) or 0)
    effective_capacity = int(getattr(preview, "effective_capacity_units", 0) or 0)
    raw_material_available = float(getattr(preview, "raw_material_units_available", 0) or 0)
    raw_material_gap = raw_material_available - getattr(preview, "total_material_required", total_planned)
    forecast_gap = abs(int(getattr(preview, "forecast_production_gap_units", 0) or 0))
    forecast_gap_base = max(total_forecast, total_planned, 1)
    planned_utilization = total_planned / effective_capacity if effective_capacity > 0 else 0.0
    defect_rate = float(getattr(preview, "projected_weighted_defect_rate", 0.0) or 0.0)
    likely_borrowing = float(getattr(preview, "projected_likely_borrowing_need", 0.0) or 0.0)
    working_capital = float(getattr(preview, "projected_working_capital_requirement", 0.0) or 0.0)
    planned_borrowing = float(candidate_firm_decision.planned_borrowing_amount or 0.0)
    launch_requests = [
        project for project in candidate_projects if project.is_defined() and project.launch_now
    ]
    launch_gate_ready_count = sum(
        1
        for project in launch_requests
        if project_ready_at_round_start(project, current_round)
    )

    if not active_products:
        forecast_state = "warn"
        forecast_message = "No active product has a current demand plan."
    elif all(decision.forecast_units > 0 for decision in active_products):
        forecast_state = "ok"
        forecast_message = ""
    else:
        forecast_state = "miss"
        forecast_message = "At least one active product is missing a forecast."

    if forecast_gap <= max(25, int(forecast_gap_base * 0.25)):
        demand_gap_state = "ok"
    else:
        demand_gap_state = "warn"

    price_state = (
        "ok"
        if all(
            decision.selling_price_per_unit > 0 and decision.target_segment in TARGET_SEGMENTS
            for decision in active_products
        )
        else "miss"
    )

    production_state = "ok" if total_planned > 0 or not active_products else "miss"
    capacity_state = "ok" if total_planned <= effective_capacity else "miss"
    if total_planned <= 0:
        utilization_state = "warn" if active_products else "ok"
    elif planned_utilization > 0.98 or planned_utilization < 0.25:
        utilization_state = "warn"
    else:
        utilization_state = "ok"

    if total_planned <= 0:
        raw_material_state = "ok"
        raw_material_label = "No RM need yet"
        raw_material_message = ""
    elif raw_material_gap >= 0:
        raw_material_state = "ok"
        raw_material_label = "RM plan covers production"
        raw_material_message = ""
    elif candidate_firm_decision.raw_material_order_qty > 0:
        raw_material_state = "warn"
        raw_material_label = "RM short this round"
        raw_material_message = "Raw materials may limit this round's production."
    else:
        raw_material_state = "miss"
        raw_material_label = "RM order missing"
        raw_material_message = "Raw materials may not support planned production."

    if candidate_firm_decision.raw_material_order_qty > 0:
        arrival_state = "ok"
        arrival_label = "Arrival timing shown"
        arrival_message = ""
    elif raw_material_gap >= 0:
        arrival_state = "ok"
        arrival_label = "No order needed"
        arrival_message = ""
    else:
        arrival_state = "warn"
        arrival_label = "No arrival timing"
        arrival_message = "Place a raw-material order to see expected arrival timing."

    if total_planned <= 0 or defect_rate <= 0.05:
        qc_state = "ok"
    elif defect_rate >= 0.12:
        qc_state = "miss"
    else:
        qc_state = "warn"

    if likely_borrowing <= 0:
        cash_state = "ok"
    elif planned_borrowing >= likely_borrowing * 0.85:
        cash_state = "ok"
    elif planned_borrowing <= 0 and likely_borrowing >= max(100_000.0, working_capital * 4.0):
        cash_state = "miss"
    else:
        cash_state = "warn"

    if not launch_requests:
        launch_state = "ok"
        launch_label = "No launch request"
        launch_message = ""
    elif launch_gate_ready_count >= len(launch_requests):
        launch_state = "ok"
        launch_label = "Launch gate ready"
        launch_message = ""
    else:
        launch_state = "miss"
        launch_label = "Launch gate not ready"
        launch_message = "A launch request may fail readiness, funding, or timing gates."

    sections: list[dict[str, object]] = [
        {
            "title": "Market Forecast",
            "role": "forecast analyst",
            "accent": "#0ea5a4",
            "mascot": KIKI_CHECKLIST_MASCOT_DIR / "market_forecast_kiki.png",
            "items": [
                _submit_check_item("Forecast entered", forecast_state, forecast_message),
                _submit_check_item("Demand gap checked", demand_gap_state),
                _submit_check_item("Price reviewed", price_state, "Review price and target segment."),
            ],
        },
        {
            "title": "Production Capacity",
            "role": "production planner",
            "accent": "#2563eb",
            "mascot": KIKI_CHECKLIST_MASCOT_DIR / "production_capacity_kiki.png",
            "items": [
                _submit_check_item("Production planned", production_state, "Active products have no planned production."),
                _submit_check_item("Capacity checked", capacity_state, "Planned production exceeds effective capacity."),
                _submit_check_item("Utilization reviewed", utilization_state),
            ],
        },
        {
            "title": "Materials Supply",
            "role": "logistics checker",
            "accent": "#d97706",
            "mascot": KIKI_CHECKLIST_MASCOT_DIR / "materials_supply_kiki.png",
            "items": [
                _submit_check_item(
                    "Supplier mix 100%",
                    "ok" if candidate_firm_decision.supplier_mix_valid() else "miss",
                    "Supplier percentages must sum to 100.",
                ),
                _submit_check_item(raw_material_label, raw_material_state, raw_material_message),
                _submit_check_item(arrival_label, arrival_state, arrival_message),
            ],
        },
        {
            "title": "Service QC Cash",
            "role": "risk guard",
            "accent": "#16a34a",
            "mascot": KIKI_CHECKLIST_MASCOT_DIR / "service_qc_cash_kiki.png",
            "items": [
                _submit_check_item("Backlog reviewed", "ok"),
                _submit_check_item("QC reviewed", qc_state, "Projected defect rate is extremely high."),
                _submit_check_item("Cash plan checked", cash_state, "Cash shortfall is severe and no borrowing is planned."),
                _submit_check_item(launch_label, launch_state, launch_message),
            ],
        },
    ]
    for section in sections:
        section["state"] = _submit_section_state(section["items"])  # type: ignore[arg-type]
    return sections


def _kiki_submit_warning_messages(sections: list[dict[str, object]]) -> list[str]:
    """Return section-level soft warnings that require student confirmation."""
    messages: list[str] = []
    for section in sections:
        title = str(section["title"])
        for item in section["items"]:  # type: ignore[assignment]
            if item["state"] == "miss":
                detail = item["message"] or item["label"]
                messages.append(f"{title}: {detail}")
    return messages


def _render_kiki_submit_checklist(sections: list[dict[str, object]]) -> None:
    """Render the compact four-part Kiki submit checklist."""
    status_class_lookup = {
        "ready": "ready",
        "caution": "caution",
        "needs review": "review",
    }
    dot_text_lookup = {"ok": "OK", "warn": "!", "miss": "X"}
    cards: list[str] = []
    for section in sections:
        status = str(section["state"])
        status_class = status_class_lookup.get(status, "review")
        mascot_uri = _image_data_uri(str(section["mascot"]))
        items_html = []
        for item in section["items"]:  # type: ignore[assignment]
            item_state = item["state"]
            items_html.append(
                '<div class="kiki-submit-item">'
                f'<span class="kiki-submit-dot kiki-submit-dot-{escape(item_state)}">'
                f"{escape(dot_text_lookup.get(item_state, item_state.upper()))}</span>"
                f"<span>{escape(item['label'])}</span>"
                "</div>"
            )
        image_html = (
            f'<img src="{mascot_uri}" alt="{escape(str(section["title"]))} Kiki mascot">'
            if mascot_uri
            else ""
        )
        cards.append(
            f'<div class="kiki-submit-card" style="--kiki-accent: {escape(str(section["accent"]))};">'
            f"<div>{image_html}</div>"
            "<div>"
            '<div class="kiki-submit-card-heading">'
            "<div>"
            f'<div class="kiki-submit-card-name">{escape(str(section["title"]))}</div>'
            f'<div class="kiki-submit-card-role">{escape(str(section["role"]))}</div>'
            "</div>"
            f'<span class="kiki-submit-status kiki-submit-status-{status_class}">{escape(status)}</span>'
            "</div>"
            f'<div class="kiki-submit-items">{"".join(items_html)}</div>'
            "</div>"
            "</div>"
        )
    st.markdown(
        '<div class="kiki-submit-check">'
        '<div class="kiki-submit-check-title">Kiki\'s 4-Part Pre-Submit Check</div>'
        '<div class="kiki-submit-check-note">'
        "Small role mascots help teams review the four major decision groups before saving the round plan."
        "</div>"
        f'<div class="kiki-submit-grid">{"".join(cards)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _clear_submit_warning_state() -> None:
    """Clear any pending soft-warning confirmation."""
    st.session_state.pop(SUBMIT_WARNING_CONTEXT_KEY, None)
    st.session_state.pop(SUBMIT_WARNING_MESSAGES_KEY, None)


def _current_supplier_mix() -> dict[str, float]:
    """Return the current supplier mix normalized the same way as the engine."""
    raw_mix = {
        "Offshore Value": float(
            st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_offshore_pct"], 0.0)
        ),
        "Balanced Source": float(
            st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_balanced_pct"], 0.0)
        ),
        "Premium Reliable": float(
            st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_premium_pct"], 0.0)
        ),
    }
    raw_total = max(sum(raw_mix.values()), 0.0)
    if raw_total <= 0:
        return {
            "Offshore Value": 0.0,
            "Balanced Source": 1.0,
            "Premium Reliable": 0.0,
        }
    return {supplier: raw_mix[supplier] / raw_total for supplier in SUPPLIER_NAMES}


def _current_material_timing(market_report) -> dict[str, float | int]:
    """Calculate the expected arrival timing for the current raw-material order."""
    timing = material_order_timing(_current_supplier_mix(), market_report.supply_risk)
    return {
        **timing,
        "order_qty": int(st.session_state.get(FIRM_WIDGET_KEYS["raw_material_order_qty"], 0)),
        "arrival_round": market_report.round_number + timing["lead_time_rounds"],
    }


def _project_fixed_settings_locked(project: ProductDevelopmentProject) -> bool:
    """Return whether project-charter fields should be locked in the UI."""
    return (
        project.is_pipeline_active()
        and (
            project.cumulative_investment > 0
            or project.investment_this_round > 0
            or project.testing_intensity > 0
            or project.launch_readiness_score > 0
            or project.status in {"development", "pilot", "launch_ready"}
        )
    )


def _sync_locked_project_fields(project: ProductDevelopmentProject) -> None:
    """Keep disabled project-charter widgets aligned with persisted values."""
    for field_name in PROJECT_FIXED_FIELDS:
        st.session_state[_project_widget_key(project.project_slot_name, field_name)] = getattr(
            project,
            field_name,
        )


def _build_team_options(current_round: int) -> list[str]:
    """Collect known team names for admin selection."""
    team_names = {
        user.team_name
        for user in load_users(role="team_leader")
        if user.team_name
    }
    team_names.update(
        decision.team_name
        for decision in load_team_decisions(round_number=current_round)
        if decision.team_name
    )
    team_names.update(
        state.team_name
        for state in load_team_states()
        if state.team_name
    )
    team_names.update(
        line.team_name
        for line in load_product_lines()
        if line.team_name
    )
    return sorted(team_names)


def _suggested_firm_decision(team_name: str, archetype: TeamArchetype) -> TeamDecision:
    """Build the firm-level suggested decision from an archetype."""
    return TeamDecision(
        team_name=team_name,
        archetype=archetype.name,
        overtime_capacity_units=archetype.suggested_overtime_capacity_units,
        capacity_expansion_units=archetype.suggested_capacity_expansion_units,
        raw_material_order_qty=archetype.suggested_raw_material_order_qty,
        supplier_mix_offshore_pct=archetype.suggested_supplier_mix_offshore_pct,
        supplier_mix_balanced_pct=archetype.suggested_supplier_mix_balanced_pct,
        supplier_mix_premium_pct=archetype.suggested_supplier_mix_premium_pct,
        expedited_order_share_pct=0.0,
        max_backorder_units=archetype.suggested_max_backorder_units,
        planned_borrowing_amount=0.0,
    )


def _suggested_product_decisions(
    team_name: str,
    archetype: TeamArchetype,
    product_lines: list[ProductLine],
) -> list[ProductDecision]:
    """Build suggested decisions for the configured portfolio slots."""
    line_by_slot = {line.slot_name: line for line in product_lines}
    template_by_slot = {
        template.slot_name: template
        for template in archetype.suggested_product_templates
    }
    product_decisions: list[ProductDecision] = []

    for slot_name in PRODUCT_SLOT_NAMES:
        product_line = line_by_slot[slot_name]
        template = template_by_slot.get(slot_name)
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        product_decisions.append(
            ProductDecision(
                product_id=product_line.product_id,
                team_name=team_name,
                slot_name=slot_name,
                product_name=product_line.product_name,
                is_active=False if is_retired_slot else product_line.is_active,
                target_segment=product_line.target_segment,
                selling_price_per_unit=(
                    0.0
                    if is_retired_slot
                    else template.suggested_selling_price_per_unit if template else 130.0
                ),
                forecast_units=(
                    0
                    if is_retired_slot
                    else template.suggested_planned_production_units if template else 0
                ),
                planned_production_units=(
                    0
                    if is_retired_slot
                    else template.suggested_planned_production_units if template else 0
                ),
                qc_budget_per_unit=(
                    0.0
                    if is_retired_slot
                    else template.suggested_qc_budget_per_unit if template else 0.0
                ),
                target_finished_goods_inventory=(
                    0
                    if is_retired_slot
                    else template.suggested_target_finished_goods_inventory
                    if template
                    else 0
                ),
                retire_flag=False,
            )
        )

    return product_decisions


def _latest_previous_firm_decision(
    current_round: int,
    team_name: str,
) -> TeamDecision | None:
    """Return the most recent saved firm decision before the current round."""
    for previous_round in range(current_round - 1, 0, -1):
        decision = load_team_decision(previous_round, team_name)
        if decision is not None:
            return decision
    return None


def _latest_previous_product_decisions(
    current_round: int,
    team_name: str,
) -> list[ProductDecision]:
    """Return the most recent saved product-slot decisions before this round."""
    for previous_round in range(current_round - 1, 0, -1):
        decisions = load_product_decisions(round_number=previous_round, team_name=team_name)
        if decisions:
            return decisions
    return []


def _seed_product_decisions_for_round(
    team_name: str,
    archetype: TeamArchetype,
    product_lines: list[ProductLine],
    current_round: int,
) -> list[ProductDecision]:
    """Build current-round defaults from prior choices while honoring current products."""
    previous_by_slot = {
        decision.slot_name: decision
        for decision in _latest_previous_product_decisions(current_round, team_name)
    }
    suggested_by_slot = {
        decision.slot_name: decision
        for decision in _suggested_product_decisions(team_name, archetype, product_lines)
    }
    defaults: list[ProductDecision] = []

    for product_line in sorted(product_lines, key=lambda item: item.slot_name):
        baseline = previous_by_slot.get(product_line.slot_name) or suggested_by_slot[product_line.slot_name]
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        defaults.append(
            ProductDecision(
                product_id=product_line.product_id,
                team_name=team_name,
                slot_name=product_line.slot_name,
                product_name=product_line.product_name,
                is_active=False if is_retired_slot else product_line.is_active,
                target_segment=product_line.target_segment,
                selling_price_per_unit=0.0 if is_retired_slot else baseline.selling_price_per_unit,
                forecast_units=0 if is_retired_slot else baseline.forecast_units,
                planned_production_units=0 if is_retired_slot else baseline.planned_production_units,
                qc_budget_per_unit=0.0 if is_retired_slot else baseline.qc_budget_per_unit,
                target_finished_goods_inventory=(
                    0 if is_retired_slot else baseline.target_finished_goods_inventory
                ),
                retire_flag=False,
            )
        )

    return defaults


def _decision_widgets_look_unseeded(product_lines: list[ProductLine]) -> bool:
    """Detect stale or blank widget state after round/page transitions."""
    active_lines = [
        line
        for line in product_lines
        if line.is_active and not (line.retirement_flag and not line.is_active)
    ]
    missing_product_name = any(
        line.product_name.strip()
        and not str(
            st.session_state.get(_product_widget_key(line.slot_name, "product_name"), "")
        ).strip()
        for line in active_lines
    )
    supplier_mix_total = sum(
        float(st.session_state.get(FIRM_WIDGET_KEYS[field_name], 0.0) or 0.0)
        for field_name in (
            "supplier_mix_offshore_pct",
            "supplier_mix_balanced_pct",
            "supplier_mix_premium_pct",
        )
    )
    return missing_product_name or supplier_mix_total <= 0.0


def _seed_projects(
    team_name: str,
    market_round: int,
) -> list[ProductDevelopmentProject]:
    """Build blank Stage B project slots for the decision editor."""
    return [
        ProductDevelopmentProject(
            project_id=build_project_id(team_name, project_slot_name),
            team_name=team_name,
            project_slot_name=project_slot_name,
            project_name="",
            target_segment="mid",
            target_tech_generation=2,
            intended_slot_name="C",
            required_investment=0.0,
            cumulative_investment=0.0,
            investment_this_round=0.0,
            testing_intensity=0.0,
            launch_readiness_score=0.0,
            planned_launch_round=market_round + 1,
            earliest_launch_round=market_round + 1,
            status="concept",
            cannibalization_group="",
            projected_base_defect_modifier=0.0,
            projected_demand_fit_modifier=1.0,
            created_round=market_round,
        )
        for project_slot_name in PROJECT_SLOT_NAMES
    ]


def _load_decisions_into_session(
    firm_decision: TeamDecision,
    product_decisions: list[ProductDecision],
    projects: list[ProductDevelopmentProject],
) -> None:
    """Push non-archetype decision objects into Streamlit widget state."""
    for field_name, widget_key in FIRM_WIDGET_KEYS.items():
        st.session_state[widget_key] = getattr(firm_decision, field_name)

    decision_by_slot = {decision.slot_name: decision for decision in product_decisions}
    for slot_name in PRODUCT_SLOT_NAMES:
        decision = decision_by_slot[slot_name]
        for field_name in PRODUCT_FIELDS:
            st.session_state[_product_widget_key(slot_name, field_name)] = getattr(
                decision,
                field_name,
            )

    project_by_slot = {project.project_slot_name: project for project in projects}
    for project_slot_name in PROJECT_SLOT_NAMES:
        project = project_by_slot[project_slot_name]
        for field_name in PROJECT_FIELDS:
            st.session_state[_project_widget_key(project_slot_name, field_name)] = getattr(
                project,
                field_name,
            )


def _current_firm_decision(team_name: str, archetype_name: str) -> TeamDecision:
    """Read the firm-level decision from the current widget state."""
    return TeamDecision(
        team_name=team_name.strip(),
        archetype=archetype_name,
        overtime_capacity_units=int(st.session_state.get(FIRM_WIDGET_KEYS["overtime_capacity_units"], 0)),
        capacity_expansion_units=int(st.session_state.get(FIRM_WIDGET_KEYS["capacity_expansion_units"], 0)),
        raw_material_order_qty=int(st.session_state.get(FIRM_WIDGET_KEYS["raw_material_order_qty"], 0)),
        supplier_mix_offshore_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_offshore_pct"], 0.0)),
        supplier_mix_balanced_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_balanced_pct"], 0.0)),
        supplier_mix_premium_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_premium_pct"], 0.0)),
        expedited_order_share_pct=0.0,
        max_backorder_units=int(st.session_state.get(FIRM_WIDGET_KEYS["max_backorder_units"], 0)),
        planned_borrowing_amount=float(st.session_state.get(FIRM_WIDGET_KEYS["planned_borrowing_amount"], 0.0)),
    )


def _current_product_decisions(
    team_name: str,
    product_lines: list[ProductLine],
) -> list[ProductDecision]:
    """Read all product-slot decisions from the current widget state."""
    line_by_slot = {line.slot_name: line for line in product_lines}
    decisions: list[ProductDecision] = []

    for slot_name in PRODUCT_SLOT_NAMES:
        product_line = line_by_slot[slot_name]
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        product_name = str(
            st.session_state.get(_product_widget_key(slot_name, "product_name"), "")
        ).strip() or product_line.product_name
        is_active = (
            False
            if is_retired_slot
            else bool(
                st.session_state.get(_product_widget_key(slot_name, "is_active"), False)
            )
        )
        decisions.append(
            ProductDecision(
                product_id=product_line.product_id,
                team_name=team_name.strip(),
                slot_name=slot_name,
                product_name=product_name,
                is_active=is_active,
                target_segment=str(
                    st.session_state.get(
                        _product_widget_key(slot_name, "target_segment"),
                        product_line.target_segment,
                    )
                ).lower(),
                selling_price_per_unit=float(
                    st.session_state.get(
                        _product_widget_key(slot_name, "selling_price_per_unit"),
                        0.0,
                    )
                ),
                forecast_units=(
                    int(
                        st.session_state.get(
                            _product_widget_key(slot_name, "forecast_units"),
                            0,
                        )
                    )
                    if is_active
                    else 0
                ),
                planned_production_units=(
                    int(
                        st.session_state.get(
                            _product_widget_key(slot_name, "planned_production_units"),
                            0,
                        )
                    )
                    if is_active
                    else 0
                ),
                qc_budget_per_unit=float(
                    st.session_state.get(
                        _product_widget_key(slot_name, "qc_budget_per_unit"),
                        0.0,
                    )
                ),
                target_finished_goods_inventory=int(
                    st.session_state.get(
                        _product_widget_key(slot_name, "target_finished_goods_inventory"),
                        0,
                    )
                ),
                retire_flag=bool(
                    st.session_state.get(_product_widget_key(slot_name, "retire_flag"), False)
                )
                if not is_retired_slot
                else False,
            )
        )

    return decisions


def _build_product_forecasts(
    round_number: int,
    product_decisions: list[ProductDecision],
) -> list[ProductForecast]:
    """Convert current product decisions into persisted forecast rows."""
    return [
        ProductForecast(
            round_number=round_number,
            team_name=decision.team_name,
            product_id=decision.product_id,
            slot_name=decision.slot_name,
            product_name=decision.product_name,
            forecast_units=decision.forecast_units if decision.is_active else 0,
        )
        for decision in product_decisions
    ]


def _current_projects(
    team_name: str,
    current_round: int,
    existing_projects: list[ProductDevelopmentProject],
) -> list[ProductDevelopmentProject]:
    """Read the editable development-project slots from widget state."""
    existing_by_slot = {project.project_slot_name: project for project in existing_projects}
    projects: list[ProductDevelopmentProject] = []

    for project_slot_name in PROJECT_SLOT_NAMES:
        existing_project = existing_by_slot[project_slot_name]
        fixed_settings_locked = _project_fixed_settings_locked(existing_project)
        if fixed_settings_locked:
            project_name = existing_project.project_name
            target_segment = existing_project.target_segment
            target_tech_generation = existing_project.target_tech_generation
            intended_slot_name = existing_project.intended_slot_name
            planned_launch_round = existing_project.planned_launch_round
            cannibalization_group = existing_project.cannibalization_group
            projected_base_defect_modifier = existing_project.projected_base_defect_modifier
            projected_demand_fit_modifier = existing_project.projected_demand_fit_modifier
        else:
            project_name = str(
                st.session_state.get(_project_widget_key(project_slot_name, "project_name"), "")
            ).strip()
            target_segment = str(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "target_segment"),
                    existing_project.target_segment,
                )
            ).lower()
            target_tech_generation = int(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "target_tech_generation"),
                    existing_project.target_tech_generation,
                )
            )
            intended_slot_name = str(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "intended_slot_name"),
                    existing_project.intended_slot_name,
                )
            ).upper()
            planned_launch_round = int(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "planned_launch_round"),
                    existing_project.planned_launch_round,
                )
            )
            cannibalization_group = str(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "cannibalization_group"),
                    existing_project.cannibalization_group,
                )
            ).strip()
            projected_base_defect_modifier = float(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "projected_base_defect_modifier"),
                    existing_project.projected_base_defect_modifier,
                )
            )
            projected_demand_fit_modifier = float(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "projected_demand_fit_modifier"),
                    existing_project.projected_demand_fit_modifier,
                )
            )
        investment_this_round = float(
            st.session_state.get(
                _project_widget_key(project_slot_name, "investment_this_round"),
                0.0,
            )
        )
        testing_intensity = float(
            st.session_state.get(
                _project_widget_key(project_slot_name, "testing_intensity"),
                0.0,
            )
        )
        reset_pipeline = (
            existing_project.status in {"launched", "canceled"}
            and (
                project_name != existing_project.project_name
                or target_segment != existing_project.target_segment
                or target_tech_generation != existing_project.target_tech_generation
                or intended_slot_name != existing_project.intended_slot_name
                or planned_launch_round != existing_project.planned_launch_round
                or cannibalization_group != existing_project.cannibalization_group
                or projected_base_defect_modifier != existing_project.projected_base_defect_modifier
                or projected_demand_fit_modifier != existing_project.projected_demand_fit_modifier
                or investment_this_round > 0
                or testing_intensity > 0
            )
            and project_name
        )
        created_round = current_round if reset_pipeline else existing_project.created_round
        cumulative_investment = 0.0 if reset_pipeline else existing_project.cumulative_investment
        launch_readiness_score = 0.0 if reset_pipeline else existing_project.launch_readiness_score
        status = "concept" if reset_pipeline else existing_project.status
        launched_round = None if reset_pipeline else existing_project.launched_round
        canceled_round = None if reset_pipeline else existing_project.canceled_round

        projects.append(
            ProductDevelopmentProject(
                project_id=existing_project.project_id,
                team_name=team_name.strip(),
                project_slot_name=project_slot_name,
                project_name=project_name,
                target_segment=target_segment,
                target_tech_generation=target_tech_generation,
                intended_slot_name=intended_slot_name,
                required_investment=existing_project.required_investment,
                cumulative_investment=cumulative_investment,
                cumulative_testing=0.0 if reset_pipeline else existing_project.cumulative_testing,
                investment_this_round=investment_this_round,
                testing_intensity=testing_intensity,
                launch_readiness_score=launch_readiness_score,
                planned_launch_round=planned_launch_round,
                earliest_launch_round=existing_project.earliest_launch_round,
                status=status,
                cannibalization_group=cannibalization_group,
                projected_base_defect_modifier=projected_base_defect_modifier,
                projected_demand_fit_modifier=projected_demand_fit_modifier,
                created_round=created_round,
                launched_round=launched_round,
                canceled_round=canceled_round,
                launch_now=bool(
                    st.session_state.get(_project_widget_key(project_slot_name, "launch_now"), False)
                ),
                cancel_now=bool(
                    st.session_state.get(_project_widget_key(project_slot_name, "cancel_now"), False)
                ),
                replaced_product_name=existing_project.replaced_product_name,
            )
        )

    return projects


def _merge_product_lines(
    existing_product_lines: list[ProductLine],
    product_decisions: list[ProductDecision],
) -> list[ProductLine]:
    """Update persistent product-line metadata from the submitted portfolio."""
    decision_by_slot = {decision.slot_name: decision for decision in product_decisions}
    merged_lines: list[ProductLine] = []

    for product_line in sorted(existing_product_lines, key=lambda item: item.slot_name):
        decision = decision_by_slot[product_line.slot_name]
        merged_lines.append(
            ProductLine(
                product_id=product_line.product_id,
                team_name=product_line.team_name,
                product_name=decision.product_name,
                slot_name=product_line.slot_name,
                is_active=decision.is_active,
                target_segment=decision.target_segment,
                lifecycle_stage=product_line.lifecycle_stage,
                age_in_rounds=product_line.age_in_rounds,
                base_defect_rate_modifier=product_line.base_defect_rate_modifier,
                base_demand_fit_modifier=product_line.base_demand_fit_modifier,
                tech_generation=product_line.tech_generation,
                cannibalization_group=product_line.cannibalization_group,
                launch_round=product_line.launch_round,
                retirement_flag=product_line.retirement_flag,
                retired_round=product_line.retired_round,
                replacement_project_id=product_line.replacement_project_id,
                inventory_units=product_line.inventory_units,
                backlog_units=product_line.backlog_units,
                material_design=product_line.material_design,
            )
        )

    return merged_lines


def _render_state_snapshot(
    product_lines: list[ProductLine],
    existing_state,
    market_report,
    selected_archetype: TeamArchetype,
) -> None:
    """Render the team's current persistent operating and technology position."""
    beginning_inventory = sum(max(line.inventory_units, 0) for line in product_lines)
    beginning_backlog = sum(max(line.backlog_units, 0) for line in product_lines)
    is_first_round_state = not existing_state or not existing_state.completed_rounds
    installed_capacity = (
        existing_state.capacity_units
        if existing_state and existing_state.capacity_units > 0
        else selected_archetype.base_capacity
        if is_first_round_state
        else 0
    )
    reputation = (
        existing_state.reputation_score
        if existing_state and existing_state.reputation_score > 0
        else selected_archetype.base_reputation
        if is_first_round_state
        else 0.0
    )
    raw_material_inventory = (
        existing_state.raw_material_inventory
        if existing_state and existing_state.raw_material_inventory > 0
        else int(round(selected_archetype.base_capacity * STARTING_RAW_MATERIAL_COVERAGE))
        if is_first_round_state
        else 0
    )
    cash_balance = existing_state.cash_balance if existing_state else 0.0
    short_term_debt = existing_state.short_term_debt_balance if existing_state else 0.0
    interest_last_round = (
        existing_state.interest_expense_last_round if existing_state else 0.0
    )
    liquidity_flag = existing_state.liquidity_warning_flag if existing_state else False
    average_tech = (
        sum(line.tech_generation for line in product_lines if line.is_active)
        / max(sum(1 for line in product_lines if line.is_active), 1)
    )

    snapshot_cols = st.columns(7)
    snapshot_cols[0].metric("Capacity", f"{installed_capacity:,}")
    snapshot_cols[1].metric("FG Inv.", f"{beginning_inventory:,}")
    snapshot_cols[2].metric("Backlog", f"{beginning_backlog:,}")
    snapshot_cols[3].metric("Reputation", f"{reputation:.1f}")
    snapshot_cols[4].metric("Cash", f"${cash_balance:,.0f}")
    snapshot_cols[5].metric("Debt", f"${short_term_debt:,.0f}")
    snapshot_cols[6].metric(
        "Tech vs Market",
        f"{average_tech - market_report.current_market_generation:+.1f}",
    )
    arriving_units = sum(
        order.quantity for order in (existing_state.open_material_orders if existing_state else [])
        if order.arrival_round <= market_report.round_number
    )
    material_cols = st.columns(3)
    format_rm = lambda value: f"{value:,.2f}".rstrip("0").rstrip(".")
    material_cols[0].metric("RM Carried Over", format_rm(raw_material_inventory),
                            help="Raw materials remaining after the previous round.")
    material_cols[1].metric("RM Arriving This Round", format_rm(arriving_units),
                            help="Previously placed orders due by this round; usable in this round's production.")
    material_cols[2].metric("RM Available for Production", format_rm(raw_material_inventory + arriving_units),
                            help="Carried-over materials plus orders arriving this round, before production consumption.")
    st.caption(
        f"Last-round interest expense: ${interest_last_round:,.0f} | "
        f"Liquidity warning flag: {'On' if liquidity_flag else 'Off'}"
    )
    if existing_state and existing_state.open_material_orders:
        incoming_rows = public_incoming_orders(existing_state.open_material_orders, market_report.round_number)
        st.caption("Incoming raw-material orders already placed and not yet received:")
        st.dataframe(pd.DataFrame(incoming_rows), use_container_width=True, hide_index=True)
    else:
        st.caption("Incoming raw-material orders: none currently waiting to arrive.")


def _render_supplier_quotes(quote):
    labels = ('Supplier', 'USD / RM', 'Units', 'Normal', 'Range', 'On time', 'Materials', 'Fee share')
    rows = []
    for row in quote:
        values = (row['label'], f"${row['unit_cost']:,.2f}", f"{row['quantity']:,}",
                  f"R{row['normal_arrival']}", f"R{row['normal_arrival']}-R{row['latest_arrival']}",
                  f"{row['on_time']:.1%}", f"${row['material_cost']:,.2f}", f"${row['order_fee']:,.2f}")
        rows.append('<tr>' + ''.join(f'<td data-label="{label}">{escape(value)}</td>'
                                    for label, value in zip(labels, values)) + '</tr>')
    st.html('''<style>
    .kiki-sourcing-table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:14px}
    .kiki-sourcing-table th,.kiki-sourcing-table td{padding:10px 6px;border-bottom:1px solid #d5d9e0;text-align:right;overflow-wrap:anywhere}
    .kiki-sourcing-table th{font-size:12px;font-weight:600}.kiki-sourcing-table th:first-child,.kiki-sourcing-table td:first-child{text-align:left}
    .kiki-sourcing-table td{font-variant-numeric:tabular-nums}
    @media(max-width:680px){.kiki-sourcing-table,.kiki-sourcing-table tbody,.kiki-sourcing-table tr{display:block;width:100%}
    .kiki-sourcing-table thead{display:none}.kiki-sourcing-table tr{padding:8px 0;border-bottom:1px solid #d5d9e0}
    .kiki-sourcing-table td{display:flex;justify-content:space-between;gap:12px;padding:4px 0;border:0}
    .kiki-sourcing-table td:before{content:attr(data-label);font-size:12px;text-align:left}}
    </style><table class="kiki-sourcing-table" aria-label="Supplier quotes"><thead><tr>'''
    + ''.join(f'<th>{label}</th>' for label in labels) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')


def _render_firm_controls(market_report, selected_archetype) -> None:
    """Render compact firm-level operations, sourcing, and finance controls."""
    st.markdown("### 3. Firm Controls")
    st.caption("Shared operations, sourcing, and finance choices for the whole firm.")
    firm_cols = st.columns(9)
    firm_cols[0].number_input(
        "Overtime Capacity",
        min_value=0,
        step=10,
        key=FIRM_WIDGET_KEYS["overtime_capacity_units"],
    )
    firm_cols[1].number_input(
        "Capacity Expansion",
        min_value=0,
        step=10,
        key=FIRM_WIDGET_KEYS["capacity_expansion_units"],
    )
    firm_cols[2].number_input(
        "Max Backorder",
        min_value=0,
        step=10,
        key=FIRM_WIDGET_KEYS["max_backorder_units"],
    )
    firm_cols[3].number_input(
        "Raw Material Order",
        min_value=0,
        step=10,
        key=FIRM_WIDGET_KEYS["raw_material_order_qty"],
    )
    firm_cols[4].number_input(
        "Borrowing",
        min_value=0.0,
        step=500.0,
        key=FIRM_WIDGET_KEYS["planned_borrowing_amount"],
    )
    firm_cols[5].number_input(
        "Economy %",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key=FIRM_WIDGET_KEYS["supplier_mix_offshore_pct"],
    )
    firm_cols[6].number_input(
        "Standard %",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key=FIRM_WIDGET_KEYS["supplier_mix_balanced_pct"],
    )
    firm_cols[7].number_input(
        "Reliable %",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key=FIRM_WIDGET_KEYS["supplier_mix_premium_pct"],
    )
    supplier_total = sum(
        float(st.session_state.get(FIRM_WIDGET_KEYS[key], 0.0))
        for key in (
            "supplier_mix_offshore_pct",
            "supplier_mix_balanced_pct",
            "supplier_mix_premium_pct",
        )
    )
    firm_cols[8].metric("Supplier Total", f"{supplier_total:.0f}%")
    if round(supplier_total, 6) != 100.0:
        st.warning("Supplier mix must sum to 100% before saving.")
    policy = load_delivery_policy()
    if policy:
        quantity = int(st.session_state.get(FIRM_WIDGET_KEYS['raw_material_order_qty'], 0))
        quote = sourcing_quote(quantity, _current_supplier_mix(), market_report.supply_risk,
                               market_report.round_number, selected_archetype.base_cost,
                               market_report.material_cost_index, policy)
        st.markdown('#### Supplier Quotes')
        st.caption(f'Supply risk: {market_report.supply_risk} | Prices reflect the current material-cost index.')
        _render_supplier_quotes(quote)
        material_cost = sum(row['material_cost'] for row in quote)
        fees = sum(row['order_fee'] for row in quote)
        cols = st.columns(4)
        cols[0].metric('New RM Order', f'{quantity:,} units')
        cols[1].metric('Material Purchase', f'${material_cost:,.2f}')
        cols[2].metric('Total Ordering Fee', f'${fees:,.0f}')
        cols[3].metric('Total Order Cash', f'${material_cost + fees:,.2f}')
        st.caption(ordering_fee_description(policy) + ' '
                   'Materials arrive separately by supplier. Reliable: at most 1 round late. '
                   'New orders cannot supply this round\'s production.')
        st.caption('End-of-round holding: raw materials USD 2/unit; finished paddles USD 6/unit. '
                   'In-transit orders have no warehouse holding charge.')
        return
    timing = _current_material_timing(market_report)
    timing_cols = st.columns([1.0, 1.0, 1.0, 2.2])
    order_qty = int(timing["order_qty"])
    if order_qty > 0:
        timing_cols[0].metric("This RM Order", f"{order_qty:,} units")
        timing_cols[1].metric("Est. Arrival If Ordered", f"Round {timing['arrival_round']}")
    else:
        timing_cols[0].metric("This RM Order", "0 units")
        timing_cols[1].metric("Est. Arrival If Ordered", "-")
    timing_cols[2].metric("Lead Time Used", f"{timing['lead_time_rounds']} round")
    timing_cols[3].caption(
        "New raw-material orders are for future production. In this deterministic version, "
        "a saved order arrives in its scheduled arrival round. "
        f"Current weighted lead time is {timing['adjusted_lead_time']:.2f} rounds "
        f"after supply risk ({market_report.supply_risk} x{timing['supply_risk_index']:.2f}). "
        "Base lead times: Economy 2.4, Standard 1.3, Reliable 0.9 rounds."
    )


def _launch_planning_lines(product_lines, projects, current_round, archetype):
    """Expose launch drafts without replacing persistent products before round execution."""
    context = st.session_state[SESSION_CONTEXT_KEY]
    backup_key = f"launch_plan_backups:{context}"
    backups = st.session_state.setdefault(backup_key, {})
    launches = [p for p in projects if p.launch_now and project_ready_at_round_start(p, current_round)]
    if len(launches) > 1:
        st.warning("Choose only one project to launch this round.")
        launches = []
    by_slot = {p.intended_slot_name: p for p in launches}
    original_defaults = {p.slot_name: p for p in _seed_product_decisions_for_round(
        product_lines[0].team_name, archetype, product_lines, current_round
    )} if product_lines else {}
    planning_lines = []
    for line in product_lines:
        slot = line.slot_name
        project = by_slot.get(slot)
        token = project.project_id + ':' + project.project_name if project else None
        previous = backups.get(slot)
        if previous and previous['token'] != token:
            for field, value in previous['values'].items():
                st.session_state[_product_widget_key(slot, field)] = value
            del backups[slot]
        if project:
            if slot not in backups:
                backups[slot] = {'token': token, 'values': {
                    field: st.session_state.get(_product_widget_key(slot, field))
                    for field in PRODUCT_FIELDS
                }}
                if (backups[slot]['values']['product_name'] == project.project_name
                        and line.product_name != project.project_name):
                    backups[slot]['values'] = {
                        field: getattr(original_defaults[slot], field) for field in PRODUCT_FIELDS
                    }
            for field, value in dict(product_name=project.project_name,
                                     target_segment=project.target_segment,
                                     is_active=True, retire_flag=False).items():
                st.session_state[_product_widget_key(slot, field)] = value
            planning_lines.append(replace(
                line, product_name=project.project_name, target_segment=project.target_segment,
                is_active=True, retirement_flag=False, retired_round=None,
                lifecycle_stage='launch', age_in_rounds=0,
                tech_generation=project.target_tech_generation, launch_round=current_round,
                inventory_units=0, backlog_units=0,
                material_design=project.target_segment,
            ))
        else:
            planning_lines.append(line)
    return planning_lines


def _render_product_profile(product_lines: list[ProductLine]) -> None:
    """Render the four product slots as compact rows."""
    st.markdown("### 4. Product Profile")
    st.caption(
        "Four product slots (A-D). New teams start with Beginner and Premium paddles; vacant slots require a development launch."
    )
    profile_widths = [2.3, 1.6, 0.9, 0.9, 1.0, 0.9, 0.95, 1.4]
    header_cols = st.columns(profile_widths)
    for column, label in zip(
        header_cols,
        [
            "Product Slot and State",
            "Segment",
            "Price",
            "Demand Forecast",
            "Production",
            "QC",
            "Target FG",
            "Controls",
        ],
    ):
        column.caption(label)

    line_by_slot = {line.slot_name: line for line in product_lines}
    segment_options = list(TARGET_SEGMENTS)
    for slot_name in PRODUCT_SLOT_NAMES:
        product_line = line_by_slot[slot_name]
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        lifecycle = product_line.lifecycle_stage.title()
        launch_draft = slot_name in st.session_state.get(
            f"launch_plan_backups:{st.session_state.get(SESSION_CONTEXT_KEY)}", {}
        )
        lifecycle_tone = (
            "green"
            if product_line.lifecycle_stage == "launch"
            else "amber"
            if product_line.lifecycle_stage == "decline"
            else "blue"
        )
        with st.container(border=True):
            row_cols = st.columns(profile_widths)
            with row_cols[0]:
                heading_suffix = " Retired / Empty" if is_retired_slot else ""
                st.markdown(
                    f'<div class="kiki-row-header">Product {slot_name}.{heading_suffix}</div>'
                    f'{_chip(lifecycle, lifecycle_tone)}'
                    f'{_chip(f"Age {product_line.age_in_rounds}")}'
                    f'{_chip(f"Gen {product_line.tech_generation}")}'
                    f'{_chip(f"FG {product_line.inventory_units:,}")}'
                    f'{_chip(f"Backlog {product_line.backlog_units:,}", "red" if product_line.backlog_units else "")}',
                    unsafe_allow_html=True,
                )
                if is_retired_slot:
                    st.caption(
                        "Vacant slot; launch a development project here."
                        if product_line.retired_round == 0 else
                        f"Retired after round {product_line.retired_round}; launch a project into this slot to replace it."
                    )
                st.text_input(
                    "Product Name",
                    key=_product_widget_key(slot_name, "product_name"),
                    disabled=is_retired_slot or launch_draft,
                    label_visibility="collapsed",
                )
            active_value = bool(
                st.session_state.get(
                    _product_widget_key(slot_name, "is_active"),
                    product_line.is_active,
                )
            )
            current_segment = str(
                st.session_state.get(
                    _product_widget_key(slot_name, "target_segment"),
                    product_line.target_segment,
                )
            )
            with row_cols[1]:
                st.selectbox(
                    "Target Segment",
                    options=segment_options,
                    index=_safe_option_index(segment_options, current_segment),
                    key=_product_widget_key(slot_name, "target_segment"),
                    disabled=is_retired_slot or launch_draft,
                    label_visibility="collapsed",
                )
            with row_cols[2]:
                st.number_input(
                    "Selling Price / Unit",
                    min_value=0.0,
                    step=1.0,
                    key=_product_widget_key(slot_name, "selling_price_per_unit"),
                    disabled=is_retired_slot,
                    label_visibility="collapsed",
                )
            with row_cols[3]:
                st.number_input(
                    "Demand Forecast",
                    min_value=0,
                    step=10,
                    key=_product_widget_key(slot_name, "forecast_units"),
                    disabled=is_retired_slot,
                    label_visibility="collapsed",
                )
            with row_cols[4]:
                st.number_input(
                    "Planned Production Units",
                    min_value=0,
                    step=10,
                    key=_product_widget_key(slot_name, "planned_production_units"),
                    disabled=is_retired_slot,
                    label_visibility="collapsed",
                )
            with row_cols[5]:
                st.number_input(
                    "QC Budget / Unit",
                    min_value=0.0,
                    step=0.25,
                    key=_product_widget_key(slot_name, "qc_budget_per_unit"),
                    disabled=is_retired_slot,
                    label_visibility="collapsed",
                )
            with row_cols[6]:
                st.number_input(
                    "Target FG Inventory",
                    min_value=0,
                    step=5,
                    key=_product_widget_key(slot_name, "target_finished_goods_inventory"),
                    disabled=is_retired_slot,
                    label_visibility="collapsed",
                )
            with row_cols[7]:
                st.checkbox(
                    "Active",
                    key=_product_widget_key(slot_name, "is_active"),
                    value=False if is_retired_slot else active_value,
                    disabled=is_retired_slot or launch_draft,
                    help=(
                        "Retired slots stay inactive until a development project launches into this slot."
                        if is_retired_slot
                        else None
                    ),
                )
                st.checkbox(
                    "Retire",
                    key=_product_widget_key(slot_name, "retire_flag"),
                    disabled=is_retired_slot or launch_draft,
                    help=(
                        "This slot has already been retired."
                        if is_retired_slot
                        else "If checked, the product sells through this round, then any remaining inventory is liquidated and the slot becomes inactive."
                    ),
                )


def _render_development_pipeline(
    team_name: str,
    current_round: int,
) -> None:
    """Render the two development-project slots below the product profile."""
    st.markdown("### 5. Development Pipeline")
    st.caption(
        "Project charter fields lock after work begins. Round controls remain adjustable: investment, testing, launch request, and cancellation."
    )
    existing_projects = load_product_development_projects(team_name=team_name)
    existing_project_by_slot = {project.project_slot_name: project for project in existing_projects}
    project_columns = st.columns(len(PROJECT_SLOT_NAMES))
    segment_options = list(TARGET_SEGMENTS)
    slot_options = list(PRODUCT_SLOT_NAMES)

    for project_column, project_slot_name in zip(project_columns, PROJECT_SLOT_NAMES):
        project = existing_project_by_slot[project_slot_name]
        fixed_settings_locked = _project_fixed_settings_locked(project)
        if fixed_settings_locked:
            _sync_locked_project_fields(project)
        with project_column:
            with st.container(border=True):
                status_tone = (
                    "green"
                    if project.status == "launch_ready"
                    else "amber"
                    if project.status in {"concept", "development", "pilot"}
                    else ""
                )
                last_launch_label = project.launched_round or "-"
                st.markdown(
                    f'<div class="kiki-row-header">Project {project_slot_name}</div>'
                    f'{_chip(project.status.replace("_", " ").title(), status_tone)}'
                    f'{_chip(f"Invested ${project.cumulative_investment:,.0f}")}'
                    f'{_chip(f"Readiness {project.launch_readiness_score:.1f}%")}'
                    f'{_chip(f"Earliest R{project.earliest_launch_round}")}'
                    f'{_chip(f"Last {last_launch_label}")}',
                    unsafe_allow_html=True,
                )
                top_cols = st.columns([1.55, 1.0, 0.85, 0.8])
                top_cols[0].text_input(
                    "Project Name",
                    key=_project_widget_key(project_slot_name, "project_name"),
                    disabled=fixed_settings_locked,
                )
                current_segment = str(
                    st.session_state.get(
                        _project_widget_key(project_slot_name, "target_segment"),
                        project.target_segment,
                    )
                )
                top_cols[1].selectbox(
                    "Target Segment",
                    options=segment_options,
                    index=_safe_option_index(segment_options, current_segment),
                    key=_project_widget_key(project_slot_name, "target_segment"),
                    disabled=fixed_settings_locked,
                )
                top_cols[2].number_input(
                    "Tech Gen",
                    min_value=MIN_TECH_GENERATION,
                    max_value=MAX_TECH_GENERATION,
                    step=1,
                    key=_project_widget_key(project_slot_name, "target_tech_generation"),
                    disabled=fixed_settings_locked,
                )
                current_slot = str(
                    st.session_state.get(
                        _project_widget_key(project_slot_name, "intended_slot_name"),
                        project.intended_slot_name,
                    )
                )
                top_cols[3].selectbox(
                    "Slot",
                    options=slot_options,
                    index=_safe_option_index(slot_options, current_slot),
                    key=_project_widget_key(project_slot_name, "intended_slot_name"),
                    disabled=fixed_settings_locked,
                )

                mid_cols = st.columns(4)
                mid_cols[0].number_input(
                    "Launch Round",
                    min_value=min(current_round, int(project.planned_launch_round)),
                    step=1,
                    key=_project_widget_key(project_slot_name, "planned_launch_round"),
                    disabled=fixed_settings_locked,
                )
                mid_cols[1].text_input(
                    "Cannibalization",
                    key=_project_widget_key(project_slot_name, "cannibalization_group"),
                    disabled=fixed_settings_locked,
                )
                mid_cols[2].number_input(
                    "Defect Mod.",
                    step=0.002,
                    key=_project_widget_key(project_slot_name, "projected_base_defect_modifier"),
                    disabled=fixed_settings_locked,
                )
                mid_cols[3].number_input(
                    "Demand Fit",
                    min_value=0.1,
                    step=0.05,
                    key=_project_widget_key(project_slot_name, "projected_demand_fit_modifier"),
                    disabled=fixed_settings_locked,
                )

                control_cols = st.columns([1.0, 1.0, 0.9, 0.85])
                control_cols[0].number_input(
                    "Investment",
                    min_value=0.0,
                    step=250.0,
                    key=_project_widget_key(project_slot_name, "investment_this_round"),
                )
                control_cols[1].slider(
                    "Testing",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    key=_project_widget_key(project_slot_name, "testing_intensity"),
                )
                control_cols[2].checkbox(
                    "Launch Now",
                    key=_project_widget_key(project_slot_name, "launch_now"),
                )
                control_cols[3].checkbox(
                    "Cancel",
                    key=_project_widget_key(project_slot_name, "cancel_now"),
                )


def _render_material_plan(preview, firm_decision):
    st.markdown("#### Shared Raw-Material Plan")
    st.caption("One shared RM inventory. Material design is fixed at product creation or launch; target-market changes do not change it.")
    rows = []
    for row in preview.material_rows:
        rows.append(
            '<tr><td>' + escape(str(row['Product']))
            + '<small>Slot ' + escape(str(row['Slot'])) + ' / ' + escape(str(row['Material Design']))
            + ' design</small></td>'
            + f'<td data-label="Planned paddles">{row["Planned Paddles"]:,}</td>'
            + f'<td data-label="RM / paddle">{row["RM / Paddle"]:.2f}</td>'
            + f'<td data-label="RM required">{row["RM Required"]:,.2f}</td>'
            + f'<td data-label="Material value">${row["Planned Material Value"]:,.2f}</td></tr>'
        )
    if rows:
        st.html('''<style>
        .kiki-material-plan{width:100%;border-collapse:collapse;table-layout:fixed;font-size:14px}
        .kiki-material-plan th,.kiki-material-plan td{padding:10px 8px;text-align:right;border-bottom:1px solid #d5d9e0;vertical-align:middle;overflow-wrap:anywhere}
        .kiki-material-plan th{font-size:12px;font-weight:500}
        .kiki-material-plan th:first-child,.kiki-material-plan td:first-child{text-align:left;width:30%;padding-left:0}
        .kiki-material-plan small{display:block;font-size:12px;margin-top:4px}
        .kiki-material-plan td{font-variant-numeric:tabular-nums}
        @media(max-width:640px){.kiki-material-plan,.kiki-material-plan tbody,.kiki-material-plan tr{display:block;width:100%}
        .kiki-material-plan thead{display:none}.kiki-material-plan tr{border-bottom:1px solid #d5d9e0;padding:8px 0}
        .kiki-material-plan td{display:flex;justify-content:space-between;gap:12px;border:0;padding:5px 0}
        .kiki-material-plan td:first-child{display:block;width:100%;font-weight:600}
        .kiki-material-plan td[data-label]:before{content:attr(data-label);font-size:12px;text-align:left}}
        </style><table class="kiki-material-plan" aria-label="Shared raw material requirements"><thead><tr>
        <th>Product / design</th><th>Planned paddles</th><th>RM / paddle</th><th>RM required</th><th>Material value</th>
        </tr></thead><tbody>''' + ''.join(rows) + '</tbody></table>')
    columns = st.columns(4)
    required = preview.total_material_required
    gap = round(preview.raw_material_units_available - required, 2)
    columns[0].metric("Required RM", f"{required:,.2f}")
    columns[1].metric("Available RM", f"{preview.raw_material_units_available:,.2f}")
    columns[2].metric("RM Shortage" if gap < 0 else "RM Remaining", f"{abs(gap):,.2f}")
    columns[3].metric("Planned Material Value", f"${required * preview.weighted_material_unit_cost:,.2f}")
    st.caption(
        f"Current quote: USD {preview.weighted_material_unit_cost:,.2f} / standard RM unit. "
        f"New order: {firm_decision.raw_material_order_qty:,} RM; "
        f"total order cash: USD {preview.projected_procurement_cost:,.2f} "
        f"(includes USD {preview.projected_ordering_cost:,.2f} in order fees). "
        "Planned material value is an estimate at this quote, not an additional cash charge. "
        "Conversion, QC and other costs are separate."
    )
    if gap < 0:
        st.warning(f"This plan needs {abs(gap):,.2f} more RM than is available this round. New orders arrive in future rounds.")


def _render_preview(
    candidate_firm_decision: TeamDecision,
    candidate_projects: list[ProductDevelopmentProject],
    current_round: int,
    preview,
) -> None:
    """Render compact Stage C portfolio, forecast, and finance analytics."""
    total_planned = preview.total_planned_production_units
    total_forecast = preview.total_forecast_units
    planned_utilization = (
        (total_planned / preview.effective_capacity_units) * 100.0
        if preview.effective_capacity_units > 0
        else 0.0
    )
    raw_material_gap = preview.raw_material_units_available - preview.total_material_required

    row_one = st.columns(5)
    row_one[0].metric("Forecast", f"{total_forecast:,}")
    row_one[1].metric("Planned Production", f"{total_planned:,}")
    row_one[2].metric("Effective Capacity", f"{preview.effective_capacity_units:,}")
    row_one[3].metric("Feasible Output", f"{preview.projected_max_feasible_production:,}")
    row_one[4].metric("Utilization", f"{planned_utilization:.1f}%")

    row_two = st.columns(5)
    row_two[0].metric("Forecast Gap", f"{preview.forecast_production_gap_units:+,}")
    row_two[1].metric("RM Gap", f"{raw_material_gap:+,.2f}")
    row_two[2].metric("Defect Rate", f"{preview.projected_weighted_defect_rate:.2%}")
    row_two[3].metric("Margin / Unit", f"${preview.projected_weighted_margin_per_unit:,.2f}")
    row_two[4].metric("Likely Borrowing", f"${preview.projected_likely_borrowing_need:,.0f}")

    row_three = st.columns(5)
    row_three[0].metric("Working Capital", f"${preview.projected_working_capital_requirement:,.0f}")
    row_three[1].metric("Cash Before Borrowing", f"${preview.projected_ending_cash_before_borrowing:,.0f}")
    row_three[2].metric("Planned Borrowing", f"${candidate_firm_decision.planned_borrowing_amount:,.0f}")
    launch_requests = [
        project for project in candidate_projects if project.is_defined() and project.launch_now
    ]
    if launch_requests:
        launch_gate_ready_count = sum(
            1
            for project in launch_requests
            if project_ready_at_round_start(project, current_round)
        )
        row_three[3].metric(
            "Launch Requests Ready",
            f"{launch_gate_ready_count}/{len(launch_requests)}",
        )
    else:
        row_three[3].metric("Launch-Ready Projects", f"{preview.launch_ready_project_count}")
    row_three[4].metric("Products in Decline", f"{preview.decline_product_count}")

    st.caption(
        f"Weighted supplier mix: {preview.weighted_supplier_mix_text} | "
        f"Projected portfolio segment mix: {preview.segment_mix_summary} | "
        + ("Supplier-specific delivery windows | " if load_delivery_policy() else
           f"Weighted lead time: {preview.weighted_lead_time:.2f} rounds | ")
        + f"Projected innovation spend: ${preview.projected_innovation_investment:,.0f} | "
        f"Max backorder units: {candidate_firm_decision.max_backorder_units:,}"
    )

    for warning_message in preview.warnings:
        st.warning(warning_message)

    product_preview_frame = pd.DataFrame(preview.product_rows)
    if not product_preview_frame.empty:
        with st.expander("Portfolio scenario preview", expanded=False):
            st.dataframe(product_preview_frame, use_container_width=True, hide_index=True)

    project_preview_frame = pd.DataFrame(preview.project_rows)
    if not project_preview_frame.empty:
        preferred_columns = [
            "project_slot_name",
            "project_name",
            "status",
            "target_segment",
            "target_tech_generation",
            "intended_slot_name",
            "estimated_cost_range",
            "remaining_investment_after_this_round",
            "funding_progress_pct",
            "projected_readiness_after_this_round",
            "readiness_gap_points",
            "funding_gate_met",
            "readiness_gate_met",
            "timing_gate_met",
            "launch_gate_met",
            "testing_adequacy",
            "launch_risk",
            "launch_blockers",
            "minimum_development_rounds",
            "expected_launch_round",
            "planned_launch_round",
            "launch_now",
        ]
        visible_columns = [
            column for column in preferred_columns if column in project_preview_frame.columns
        ]
        with st.expander("Development pipeline estimate preview", expanded=False):
            st.caption(
                "Estimated cost, remaining funding, readiness, launch timing, and launch risk before saving."
            )
            st.dataframe(
                project_preview_frame[visible_columns],
                use_container_width=True,
                hide_index=True,
            )


def _render_project_launch_gate_guidance(
    candidate_projects: list[ProductDevelopmentProject],
    current_round: int,
) -> None:
    """Show a plain-language launch checklist for active development projects."""
    rows: list[dict[str, object]] = []
    for project in candidate_projects:
        if not project.is_defined() or project.status in {"launched", "canceled"}:
            continue
        estimate = estimate_development_project(
            project,
            include_current_round_investment=True,
            current_round=current_round,
        )
        rows.append(
            {
                "project": f"{project.project_slot_name}: {project.project_name}",
                "funding_gate": "Pass" if estimate.get("funding_gate_met") else "Not yet",
                "Testing Cost": estimate.get("testing_cost_this_round", 0.0),
                "Testing Coverage": f"{estimate.get('cumulative_testing_after_this_round', 0.0):.0%}",
                "readiness_gate": "Pass" if estimate.get("readiness_gate_met") else "Not yet",
                "timing_gate": "Pass" if estimate.get("timing_gate_met") else "Not yet",
                "can_launch_now": "Yes" if project_ready_at_round_start(project, current_round) else "No",
                "funding_progress_pct": estimate.get("funding_progress_pct", 0.0),
                "readiness_after_this_round": estimate.get(
                    "projected_readiness_after_this_round",
                    0.0,
                ),
                "readiness_needed": estimate.get("readiness_threshold", 0.0),
                "what_to_do_next": estimate.get("launch_blockers", ""),
            }
        )

    if not rows:
        return

    st.markdown("#### Launch Gate Checklist")
    st.caption(
        "Testing accumulates up to 100% coverage. Two rounds at 0.5 cost $500 each; one round at 1.0 costs $2,000. "
        "Both achieve the same coverage, but spreading tests takes longer. Set testing to 0 after full coverage to avoid unnecessary costs. "
        "Testing costs are included in development spending and do not count toward project funding. "
        "A project can launch only when all three gates pass: funding, readiness, and timing. "
        "Can Launch Now uses development completed before this round. Select Launch Now, then set the new product's price, demand forecast and production before saving."
    )
    launch_gate_frame = pd.DataFrame(rows).rename(
        columns={
            "project": "Project",
            "funding_gate": "Funding",
            "readiness_gate": "Readiness",
            "timing_gate": "Timing",
            "can_launch_now": "Can Launch Now",
            "funding_progress_pct": "Funding %",
            "readiness_after_this_round": "Readiness After This Round",
            "readiness_needed": "Readiness Needed",
            "what_to_do_next": "Next Step",
        }
    )
    st.dataframe(launch_gate_frame, width="stretch", hide_index=True)


def _validation_messages(
    candidate_firm_decision: TeamDecision,
    candidate_product_decisions: list[ProductDecision],
    candidate_projects: list[ProductDevelopmentProject],
    current_round: int,
) -> list[str]:
    """Build save-time validation messages."""
    messages: list[str] = []
    if not candidate_firm_decision.team_name:
        messages.append("Team name is required before you can save.")
    if not candidate_firm_decision.supplier_mix_valid():
        messages.append("Supplier mix percentages must sum to 100 before saving.")
    if not any(item.is_active for item in candidate_product_decisions) and not any(
        item.launch_now for item in candidate_projects if item.is_defined()
    ):
        messages.append("Keep at least one active product or request at least one project launch.")

    for decision in candidate_product_decisions:
        if not decision.product_name.strip():
            messages.append(f"Product {decision.slot_name} must have a name.")
        if decision.target_segment not in TARGET_SEGMENTS:
            messages.append(f"Product {decision.slot_name} has an invalid target segment.")
        if decision.is_active and decision.selling_price_per_unit <= 0:
            messages.append(f"Product {decision.slot_name} needs a positive selling price.")
        if decision.is_active and decision.forecast_units <= 0:
            messages.append(f"Product {decision.slot_name} needs a demand forecast before saving.")

    launch_requests = 0
    for project in candidate_projects:
        project_controls_used = (
            project.investment_this_round > 0
            or project.testing_intensity > 0
            or project.launch_now
            or project.cancel_now
        )
        if not project.project_name.strip():
            if project_controls_used:
                messages.append(
                    f"Project {project.project_slot_name} needs a project name before investment, testing, launch, or cancellation controls can be used."
                )
            continue
        if project.target_segment not in TARGET_SEGMENTS:
            messages.append(f"Project {project.project_slot_name} has an invalid target segment.")
        if project.planned_launch_round < project.created_round:
            messages.append(
                f"Project {project.project_slot_name} cannot have a planned launch round earlier than the project creation round."
            )
        if not 0.0 <= project.testing_intensity <= 1.0:
            messages.append(f"Project {project.project_slot_name} testing intensity must stay between 0.0 and 1.0.")
        if project.target_tech_generation < MIN_TECH_GENERATION or project.target_tech_generation > MAX_TECH_GENERATION:
            messages.append(f"Project {project.project_slot_name} tech generation must stay between {MIN_TECH_GENERATION} and {MAX_TECH_GENERATION}.")
        if project.projected_demand_fit_modifier <= 0:
            messages.append(f"Project {project.project_slot_name} demand-fit modifier must be positive.")
        if project.launch_now:
            launch_requests += 1
            if not project_ready_at_round_start(project, current_round):
                messages.append(f"Project {project.project_slot_name} must finish development before this round to launch now.")

    if launch_requests > 1:
        messages.append("Only one launch request per team is allowed per round.")

    return messages


def _save_stage_b_submission(
    candidate_firm_decision: TeamDecision,
    candidate_product_decisions: list[ProductDecision],
    candidate_projects: list[ProductDevelopmentProject],
    product_lines: list[ProductLine],
    current_round: int,
    submitted_by_user_id: str,
) -> str:
    """Persist the firm, product, forecast, pipeline, and product-line submission."""
    from utils.decision_audit import save_audited_submission
    launch_slots = {p.intended_slot_name for p in candidate_projects if p.launch_now}
    original_by_slot = {p.slot_name: p for p in product_lines}
    merged_lines = [original_by_slot[p.slot_name] if p.slot_name in launch_slots else p
                    for p in _merge_product_lines(product_lines, candidate_product_decisions)]
    import sqlite3
    try:
        save_audited_submission(candidate_firm_decision, candidate_product_decisions, candidate_projects,
                               merged_lines, current_round, submitted_by_user_id)
    except (PermissionError, ValueError, sqlite3.Error, OSError):
        st.error("Your decision was not saved. The previous saved plan is unchanged. Please retry or contact your instructor.")
        st.stop()
    return (
        f"Saved the Stage C portfolio, forecast, and pipeline submission for "
        f"`{candidate_firm_decision.team_name}` in round `{current_round}`."
    )


@st.dialog("Kiki found unfinished checks")
def _render_kiki_submit_warning_dialog(
    warning_messages: list[str],
    candidate_firm_decision: TeamDecision,
    candidate_product_decisions: list[ProductDecision],
    candidate_projects: list[ProductDevelopmentProject],
    product_lines: list[ProductLine],
    current_round: int,
    submitted_by_user_id: str,
) -> None:
    """Ask students to confirm before saving a plan with soft OM warnings."""
    header_cols = st.columns([0.25, 0.75])
    mascot_path = KIKI_CHECKLIST_MASCOT_DIR / "service_qc_cash_kiki.png"
    if mascot_path.exists():
        header_cols[0].image(str(mascot_path), width=78)
    header_cols[1].markdown("### Review before submit")
    header_cols[1].caption(
        "These are soft OM warnings. Hard validation errors still block saving."
    )

    st.error(f"Kiki found {len(warning_messages)} unfinished check(s).")
    for message in warning_messages:
        st.markdown(f"- {message}")

    action_cols = st.columns(2)
    if action_cols[0].button("Go Back and Fix", key="stage_b_submit_warning_fix"):
        _clear_submit_warning_state()
        st.rerun()
    if action_cols[1].button(
        "Submit Anyway",
        type="primary",
        key="stage_b_submit_warning_confirm",
    ):
        st.session_state[SUBMIT_SUCCESS_MESSAGE_KEY] = _save_stage_b_submission(
            candidate_firm_decision,
            candidate_product_decisions,
            candidate_projects,
            product_lines,
            current_round,
            submitted_by_user_id,
        )
        _clear_submit_warning_state()
        st.rerun()


def main() -> None:
    """Render the Stage B team decision editor."""
    ensure_app_storage()
    user = require_authenticated_user()
    _inject_compact_decision_css()

    st.title("Team Decisions")
    st.caption(
        "Set firm controls, compare Product A-D, manage development projects, and check the live planning preview before saving."
    )

    market_report = planning_market_report(load_market_report())
    st.caption("Planning previews use the public demand outlook midpoint, not actual market demand. Final results depend on competitors and the instructor's committed market demand.")
    current_round = market_report.round_number
    round_status = load_round_status(current_round)
    team_states = load_team_states()
    state_lookup = {item.team_name.lower(): item for item in team_states}
    current_round_firm_decisions = load_team_decisions(round_number=current_round)
    current_round_product_decisions = load_product_decisions(round_number=current_round)
    current_round_projects = load_product_development_projects()
    archetypes = load_team_archetypes()
    archetype_lookup = {item.name: item for item in archetypes}
    archetype_names = list(archetype_lookup)

    st.caption(
        "The preview uses the current market report, your persistent portfolio state, saved round submissions, and your current forecast-vs-plan inputs."
    )
    if round_status.submissions_open:
        st.success(f"Round {current_round} submissions are open.")
    else:
        st.warning(
            f"Round {current_round} submissions are closed. Team leaders can review their plan, but cannot save changes unless the instructor reopens the round."
        )

    st.markdown("### 1. Team Setup")
    identity_cols = st.columns([1.25, 1.35, 0.9, 1.05])
    if user.role == "team_leader":
        if not user.team_name:
            st.error("Your account does not have a team assignment yet.")
            st.stop()
        team_name = user.team_name
        identity_cols[0].text_input("Team Name", value=team_name, disabled=True)
    else:
        team_options = _build_team_options(current_round)
        if team_options:
            team_name = identity_cols[0].selectbox("Team", options=team_options)
        else:
            team_name = identity_cols[0].text_input("Team Name", placeholder="Team Alpha")

    team_name_key = team_name.strip().lower()
    if not team_name_key:
        st.info("Select or enter a team to start editing the portfolio.")
        st.stop()

    existing_state = state_lookup.get(team_name_key)
    existing_firm_decision = load_team_decision(current_round, team_name)
    default_archetype_name = (
        existing_firm_decision.archetype
        if existing_firm_decision
        else (
            existing_state.archetype
            if existing_state and existing_state.archetype in archetype_lookup
            else archetype_names[0]
        )
    )

    product_lines = ensure_product_lines_for_team(team_name, default_archetype_name)
    saved_product_decisions = load_product_decisions(round_number=current_round, team_name=team_name)
    saved_projects = ensure_development_projects_for_team(team_name)

    current_context = f"{current_round}:{team_name_key}"
    if (
        st.session_state.get(SESSION_CONTEXT_KEY) != current_context
        or _decision_widgets_look_unseeded(product_lines)
    ):
        previous_firm_decision = _latest_previous_firm_decision(current_round, team_name)
        seed_firm_decision = (
            existing_firm_decision
            if existing_firm_decision is not None
            else previous_firm_decision
            if previous_firm_decision is not None
            else _suggested_firm_decision(team_name, archetype_lookup[default_archetype_name])
        )
        seed_product_decisions = (
            saved_product_decisions
            if saved_product_decisions
            else _seed_product_decisions_for_round(
                team_name,
                archetype_lookup[default_archetype_name],
                product_lines,
                current_round,
            )
        )
        seed_projects = saved_projects if saved_projects else _seed_projects(team_name, current_round)
        # This is safe here because the archetype widget has not been created
        # yet in this page run. Button callbacks below must not mutate it.
        st.session_state[ARCHETYPE_KEY] = seed_firm_decision.archetype
        _load_decisions_into_session(seed_firm_decision, seed_product_decisions, seed_projects)
        st.session_state[SESSION_CONTEXT_KEY] = current_context

    selected_archetype_name = default_archetype_name
    st.session_state[ARCHETYPE_KEY] = selected_archetype_name
    identity_cols[1].text_input("Operating baseline", value=selected_archetype_name, disabled=True)
    selected_archetype = archetype_lookup[selected_archetype_name]

    if identity_cols[2].button("Apply Suggestions"):
        _load_decisions_into_session(
            _suggested_firm_decision(team_name, selected_archetype),
            _suggested_product_decisions(team_name, selected_archetype, product_lines),
            saved_projects,
        )
        st.rerun()
    if identity_cols[3].button(
        "Load Saved Round",
        disabled=not (saved_product_decisions and existing_firm_decision),
    ):
        _load_decisions_into_session(
            existing_firm_decision,
            saved_product_decisions,
            saved_projects,
        )
        st.rerun()

    st.markdown("### 2. Current Team State")
    _render_state_snapshot(product_lines, existing_state, market_report, selected_archetype)
    st.caption(
        f"Market generation is currently Gen {market_report.current_market_generation}. "
        f"Premium tech adoption is {market_report.premium_tech_adoption:.0%} and mid-market tech adoption is {market_report.mid_market_tech_adoption:.0%}."
    )

    _render_firm_controls(market_report, selected_archetype)
    planning_projects = _current_projects(team_name, current_round, saved_projects)
    for project in planning_projects:
        if project_ready_at_round_start(project, current_round) and not project.launch_now:
            if st.button(
                f"Launch {project.project_name} in Product {project.intended_slot_name}",
                key=f"plan_launch_{current_context}_{project.project_slot_name}",
                disabled=any(p.launch_now for p in planning_projects),
            ):
                st.session_state[_project_widget_key(project.project_slot_name, 'launch_now')] = True
                st.rerun()
    planning_lines = _launch_planning_lines(product_lines, planning_projects, current_round, selected_archetype)
    _render_product_profile(planning_lines)
    material_plan_container = st.container()
    _render_development_pipeline(team_name, current_round)

    candidate_firm_decision = _current_firm_decision(team_name, selected_archetype_name)
    candidate_product_decisions = _current_product_decisions(team_name, planning_lines)
    candidate_projects = _current_projects(team_name, current_round, saved_projects)
    _render_project_launch_gate_guidance(candidate_projects, current_round)
    preview = preview_team_decision(
        market_report=market_report,
        candidate_team_decision=candidate_firm_decision,
        candidate_product_decisions=candidate_product_decisions,
        candidate_projects=candidate_projects,
        product_lines=load_product_lines(),
        current_round_team_decisions=current_round_firm_decisions,
        current_round_product_decisions=current_round_product_decisions,
        current_round_projects=current_round_projects,
        existing_states=team_states,
    )

    with material_plan_container:
        _render_material_plan(preview, candidate_firm_decision)

    st.markdown("### 6. Planning Analytics Preview")
    _render_preview(candidate_firm_decision, candidate_projects, current_round, preview)

    st.markdown("### 7. Pre-Submit Check")
    kiki_submit_sections = _build_kiki_submit_checklist(
        candidate_firm_decision,
        candidate_product_decisions,
        candidate_projects,
        preview,
        current_round,
    )
    kiki_warning_messages = _kiki_submit_warning_messages(kiki_submit_sections)
    pending_warning_messages = st.session_state.get(SUBMIT_WARNING_MESSAGES_KEY, [])
    pending_warning_context = st.session_state.get(SUBMIT_WARNING_CONTEXT_KEY)
    pending_warning_active = (
        pending_warning_context == current_context
        and pending_warning_messages == kiki_warning_messages
        and bool(kiki_warning_messages)
    )
    if pending_warning_messages and not pending_warning_active:
        _clear_submit_warning_state()
        pending_warning_active = False
    _render_kiki_submit_checklist(kiki_submit_sections)

    success_message = st.session_state.pop(SUBMIT_SUCCESS_MESSAGE_KEY, None)
    if success_message:
        st.success(success_message)

    if pending_warning_active:
        _render_kiki_submit_warning_dialog(
            warning_messages=kiki_warning_messages,
            candidate_firm_decision=candidate_firm_decision,
            candidate_product_decisions=candidate_product_decisions,
            candidate_projects=candidate_projects,
            product_lines=product_lines,
            current_round=current_round,
            submitted_by_user_id=user.user_id,
        )

    save_col, note_col = st.columns([1, 2])
    save_disabled = user.role == "team_leader" and not round_status.submissions_open
    if save_col.button(
        "Save Portfolio and Pipeline Decision",
        type="primary",
        disabled=save_disabled or pending_warning_active,
    ):
        if user.role == "team_leader" and not round_status.submissions_open:
            st.error("Submissions are closed for this round.")
            st.stop()
        errors = _validation_messages(
            candidate_firm_decision,
            candidate_product_decisions,
            candidate_projects,
            current_round,
        )
        if errors:
            for error_message in errors:
                st.error(error_message)
            _clear_submit_warning_state()
        elif kiki_warning_messages:
            st.session_state[SUBMIT_WARNING_CONTEXT_KEY] = current_context
            st.session_state[SUBMIT_WARNING_MESSAGES_KEY] = kiki_warning_messages
            st.rerun()
        else:
            st.success(
                _save_stage_b_submission(
                    candidate_firm_decision,
                    candidate_product_decisions,
                    candidate_projects,
                    product_lines,
                    current_round,
                    user.user_id,
                )
            )

    note_col.caption(
        "Firm-level decisions remain shared across the business, while product-slot forecasts, portfolio decisions, and development projects let teams balance S&OP discipline, cash pressure, and future launches."
    )


main()
