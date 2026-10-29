"""Shared standard-material units, separate from whole-paddle capacity."""

from decimal import Decimal
from fractions import Fraction
import math


DEFAULT_REQUIREMENTS = {"beginner": 0.7, "mid": 1.0, "premium": 1.2}
LEGACY_REQUIREMENTS = {segment: 1.0 for segment in DEFAULT_REQUIREMENTS}


def validate_requirements(values):
    if set(values) != set(DEFAULT_REQUIREMENTS):
        raise ValueError("Provide Beginner, Mid and Premium material requirements.")
    result = {}
    for segment, value in values.items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("RM per paddle must be a number.") from exc
        if (not math.isfinite(number) or not 0.01 <= number <= 10
                or abs(number - round(number, 2)) > 1e-9):
            raise ValueError("RM per paddle must be 0.01 to 10, with at most two decimals.")
        result[segment] = round(number, 2)
    return result


def material_design(product):
    return product.material_design or product.target_segment


def allocate_materials(requests, rates, capacity, available):
    """Scale plans together, then allocate whole-paddle remainders without overdraft."""
    requests = {slot: max(int(qty), 0) for slot, qty in requests.items()}
    costs = {slot: int(Decimal(str(rates[slot])) * 100) for slot in requests}
    if any(cost <= 0 for cost in costs.values()):
        raise ValueError("Material requirements must be positive.")
    stock = max(int(Decimal(str(available)) * 100), 0)
    capacity = max(int(capacity), 0)
    total = sum(requests.values())
    required = sum(requests[s] * costs[s] for s in requests)
    if not total or not capacity or not stock:
        return {slot: 0 for slot in requests}, 0.0
    scale = min(Fraction(1), Fraction(capacity, total), Fraction(stock, required))
    targets = {s: requests[s] * scale for s in requests}
    allocated = {s: math.floor(targets[s]) for s in requests}
    remaining_stock = stock - sum(allocated[s] * costs[s] for s in requests)
    remaining_capacity = capacity - sum(allocated.values())
    # Integer hundredths prevent fractional inventory drift across rounds.
    while remaining_capacity:
        eligible = [s for s in requests if allocated[s] < requests[s] and costs[s] <= remaining_stock]
        if not eligible:
            break
        slot = max(eligible, key=lambda s: (targets[s] - allocated[s], requests[s], s))
        allocated[slot] += 1
        remaining_stock -= costs[slot]
        remaining_capacity -= 1
    return allocated, (stock - remaining_stock) / 100
