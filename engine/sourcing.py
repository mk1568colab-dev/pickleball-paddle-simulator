"""Shared material-order timing for the decision preview and round engine."""

from engine.config import SUPPLIER_BASE_LEAD_TIMES, SUPPLIER_NAMES, SUPPLY_RISK_INDEX
from engine.config import BASE_MATERIAL_COST_SHARE, SUPPLIER_MATERIAL_COST_MULTIPLIERS
from hashlib import sha256
import math


DISPLAY_NAMES = dict(zip(SUPPLIER_NAMES, ('Economy', 'Standard', 'Reliable')))
NORMAL_LEAD = dict(zip(SUPPLIER_NAMES, (2, 1, 1)))
# Version 1: probabilities of +0, +1 and +2 rounds, fixed at order placement.
DELAY_PROBABILITIES = {
    'Offshore Value': {'Low': (.90, .10, 0), 'Moderate': (.75, .20, .05), 'High': (.55, .30, .15)},
    'Balanced Source': {'Low': (.97, .03, 0), 'Moderate': (.92, .08, 0), 'High': (.85, .13, .02)},
    'Premium Reliable': {'Low': (.995, .005, 0), 'Moderate': (.99, .01, 0), 'High': (.98, .02, 0)},
}


def supplier_delay(seed, placed_round, supplier, risk):
    """One reproducible supplier shock per classroom/round, shared by all teams."""
    digest = sha256(f'shipping-v1:{seed}:{placed_round}:{supplier}'.encode()).digest()
    draw = int.from_bytes(digest[:8], 'big') / 2**64
    cumulative = 0.0
    for delay, probability in enumerate(DELAY_PROBABILITIES[supplier][risk]):
        cumulative += probability
        if draw < cumulative:
            return delay
    return max(i for i, p in enumerate(DELAY_PROBABILITIES[supplier][risk]) if p)


def supplier_quantities(quantity, mix):
    """Allocate whole material units without losing units or creating tiny phantom orders."""
    quantity = max(int(quantity), 0)
    weights = {name: max(float(mix.get(name, 0)), 0) for name in SUPPLIER_NAMES}
    total = sum(weights.values())
    if not total:
        weights['Balanced Source'], total = 1, 1
    exact = {name: quantity * weights[name] / total for name in SUPPLIER_NAMES}
    result = {name: math.floor(value) for name, value in exact.items()}
    ranked = sorted(SUPPLIER_NAMES, key=lambda name: exact[name] - result[name], reverse=True)
    for name in ranked[:quantity - sum(result.values())]:
        result[name] += 1
    return result


def order_fee_allocations(quantities, policy):
    """Allocate one round-level ordering charge across its supplier shipments."""
    active = [name for name in SUPPLIER_NAMES if quantities[name] > 0]
    fees = dict.fromkeys(SUPPLIER_NAMES, 0.0)
    if not active:
        return fees
    if policy.version == 1:
        return {name: policy.order_fee if name in active else 0.0 for name in SUPPLIER_NAMES}
    if policy.version != 2:
        raise ValueError('Unsupported ordering policy version.')
    total_cents = round((policy.order_fee + (len(active) - 1) * policy.additional_supplier_fee) * 100)
    share, remainder = divmod(total_cents, len(active))
    for index, name in enumerate(active):
        fees[name] = (share + (index < remainder)) / 100
    return fees


def ordering_fee_description(policy):
    if policy.version == 1:
        return f'USD {policy.order_fee:,.0f} per supplier with a nonzero order; no order, no fee.'
    return (f'Base order fee USD {policy.order_fee:,.0f} + USD {policy.additional_supplier_fee:,.0f} '
            'per additional supplier with a nonzero order. No order, no fee. '
            'Fee shares in the table allocate this single total evenly across suppliers.')


def sourcing_quote(quantity, mix, risk, placed_round, base_cost, material_index, policy):
    """Public quote only: never evaluate or reveal a future disruption here."""
    quantities = supplier_quantities(quantity, mix)
    fees = order_fee_allocations(quantities, policy)
    rows = []
    for name in SUPPLIER_NAMES:
        probabilities = DELAY_PROBABILITIES[name][risk]
        normal = NORMAL_LEAD[name]
        max_delay = max(i for i, p in enumerate(probabilities) if p)
        unit_cost = round(base_cost * BASE_MATERIAL_COST_SHARE * material_index
                          * SUPPLIER_MATERIAL_COST_MULTIPLIERS[name], 2)
        qty = quantities[name]
        rows.append(dict(supplier=name, label=DISPLAY_NAMES[name], quantity=qty,
                         normal_lead=normal, normal_arrival=placed_round + normal,
                         latest_arrival=placed_round + normal + max_delay,
                         on_time=probabilities[0], unit_cost=unit_cost,
                         material_cost=round(qty * unit_cost, 2),
                         order_fee=fees[name]))
    return rows


def public_incoming_orders(orders, current_round):
    """Expose confirmed current arrivals, but not future realized delay draws."""
    rows = []
    for order in sorted(orders, key=lambda o: (o.placed_round, o.supplier_name)):
        arrived = order.arrival_round <= current_round
        if order.supplier_name:
            normal = order.normal_arrival_round
            latest = order.latest_arrival_round
            window = f'R{normal}' if normal == latest else f'R{normal}-R{latest}'
            status = 'Available this round' if arrived else ('Delayed / in transit' if current_round >= normal else 'In transit')
            reliability = f'{order.on_time_probability:.1%}'
        else:
            normal = order.arrival_round
            window = f'R{normal}'
            status = 'Available this round' if arrived else 'Scheduled (legacy order)'
            reliability = '-'
        rows.append({'Supplier': DISPLAY_NAMES.get(order.supplier_name, 'Legacy mixed order'),
                     'Quantity': order.quantity, 'Status': status, 'Placed': f'R{order.placed_round}',
                     'Normal Arrival': f'R{normal}', 'Delivery Window': window,
                     'On-time at Order': reliability,
                     'Unit Cost': f'${order.weighted_material_unit_cost:,.2f}'})
    return rows


def material_lead_time_rounds(adjusted_lead_time: float) -> int:
    """Match the engine's stored two-decimal lead time before rounding rounds."""
    return max(int(round(round(adjusted_lead_time, 2))), 1)


def material_order_timing(normalized_mix: dict[str, float], supply_risk: str) -> dict:
    base = sum(normalized_mix[name] * SUPPLIER_BASE_LEAD_TIMES[name]
               for name in SUPPLIER_NAMES)
    risk_index = SUPPLY_RISK_INDEX[supply_risk]
    adjusted = round(max(base * risk_index, 1.0), 2)
    return {
        "base_weighted_lead_time": round(base, 2),
        "adjusted_lead_time": adjusted,
        "lead_time_rounds": material_lead_time_rounds(adjusted),
        "supply_risk_index": risk_index,
    }
