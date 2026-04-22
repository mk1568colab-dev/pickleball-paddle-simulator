"""Page for capturing team decisions."""

from __future__ import annotations

import streamlit as st

from models.schemas import TeamDecision
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_market_report,
    load_team_decision,
    load_team_archetypes,
    save_team_decision,
)


def main() -> None:
    """Render the team decision entry page."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Team Decisions")
    st.caption("Capture the current round's operations decision submission.")

    market_report = load_market_report()
    current_round = market_report.round_number
    archetypes = load_team_archetypes()
    archetype_lookup = {item.name: item for item in archetypes}
    archetype_names = [archetype.name for archetype in archetypes]

    if user.role == "team_leader":
        if not user.team_name:
            st.error("Your account does not have a team assignment yet.")
            st.stop()
        team_name = user.team_name
        st.info(f"Submitting for `{team_name}` in round `{current_round}`.")
    else:
        team_name = ""
        st.info(
            "As admin, you can enter or revise the current round decision for any team."
        )

    existing_decision = (
        load_team_decision(current_round, team_name) if team_name else None
    )
    default_archetype_name = (
        existing_decision.archetype
        if existing_decision and existing_decision.archetype in archetype_lookup
        else archetype_names[0]
    )
    default_archetype = archetype_lookup[default_archetype_name]

    with st.form("team_decision_form"):
        if user.role == "team_leader":
            st.text_input("Team Name", value=team_name, disabled=True)
        else:
            team_name = st.text_input("Team Name", placeholder="Team Alpha")

        selected_archetype = st.selectbox(
            "Archetype",
            options=archetype_names,
            index=archetype_names.index(default_archetype_name),
        )
        selected_archetype_record = archetype_lookup[selected_archetype]

        col_1, col_2 = st.columns(2)
        with col_1:
            price_level = st.selectbox(
                "Price Level",
                options=["Beginner", "Mid", "Premium"],
                index=["Beginner", "Mid", "Premium"].index(
                    existing_decision.price_level
                    if existing_decision
                    else selected_archetype_record.default_price_level
                ),
            )
            production_quantity = st.number_input(
                "Production Quantity",
                min_value=0,
                step=25,
                value=(
                    existing_decision.production_quantity
                    if existing_decision
                    else max(int(market_report.total_demand / 4), 0)
                ),
            )
        with col_2:
            capacity_plan = st.selectbox(
                "Capacity Plan",
                options=["Reduce", "Maintain", "Expand", "Selective Expansion"],
                index=["Reduce", "Maintain", "Expand", "Selective Expansion"].index(
                    existing_decision.capacity_plan
                    if existing_decision
                    else selected_archetype_record.default_capacity_plan
                ),
            )
            quality_level = st.selectbox(
                "Quality Level",
                options=["Basic", "Standard", "High"],
                index=["Basic", "Standard", "High"].index(
                    existing_decision.quality_level
                    if existing_decision
                    else selected_archetype_record.default_quality_level
                ),
            )

        inventory_posture = st.selectbox(
            "Inventory Posture",
            options=["Lean", "Balanced", "Build"],
            index=["Lean", "Balanced", "Build"].index(
                existing_decision.inventory_posture
                if existing_decision
                else selected_archetype_record.default_inventory_posture
            ),
        )

        submitted = st.form_submit_button("Save Team Decision", type="primary")

    if submitted:
        if not team_name.strip():
            st.error("Enter a team name before saving.")
            return

        decision = TeamDecision(
            team_name=team_name.strip(),
            archetype=selected_archetype_record.name,
            price_level=price_level,
            production_quantity=int(production_quantity),
            capacity_plan=capacity_plan,
            quality_level=quality_level,
            inventory_posture=inventory_posture,
        )
        save_team_decision(
            decision=decision,
            round_number=current_round,
            submitted_by_user_id=user.user_id,
        )

        st.success(f"Decision saved for `{decision.team_name}` in round `{current_round}`.")
        st.json(decision.to_dict())


main()
