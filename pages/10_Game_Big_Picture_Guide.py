"""Student slide viewer. Navigation changes session state only."""
import base64
from html import escape
from pathlib import Path

import streamlit as st

from utils.auth import require_authenticated_user
from utils.branding import MASCOT_IMAGE_PATH

SLIDES = [
    ("The Round Loop", "One coordinated plan. One round of consequences.", [
        ("01", "Read", "Demand outlook, market brief, competitor prices and previous results."),
        ("02", "Decide", "Forecast, price, source, produce, develop and fund your plan."),
        ("03", "Submit", "Save decisions before the instructor closes submissions."),
        ("04", "Debrief", "Review actual demand and results; adjust for the next round."),
    ], "Cash, debt, inventory, backlog, capacity and product development carry forward."),
    ("Forecast Before You Know", "The outlook is public. Actual demand stays hidden until results.", [
        ("BEFORE", "Outlook range", "Use the low, midpoint and high scenarios for planning."),
        ("OPEN", "Demand locked", "The instructor's actual demand is fixed when submissions first open."),
        ("AFTER", "Actual revealed", "Completed-round demand is disclosed after results."),
    ], "Closing and reopening submissions does not unlock demand. Market demand is not guaranteed team sales."),
    ("Five Slots, Two Starting Products", "New teams start equally. Existing teams keep their saved portfolio.", [
        ("A", "Premium Control", "Premium segment | $189 | active at a new start."),
        ("B", "Starter Play", "Beginner segment | $99 | active at a new start."),
        ("C / D / E", "Vacant slots", "Develop and launch a paddle to fill an empty slot."),
    ], "Five products maximum, with up to two development projects. A launch into an occupied slot replaces its current product."),
    ("Four Checks Before Submission", "Coordinate operations, not just individual numbers.", [
        ("MARKET", "Products", "Segment, price, forecast, quality, inventory target and retirement."),
        ("SUPPLY", "Operations", "Supplier mix, order arrivals, materials, capacity and production."),
        ("FUTURE", "Development", "Project funding, testing, launch timing and replacement."),
        ("CASH", "Finance", "Spending, borrowing, warnings and saved decisions."),
    ], "A forecast is your estimate. Production is your planned output; actual output is limited by available materials and capacity."),
    ("Testing: Time Versus Cost", "Testing effort accumulates across rounds, up to 100% coverage.", [
        ("ROUND 1", "0.5 intensity", "$500 testing cost; 50% cumulative coverage."),
        ("ROUND 2", "+ 0.5 intensity", "$500 more; 100% coverage. Total: $1,000."),
        ("ONE ROUND", "1.0 intensity", "100% coverage immediately. Total: $2,000."),
    ], "Equal coverage gives equal testing benefit. Spreading tests takes longer. Testing costs reduce cash and profit but do not count toward project funding. Intensity resets to zero after each round."),
    ("Ready Does Not Mean Launched", "A launch requires all three gates plus your explicit launch request.", [
        ("GATE 1", "Funding", "Cumulative development investment meets the required amount."),
        ("GATE 2", "Readiness", "Development and accumulated testing meet the readiness threshold."),
        ("GATE 3", "Timing", "The earliest eligible launch round has arrived."),
        ("ACTION", "Launch Now", "Request the launch before saving. At most one launch per team per round."),
    ], "A planned launch date alone does not launch a product. Check the launch preview and the intended replacement slot."),
    ("Read the Planning Preview", "These numbers are planning estimates, not completed results.", [
        ("PLAN", "Forecast vs. output", "Forecast Gap compares production with your forecast."),
        ("MATERIALS", "RM Gap", "Available raw materials minus planned production. Positive means a buffer."),
        ("CAPACITY", "Feasible Output", "How much the current capacity and materials can support."),
        ("RISK", "Warnings", "An active paddle priced below estimated variable cost needs review."),
    ], "Vacant slots do not need prices and should not generate low-price warnings. Without a published demand outlook, demand-based projections are not informative."),
    ("Success Has More Than One Measure", "Choose a strategy that fits the market and your instructor's rubric.", [
        ("EARN", "Profitability", "Review profit and margins, not revenue alone."),
        ("DELIVER", "Service", "Review fill rate, shortages, defects and forecast errors."),
        ("PROTECT", "Resilience", "Watch cash, debt, inventory exposure and supply risk."),
    ], "The largest firm is not automatically the best-run firm. Explain the tradeoffs behind your results."),
]

KEY = "kiki_big_picture_slide"


