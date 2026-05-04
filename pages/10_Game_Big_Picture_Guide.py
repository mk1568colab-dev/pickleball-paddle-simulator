"""Student-facing visual guide using the polished classroom infographic files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage


ROOT_DIR = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT_DIR / "documentation" / "figures" / "game_big_picture"


@dataclass(frozen=True)
class GuideFigure:
    """Metadata for one big-picture teaching figure."""

    title: str
    file_name: str
    caption: str
    student_takeaway: str


FIGURES: list[GuideFigure] = [
    GuideFigure(
        title="Figure 1. The Round Loop",
        file_name="Figure_1_The_Round_Loop.png",
        caption="Shows the repeated classroom rhythm: read the market, decide, run the engine, review results, and adjust.",
        student_takeaway="Every round is a learning cycle. Your team should use prior results to improve the next decision.",
    ),
    GuideFigure(
        title="Figure 2. What Students Control",
        file_name="Figure_2_What_Students_Control.png",
        caption="Maps the major decision areas students control across demand, operations, supply, portfolio, pipeline, and finance.",
        student_takeaway="Strong teams make decisions that fit together instead of optimizing one input in isolation.",
    ),
    GuideFigure(
        title="Figure 3. Portfolio and Pipeline",
        file_name="Figure_3_Portfolio_and_Pipeline.png",
        caption="Explains the difference between active Product A/B/C slots and future Project P1/P2 development work.",
        student_takeaway="You are managing today's products and tomorrow's replacement products at the same time.",
    ),
    GuideFigure(
        title="Figure 4. How Demand Is Allocated",
        file_name="Figure_4_Demand_Allocation_Infographic.png",
        caption="Shows how segment demand is distributed to products based on attractiveness, price, quality, service, technology, lifecycle, and reputation.",
        student_takeaway="Demand is competitive. Better product fit and execution earn a larger share of the market.",
    ),
    GuideFigure(
        title="Figure 5. Operations and Cost Engine",
        file_name="Figure_5_Operations_and_Cost_Engine.png",
        caption="Connects capacity, materials, production, defects, good units, sales service, and cost buckets.",
        student_takeaway="Operations decisions become cost, service, inventory, and profit outcomes.",
    ),
    GuideFigure(
        title="Figure 6. Forecasting and S&OP",
        file_name="Figure_6_Forecasting_and_SOP.png",
        caption="Shows how product forecasts discipline production, material, capacity, and cash planning.",
        student_takeaway="Forecasts do not create demand, but they help your team plan realistically and avoid self-inflicted problems.",
    ),
    GuideFigure(
        title="Figure 7. Cash and Debt Pressure",
        file_name="Figure_7_Cash_and_Debt_Pressure.png",
        caption="Explains the cash bridge from starting cash through revenue, costs, investment, interest, and borrowing.",
        student_takeaway="Profit and cash are related but not identical. A team can sell well and still get squeezed by debt or working capital.",
    ),
    GuideFigure(
        title="Figure 8. Strategy Archetypes",
        file_name="Figure_8_Strategy_Archetypes.png",
        caption="Compares the six classroom strategy archetypes and the environments where each can perform well.",
        student_takeaway="There is no permanent winning strategy. The best approach depends on the market environment and scoring priorities.",
    ),
]


def _render_page_styles() -> None:
    """Keep image sections clean without recreating the figures in HTML."""
    st.markdown(
        """
        <style>
        .big-picture-intro {
            background: #fff7ed;
            border: 1px solid #fed7aa;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin: 0.75rem 0 1.25rem 0;
        }
        .figure-caption {
            color: #64748b;
            font-size: 0.95rem;
            margin-bottom: 0.75rem;
        }
        .takeaway {
            background: #f8fafc;
            border-left: 5px solid #ef4444;
            border-radius: 10px;
            padding: 0.75rem 0.9rem;
            margin-top: 0.85rem;
            color: #334155;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_figure(figure: GuideFigure) -> None:
    """Render one existing PNG infographic with a compact explanation."""
    figure_path = FIGURE_DIR / figure.file_name

    with st.container(border=True):
        st.markdown(f"### {figure.title}")
        st.markdown(
            f'<div class="figure-caption">{figure.caption}</div>',
            unsafe_allow_html=True,
        )

        if figure_path.exists():
            st.image(str(figure_path), use_container_width=True)
        else:
            st.error(f"Missing figure file: {figure_path}")

        st.markdown(
            f'<div class="takeaway"><strong>Student takeaway:</strong> {figure.student_takeaway}</div>',
            unsafe_allow_html=True,
        )


def main() -> None:
    """Render the student guide page."""
    ensure_app_storage()
    user = require_authenticated_user()

    _render_page_styles()

    st.title("Game Big Picture Guide")
    st.caption(
        "A visual student guide for how Kiki Pickleball Business Simulation connects decisions, competition, operations, innovation, and finance."
    )
    st.markdown(
        f"""
        <div class="big-picture-intro">
        You are viewing this guide as <strong>{user.username}</strong>. These are the polished classroom
        figures for understanding the game before submitting decisions and during round debrief.
        </div>
        """,
        unsafe_allow_html=True,
    )

    for figure in FIGURES:
        _render_figure(figure)

    st.subheader("How To Use These Figures")
    st.markdown(
        """
        - Before saving decisions, use Figures 2, 3, 6, and 7 to check whether your plan is internally consistent.
        - After results, use Figures 4, 5, and 8 to explain why teams won or lost demand, profit, service, or cash health.
        - Between rounds, use Figure 1 to remember that the game rewards learning and adjustment, not one perfect first plan.
        """
    )


main()
