"""Student-facing visual guide for understanding the simulator as a system."""

from __future__ import annotations

from html import escape

import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage


CARD_COLORS = [
    "#fef3c7",
    "#dbeafe",
    "#dcfce7",
    "#fee2e2",
    "#ede9fe",
    "#cffafe",
]


def _render_styles() -> None:
    """Add lightweight CSS for readable classroom diagrams."""
    st.markdown(
        """
        <style>
        .big-picture-figure {
            border: 1px solid #d8dee9;
            border-radius: 14px;
            padding: 18px 18px 14px 18px;
            margin: 14px 0 28px 0;
            background: #ffffff;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
        }
        .figure-caption {
            color: #64748b;
            font-size: 0.95rem;
            margin-bottom: 14px;
        }
        .flow-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: stretch;
            margin: 12px 0;
        }
        .flow-card {
            min-width: 145px;
            flex: 1 1 145px;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            font-weight: 700;
            color: #0f172a;
        }
        .flow-arrow {
            display: flex;
            align-items: center;
            font-size: 1.6rem;
            color: #64748b;
            padding: 0 2px;
        }
        .small-note {
            color: #475569;
            font-size: 0.9rem;
            line-height: 1.35;
        }
        .two-column-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 12px;
            margin: 12px 0;
        }
        .info-card {
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            padding: 12px;
            background: #f8fafc;
        }
        .info-card h4 {
            margin: 0 0 6px 0;
            color: #0f172a;
            font-size: 1rem;
        }
        .info-card p {
            margin: 0;
            color: #475569;
            font-size: 0.9rem;
        }
        .strategy-table {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
            font-size: 0.92rem;
        }
        .strategy-table th {
            background: #0f172a;
            color: white;
            padding: 8px;
            border: 1px solid #cbd5e1;
        }
        .strategy-table td {
            padding: 8px;
            border: 1px solid #cbd5e1;
            vertical-align: top;
        }
        .formula-box {
            background: #f1f5f9;
            border-left: 5px solid #2563eb;
            border-radius: 10px;
            padding: 12px;
            font-family: Consolas, monospace;
            color: #0f172a;
            margin: 12px 0;
            white-space: pre-wrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _flow_html(items: list[str]) -> str:
    """Build a horizontal flow diagram without fragile indented HTML."""
    parts: list[str] = ['<div class="flow-row">']
    for index, item in enumerate(items):
        color = CARD_COLORS[index % len(CARD_COLORS)]
        parts.append(
            f'<div class="flow-card" style="background:{color};">{escape(item)}</div>'
        )
        if index < len(items) - 1:
            parts.append('<div class="flow-arrow">&rarr;</div>')
    parts.append("</div>")
    return "".join(parts)


def _card_grid(cards: list[tuple[str, str]]) -> str:
    """Build a responsive card grid."""
    html = ['<div class="two-column-grid">']
    for index, (title, body) in enumerate(cards):
        color = CARD_COLORS[index % len(CARD_COLORS)]
        html.append(
            f'<div class="info-card" style="background:{color};">'
            f"<h4>{escape(title)}</h4>"
            f"<p>{escape(body)}</p>"
            "</div>"
        )
    html.append("</div>")
    return "".join(html)


def _formula_box(formula: str) -> str:
    """Build a formula box without indented Markdown code-block behavior."""
    return f'<div class="formula-box">{escape(formula.strip())}</div>'


def _figure(title: str, caption: str, body_html: str, takeaway: str) -> None:
    """Render one numbered figure with caption and takeaway."""
    st.markdown(
        (
            '<div class="big-picture-figure">'
            f"<h3>{escape(title)}</h3>"
            f'<div class="figure-caption">{escape(caption)}</div>'
            f"{body_html}"
            f'<p class="small-note"><strong>Student takeaway:</strong> {escape(takeaway)}</p>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _strategy_table() -> str:
    """Return the strategy tradeoff table."""
    rows = [
        (
            "Cash Conservative",
            "Protect cash, avoid debt, keep production disciplined.",
            "Cash health, resilience, low financial risk.",
            "May miss upside in boom or technology-shift rounds.",
        ),
        (
            "Balanced S&OP",
            "Align forecast, production, inventory, and sourcing.",
            "Forecast accuracy, service level, stable operations.",
            "Can be too cautious if the market suddenly expands.",
        ),
        (
            "Premium Quality",
            "Higher price, stronger QC, premium segment focus.",
            "Margin, quality, reputation, premium demand.",
            "Higher costs; weak if market becomes price sensitive.",
        ),
        (
            "Innovation Leap",
            "Invest early in Gen 3/Gen 4 future products.",
            "Future competitiveness and technology advantage.",
            "Cash drain, delayed payoff, launch risk.",
        ),
        (
            "Aggressive Growth",
            "Expand capacity, produce more, chase demand.",
            "Upside in demand boom or capacity-constrained markets.",
            "Debt, inventory, and utilization stress.",
        ),
        (
            "Low-Cost Volume",
            "Lower price, high volume, simpler products.",
            "Beginner boom, price war, mass market.",
            "Margin risk; high sales can still lose money.",
        ),
    ]
    body = "".join(
        "<tr>"
        f"<td><strong>{escape(strategy)}</strong></td>"
        f"<td>{escape(logic)}</td>"
        f"<td>{escape(strength)}</td>"
        f"<td>{escape(risk)}</td>"
        "</tr>"
        for strategy, logic, strength, risk in rows
    )
    return (
        '<table class="strategy-table">'
        "<thead><tr>"
        "<th>Strategy</th>"
        "<th>Core Logic</th>"
        "<th>Where It Can Win</th>"
        "<th>Main Risk</th>"
        "</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
    )


def main() -> None:
    """Render the visual guide page."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Game Big Picture Guide")
    st.caption(
        "A student-friendly map of how decisions, products, competition, innovation, and finance connect in the simulator."
    )
    st.write(
        f"You are viewing this guide as `{user.username}`. Use it before making decisions and during debrief after each round."
    )
    _render_styles()

    _figure(
        "Figure 1. Overall Game Loop",
        "Every round follows the same classroom rhythm.",
        _flow_html(
            [
                "Instructor Sets Market",
                "Teams Submit Decisions",
                "Round Engine Runs",
                "Results Are Revealed",
                "Teams Learn and Adjust",
            ]
        ),
        "The game is a repeated learning cycle. You do not need to be perfect in round 1; you need to learn from results and improve.",
    )

    _figure(
        "Figure 2. Team Decision Map",
        "A team manages one business system, not separate random inputs.",
        _card_grid(
            [
                ("Forecasting", "Estimate product demand before deciding production."),
                ("Pricing", "Set product price and influence demand share and margin."),
                ("Production", "Choose how many units to make for each active product."),
                ("Capacity", "Use overtime or expansion to support production plans."),
                ("Supplier Mix", "Balance offshore, balanced, and premium sourcing."),
                ("Quality Control", "Spend QC budget to reduce defects and warranty cost."),
                ("Inventory / Backlog", "Protect service without tying up too much cash."),
                ("Finance", "Manage cash, debt, interest, and working capital."),
                ("Portfolio", "Run Product A, B, and C across lifecycle stages."),
                ("NPD Pipeline", "Invest and test future products before launch."),
            ]
        ),
        "Good decisions fit together. A great forecast with bad sourcing, or a great product with no cash, can still fail.",
    )

    _figure(
        "Figure 3. Product Portfolio and Pipeline",
        "Teams manage active products and future projects at the same time.",
        _card_grid(
            [
                ("Product A", "Active or inactive product slot; has price, forecast, production, QC, inventory, lifecycle, and tech generation."),
                ("Product B", "A second product can target another segment or replace an aging product."),
                ("Product C", "A third product can diversify the portfolio or cover beginner/mid/premium demand."),
                ("Project P1", "Future product under development. It cannot sell until launch gates pass."),
                ("Project P2", "Second future product option. Useful for replacement or technology transition."),
                ("Shared Firm Limits", "All products share capacity, materials, cash, reputation, backlog, and management attention."),
            ]
        ),
        "A team is not selling one generic paddle. It is managing a small product business with current products and future bets.",
    )

    _figure(
        "Figure 4. New Product Development Gates",
        "More money helps, but launch requires funding, readiness, and timing.",
        _flow_html(
            [
                "Define Project Charter",
                "Invest Money",
                "Set Testing Intensity",
                "Funding Gate",
                "Readiness Gate",
                "Timing Gate",
                "Launch Now If Ready",
            ]
        )
        + _formula_box(
            """
can_launch_now =
    funding_gate_passed
    and readiness_gate_passed
    and timing_gate_passed
            """
        ),
        "If readiness is stuck, check testing intensity and remaining investment. A planned launch date is a target, not a guarantee.",
    )

    _figure(
        "Figure 5. Competition and Demand Allocation",
        "Products compete for segment demand based on total attractiveness.",
        _card_grid(
            [
                ("Market Demand", "Instructor sets total demand and segment shares: premium, mid, beginner."),
                ("Product Attractiveness", "Price, quality, archetype fit, segment fit, reputation, service readiness, lifecycle, and technology."),
                ("Demand Share", "Products with higher attractiveness receive a larger share of segment demand."),
                ("Sales Realization", "Demand becomes sales only if enough good units are available."),
            ]
        )
        + _formula_box(
            """
product_demand =
    segment_demand
    * product_attractiveness
    / total_attractiveness_of_all_products
            """
        ),
        "Winning demand is not only about low price. It is about the whole value proposition versus competitors.",
    )

    _figure(
        "Figure 6. Product Lifecycle",
        "Products age over time, and lifecycle affects demand attractiveness.",
        _flow_html(["Launch", "Growth", "Maturity", "Decline"])
        + _card_grid(
            [
                ("Launch", "New product gets novelty, but may have early launch risk."),
                ("Growth", "Strong demand momentum if the product fits the market."),
                ("Maturity", "Stable product, but less exciting than newer alternatives."),
                ("Decline", "Demand pressure increases; retirement or replacement may become smart."),
            ]
        ),
        "Old products do not instantly become useless, but they can lose competitiveness as markets and technology move forward.",
    )

    _figure(
        "Figure 7. Cash Flow and Financial Pressure",
        "Operational decisions become cash consequences.",
        _flow_html(
            [
                "Starting Cash",
                "Revenue",
                "Costs",
                "Borrowing / Interest",
                "Ending Cash and Debt",
            ]
        )
        + _formula_box(
            """
ending_cash_before_borrowing =
    starting_cash
    + revenue
    - materials
    - production
    - QC
    - holding
    - warranty
    - backlog
    - expansion
    - NPD investment
    - interest
            """
        ),
        "A strategy can look good operationally but fail financially if it creates too much inventory, debt, or development spending.",
    )

    _figure(
        "Figure 8. Strategy Tradeoff Matrix",
        "Different strategies can win under different market environments.",
        _strategy_table(),
        "There is no universal best strategy. The winner depends on what the market rewards and how well the team manages tradeoffs.",
    )

    st.subheader("How Students Should Use This Page")
    st.markdown(
        """
        - Before submitting: use Figures 2, 3, 4, and 7 to check whether your decisions fit together.
        - During debrief: use Figures 5, 6, and 8 to explain why some teams won demand or profit.
        - Between rounds: ask whether your strategy should stay the same or adapt to the new market report.
        """
    )


main()