def move_slide(delta):
    st.session_state[KEY] = max(0, min(len(SLIDES) - 1, st.session_state.get(KEY, 0) + delta))


def main():
    st.set_page_config(page_title="Game Big Picture | Kiki", layout="wide")
    require_authenticated_user()
    st.session_state.setdefault(KEY, 0)
    index = max(0, min(len(SLIDES) - 1, st.session_state[KEY]))
    st.title("Game Big Picture")
    with st.container(key="guide_nav"):
        left, middle, right = st.columns([1, 3, 1])
    left.button("", icon=":material/arrow_back:", key="slide_previous", help="Previous slide", disabled=index == 0,
                on_click=move_slide, args=(-1,), use_container_width=True)
    middle.markdown(f"<p style='text-align:center;margin:6px 0'><strong>{index + 1} / {len(SLIDES)}</strong></p>",
                    unsafe_allow_html=True)
    right.button("", icon=":material/arrow_forward:", key="slide_next", help="Next slide", disabled=index == len(SLIDES) - 1,
                 on_click=move_slide, args=(1,), use_container_width=True)
    title, subtitle, blocks, takeaway = SLIDES[index]
    encoded = base64.b64encode(Path(MASCOT_IMAGE_PATH).read_bytes()).decode("ascii")
    panels = "".join(
        f'<section class="kiki-step tone-{i % 4}"><span>{escape(tag)}</span>'
        f'<h3>{escape(label)}</h3><p>{escape(body)}</p></section>'
        for i, (tag, label, body) in enumerate(blocks)
    )
    st.html(f"""
    <style>
    .stMainBlockContainer {{padding-top:2rem}}
    .stMainBlockContainer h1 {{font-size:28px}}
    .st-key-guide_nav [data-testid="stHorizontalBlock"] {{flex-direction:row;flex-wrap:nowrap}}
    .st-key-guide_nav [data-testid="stColumn"] {{min-width:0!important;flex:1 1 0!important;width:auto!important}}
    .kiki-slide {{max-width:1100px;margin:12px auto 0;min-height:430px;color:#202b29;
        font-family:Arial,sans-serif;letter-spacing:0}}
    .kiki-slide header {{display:flex;align-items:center;justify-content:space-between;gap:20px;
        border-bottom:2px solid #13836d;padding-bottom:14px}}
    .kiki-slide h2 {{font-size:26px;line-height:1.2;margin:0 0 8px;letter-spacing:0}}
    .kiki-slide header p {{font-size:16px;margin:0}}
    .kiki-slide img {{width:86px;height:86px;object-fit:contain;flex-shrink:0}}
    .kiki-diagram {{display:grid;grid-template-columns:repeat({len(blocks)},minmax(0,1fr));gap:14px;margin:28px 0}}
    .kiki-step {{border:1px solid #cbd8d3;border-top:5px solid #13836d;border-radius:6px;padding:18px 16px;min-height:190px;box-sizing:border-box}}
    .kiki-step span {{font-size:13px;font-weight:bold;color:#12614f}}
    .kiki-step h3 {{font-size:21px;margin:16px 0 10px;line-height:1.2;letter-spacing:0;overflow-wrap:anywhere}}
    .kiki-step p {{font-size:16px;line-height:1.5;margin:0}}
    .tone-0 {{background:#eff9f5}}
    .tone-1 {{background:#edf4fc;border-top-color:#3874bb}}
    .tone-2 {{background:#fff7e6;border-top-color:#c5901b}}
    .tone-3 {{background:#fcf0f0;border-top-color:#ba5a5a}}
    .kiki-takeaway {{border-top:1px solid #ccd6d1;padding-top:16px;font-size:16px;line-height:1.6}}
    @media(max-width:700px) {{
        .kiki-slide {{min-height:0}}
        .kiki-slide h2 {{font-size:22px}}
        .kiki-slide img {{width:58px;height:58px}}
        .kiki-diagram {{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:18px 0}}
        .kiki-step {{padding:12px;min-height:160px}}
        .kiki-step h3 {{font-size:18px;margin:10px 0 8px}}
        .kiki-step p,.kiki-takeaway {{font-size:14px}}
    }}
    </style>
    <article class="kiki-slide" aria-label="Slide {index + 1} of {len(SLIDES)}">
    <header><div><h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div>
    <img src="data:image/png;base64,{encoded}" alt="Kiki pickleball mascot"></header>
    <div class="kiki-diagram">{panels}</div>
    <p class="kiki-takeaway">{escape(takeaway)}</p></article>
    """)


main()
