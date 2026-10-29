"""Read-only supply comparisons; no orders or decisions are persisted here."""

from copy import deepcopy

import pandas as pd
import streamlit as st

from engine.config import SUPPLIER_NAMES
from engine.sourcing import material_order_timing, public_incoming_orders, sourcing_quote
from utils.classrooms import active_classroom_id
from utils.database import get_connection
from utils.material_rules import rules_from_connection
from utils.sourcing_rules import load_delivery_policy


COMPARISON_KEY = 'stage_b_supply_comparison'
KEEP_KEY = 'stage_b_keep_supply_comparison'


def _window(first, last):
    return f'R{first}' if first == last else f'R{first}-R{last}'


def proposed_receipts(firm, report, archetype, policy):
    """Use public quotes only; never draw or expose a future shipping outcome."""
    if not firm.supplier_mix_valid() or firm.raw_material_order_qty <= 0:
        return []
    total = firm.supplier_mix_total()
    mix = dict(zip(SUPPLIER_NAMES, (firm.supplier_mix_offshore_pct / total,
                                   firm.supplier_mix_balanced_pct / total,
                                   firm.supplier_mix_premium_pct / total)))
    if policy is None:
        timing = material_order_timing(mix, report.supply_risk)
        arrival = report.round_number + timing['lead_time_rounds']
        return [dict(supplier='Mixed order', quantity=firm.raw_material_order_qty,
                     first=arrival, last=arrival, on_time='-')]
    quote = sourcing_quote(firm.raw_material_order_qty, mix, report.supply_risk,
                           report.round_number, archetype.base_cost,
                           report.material_cost_index, policy)
    return [dict(supplier=row['label'], quantity=row['quantity'],
                 first=row['normal_arrival'], last=row['latest_arrival'],
                 on_time=f"{row['on_time']:.1%}") for row in quote if row['quantity'] > 0]


def arrival_rows(existing_orders, round_number, proposed):
    rows = [dict(Order='Existing', Supplier=row['Supplier'],
                 **{'RM units': row['Quantity'], 'Arrival / window': row['Delivery Window'],
                    'Status': row['Status'], 'On time at order': row['On-time at Order']})
            for row in public_incoming_orders(existing_orders, round_number)]
    rows.extend(dict(Order='Proposed', Supplier=row['supplier'],
                     **{'RM units': row['quantity'], 'Arrival / window': _window(row['first'], row['last']),
                        'Status': 'Not placed', 'On time at order': row['on_time']})
                for row in proposed)
    return rows


def plan_snapshot(preview, firm, proposed):
    window = (_window(min(row['first'] for row in proposed), max(row['last'] for row in proposed))
              if proposed else '-')
    return dict(
        production=preview.total_planned_production_units,
        required=preview.total_material_required,
        available=preview.raw_material_units_available,
        balance=round(preview.raw_material_units_available - preview.total_material_required, 2),
        order=firm.raw_material_order_qty,
        mix=(f'Economy {firm.supplier_mix_offshore_pct:g}% / '
             f'Standard {firm.supplier_mix_balanced_pct:g}% / Reliable {firm.supplier_mix_premium_pct:g}%'),
        unit_cost=preview.weighted_material_unit_cost,
        fees=preview.projected_ordering_cost,
        order_cash=preview.projected_procurement_cost,
        window=window,
        products=deepcopy(preview.material_rows),
    )


MEASURES = (
    ('production', 'Planned paddles', 'units'),
    ('required', 'Required RM', 'rm'),
    ('available', 'Available RM this round', 'rm'),
    ('balance', 'RM surplus / shortage', 'rm'),
    ('order', 'New RM order', 'units'),
    ('mix', 'Supplier mix', 'text'),
    ('unit_cost', 'Current quote / RM', 'currency'),
    ('fees', 'Ordering fee', 'currency'),
    ('order_cash', 'Total order cash', 'currency'),
    ('window', 'New-order delivery window', 'text'),
)


def comparison_rows(saved, current):
    rows = []
    for key, label, kind in MEASURES:
        before, after = saved[key], current[key]
        if kind == 'text':
            delta = 'Changed' if before != after else '-'
        else:
            delta = after - before
            precision = 0 if kind == 'units' else 2
            delta = f'{delta:+,.{precision}f}'
            if kind == 'currency':
                delta = delta[0] + '$' + delta[1:]
            before, after = (f'{value:,.{precision}f}' for value in (before, after))
            if kind == 'currency':
                before, after = '$' + before, '$' + after
        rows.append({'Measure': label, 'Kept comparison': before, 'Current plan': after, 'Change': delta})
    return rows


def product_comparison_rows(saved, current):
    before = {row['Slot']: row for row in saved['products']}
    after = {row['Slot']: row for row in current['products']}
    rows = []
    for slot in sorted(before.keys() | after.keys()):
        old, new = before.get(slot, {}), after.get(slot, {})
        rows.append({'Slot': slot, 'Kept product': old.get('Product', '-'),
                     'Current product': new.get('Product', '-'),
                     'Kept paddles': old.get('Planned Paddles', 0),
                     'Current paddles': new.get('Planned Paddles', 0),
                     'Kept RM': old.get('RM Required', 0), 'Current RM': new.get('RM Required', 0)})
    return rows


def comparison_context(user, firm, report, archetype, policy):
    with get_connection() as connection:
        game_id = connection.execute('SELECT game_id FROM decision_audit_context WHERE singleton=1').fetchone()[0]
        rates = rules_from_connection(connection, report.round_number)
    # A reset or a changed public quote invalidates a comparison even within the same round.
    return (active_classroom_id(), game_id, user.user_id, user.username.casefold(),
            firm.team_name.casefold(), report.round_number, report.supply_risk,
            report.material_cost_index, archetype.base_cost, tuple(sorted(rates.items())),
            None if policy is None else (policy.version, policy.order_fee, policy.additional_supplier_fee))


def render_supply_planning(user, firm, report, archetype, preview, existing_state):
    policy = load_delivery_policy()
    proposed = proposed_receipts(firm, report, archetype, policy)
    with st.expander('Arrival schedule', expanded=False):
        st.caption(f'Available this round: {preview.raw_material_units_available:,.2f} RM | '
                   f'Planned use: {preview.total_material_required:,.2f} RM')
        rows = arrival_rows(existing_state.open_material_orders if existing_state else [],
                            report.round_number, proposed)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption('Receipts only, before future production consumption. Proposed orders are not placed.')
        else:
            st.caption('No existing or proposed arrivals.')
        if not firm.supplier_mix_valid():
            st.warning('Proposed arrival unavailable: supplier percentages must total 100%.')

    context = comparison_context(user, firm, report, archetype, policy)
    retained = st.session_state.get(COMPARISON_KEY)
    if retained and retained['context'] != context:
        st.session_state.pop(COMPARISON_KEY)
        retained = None
    current = plan_snapshot(preview, firm, proposed)
    compare_column, keep_column = st.columns([5, 1.5])
    # Render the action first so the table updates on this same rerun, without saving a decision.
    with keep_column:
        if st.button('Keep comparison', key=KEEP_KEY, icon=':material/bookmark_add:',
                     help='Keep this plan in this browser session for comparison. Does not submit or place an order.',
                     disabled=not firm.supplier_mix_valid(), use_container_width=True):
            retained = {'context': context, 'plan': deepcopy(current)}
            st.session_state[COMPARISON_KEY] = retained
            st.toast('Comparison kept for this team and round. No decision submitted.')
    with compare_column.expander('Compare options', expanded=False):
        if retained:
            st.caption('Comparison kept in this session | Not a submission')
            if firm.supplier_mix_valid():
                st.dataframe(pd.DataFrame(comparison_rows(retained['plan'], current)),
                             hide_index=True, use_container_width=True)
                st.caption('Product quantities')
                st.dataframe(pd.DataFrame(product_comparison_rows(retained['plan'], current)),
                             hide_index=True, use_container_width=True)
            else:
                st.warning('Current comparison unavailable: supplier percentages must total 100%.')
        else:
            st.caption('No comparison kept for this team and round.')
