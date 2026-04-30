"""Teaching analytics used for instructor debriefs and ITE-style evidence.

The simulator already produces many quantitative outputs. This module translates
those outputs into classroom-friendly diagnostics without changing the round
engine or team scores.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from models.schemas import ForecastAccuracyResult, ProductRoundResult, RoundResult


def build_debrief_rows(
    team_results: list[RoundResult],
    product_results: list[ProductRoundResult],
) -> list[dict[str, object]]:
    """Build instructor-facing debrief diagnostics for the latest round."""
    latest_team_results = _latest_team_results(team_results)
    if not latest_team_results:
        return []

    products_by_team: dict[str, list[ProductRoundResult]] = defaultdict(list)
    latest_round = max(result.round_number for result in latest_team_results)
    for product in product_results:
        if product.round_number == latest_round:
            products_by_team[product.team_name].append(product)

    rows: list[dict[str, object]] = []
    for result in sorted(latest_team_results, key=lambda item: item.team_name):
        product_focus = _product_focus(products_by_team[result.team_name])
        teaching_point, root_cause, question = _diagnose_team_result(result)
        rows.append(
            {
                "round_number": result.round_number,
                "team_name": result.team_name,
                "primary_teaching_point": teaching_point,
                "likely_root_cause": root_cause,
                "key_evidence": _key_evidence_text(result),
                "product_to_discuss": product_focus,
                "suggested_debrief_question": question,
            }
        )
    return rows


def build_balanced_score_rows(
    team_results: list[RoundResult],
) -> list[dict[str, object]]:
    """Build an optional multi-objective teaching score for the latest round."""
    latest_team_results = _latest_team_results(team_results)
    if not latest_team_results:
        return []

    profit_scores = _percentile_scores(
        {result.team_name: result.profit for result in latest_team_results}
    )
    fill_rate_scores = _percentile_scores(
        {result.team_name: result.fill_rate for result in latest_team_results}
    )
    forecast_scores = _percentile_scores(
        {result.team_name: -result.forecast_wape for result in latest_team_results}
    )
    liquidity_scores = _percentile_scores(
        {
            result.team_name: result.ending_cash_balance
            - result.short_term_debt_balance
            for result in latest_team_results
        }
    )

    rows: list[dict[str, object]] = []
    for result in latest_team_results:
        liquidity_penalty = 0.08 if result.liquidity_stress_flag else 0.0
        balanced_score = 100.0 * (
            0.40 * profit_scores[result.team_name]
            + 0.20 * fill_rate_scores[result.team_name]
            + 0.20 * forecast_scores[result.team_name]
            + 0.20 * liquidity_scores[result.team_name]
            - liquidity_penalty
        )
        rows.append(
            {
                "round_number": result.round_number,
                "team_name": result.team_name,
                "balanced_score": round(max(balanced_score, 0.0), 1),
                "profit_component": round(100.0 * profit_scores[result.team_name], 1),
                "service_component": round(100.0 * fill_rate_scores[result.team_name], 1),
                "forecast_component": round(100.0 * forecast_scores[result.team_name], 1),
                "liquidity_component": round(100.0 * liquidity_scores[result.team_name], 1),
                "liquidity_penalty_applied": result.liquidity_stress_flag,
                "profit": round(result.profit, 2),
                "fill_rate": round(result.fill_rate, 3),
                "forecast_wape": round(result.forecast_wape, 3),
                "cash_minus_debt": round(
                    result.ending_cash_balance - result.short_term_debt_balance,
                    2,
                ),
            }
        )

    return sorted(rows, key=lambda row: row["balanced_score"], reverse=True)


def build_forecast_learning_rows(
    forecast_results: list[ForecastAccuracyResult],
) -> list[dict[str, object]]:
    """Summarize forecast learning evidence by team for the latest round."""
    if not forecast_results:
        return []

    latest_round = max(result.round_number for result in forecast_results)
    grouped: dict[str, list[ForecastAccuracyResult]] = defaultdict(list)
    for result in forecast_results:
        if result.round_number == latest_round:
            grouped[result.team_name].append(result)

    rows: list[dict[str, object]] = []
    for team_name, team_rows in sorted(grouped.items()):
        total_actual = sum(item.actual_demand_units for item in team_rows)
        total_absolute_error = sum(item.absolute_error_units for item in team_rows)
        total_forecast = sum(item.forecast_units for item in team_rows)
        total_bias = sum(item.forecast_error_units for item in team_rows)
        rows.append(
            {
                "round_number": latest_round,
                "team_name": team_name,
                "total_forecast_units": total_forecast,
                "total_actual_demand_units": round(total_actual, 1),
                "absolute_error_units": round(total_absolute_error, 1),
                "wape": round(total_absolute_error / max(total_actual, 1.0), 3),
                "bias_pct": round(total_bias / max(total_forecast, 1), 3),
            }
        )
    return rows


def _latest_team_results(team_results: Iterable[RoundResult]) -> list[RoundResult]:
    """Return team results for only the latest completed round."""
    results = list(team_results)
    if not results:
        return []
    latest_round = max(result.round_number for result in results)
    return [result for result in results if result.round_number == latest_round]


def _diagnose_team_result(result: RoundResult) -> tuple[str, str, str]:
    """Return a teaching point, likely cause, and debrief question."""
    if result.liquidity_stress_flag or result.short_term_debt_balance > max(
        5_000.0,
        0.35 * result.revenue,
    ):
        return (
            "Liquidity discipline",
            "The team created cash pressure through cost, inventory, borrowing, or investment timing.",
            "Which decision consumed the most cash, and what would you change if cash health were the primary objective?",
        )
    if result.profit < 0 and result.sales_units > 0:
        return (
            "Volume is not the same as profit",
            "Revenue was not enough to cover procurement, production, QC, holding, warranty, backlog, expansion, and interest costs.",
            "Which cost bucket made the strategy unattractive even though the team sold units?",
        )
    if result.forecast_wape > 0.35:
        return (
            "Forecast-vs-plan discipline",
            "Product forecasts were materially different from realized demand.",
            "Did the team overbuild, underbuild, or misallocate production across products?",
        )
    if result.fill_rate < 0.85 or result.service_gap_units > 0:
        return (
            "Service level and constraint management",
            "Demand exceeded the team's ability or willingness to serve it.",
            "Was the service gap caused by capacity, raw materials, product mix, or inventory policy?",
        )
    if result.defect_rate > 0.06:
        return (
            "Quality is an economic decision",
            "Defects and warranty exposure were high relative to the market.",
            "Was quality pressure caused by supplier mix, QC spend, utilization stress, or launch instability?",
        )
    if result.ending_inventory > max(100, 0.35 * result.total_actual_demand_units):
        return (
            "Inventory risk",
            "The team carried a large ending inventory position relative to demand.",
            "Was inventory a deliberate service buffer or an expensive forecast/planning error?",
        )
    if result.innovation_investment > max(3_000.0, 0.12 * result.revenue):
        return (
            "Innovation timing tradeoff",
            "The team invested heavily in future products relative to current-round revenue.",
            "Did innovation spending create enough future readiness to justify the current cash tradeoff?",
        )
    if result.cannibalized_demand_units > max(20.0, 0.05 * result.demand_allocated):
        return (
            "Portfolio cannibalization",
            "Products within the same team competed for similar demand.",
            "Should the team reposition, retire, or differentiate one of the overlapping products?",
        )
    return (
        "Balanced execution",
        "The team avoided the most visible planning, service, quality, and liquidity problems.",
        "Which tradeoff did the team manage best, and what risk remains for the next round?",
    )


def _key_evidence_text(result: RoundResult) -> str:
    """Create compact evidence text for the debrief table."""
    return (
        f"Profit ${result.profit:,.0f}; fill rate {result.fill_rate:.0%}; "
        f"WAPE {result.forecast_wape:.0%}; debt ${result.short_term_debt_balance:,.0f}; "
        f"defects {result.defect_rate:.1%}."
    )


def _product_focus(products: list[ProductRoundResult]) -> str:
    """Return the product that is most useful to discuss in debrief."""
    if not products:
        return "No product-level result"

    candidate = min(
        products,
        key=lambda item: (
            item.profit_contribution,
            -item.lost_sales_units,
            item.fill_rate,
        ),
    )
    return (
        f"{candidate.slot_name}: {candidate.product_name} "
        f"(profit ${candidate.profit_contribution:,.0f}, "
        f"fill {candidate.fill_rate:.0%})"
    )


def _percentile_scores(values_by_team: dict[str, float]) -> dict[str, float]:
    """Return simple percentile scores from 0 to 1, where higher is better."""
    if not values_by_team:
        return {}
    if len(values_by_team) == 1:
        team_name = next(iter(values_by_team))
        return {team_name: 1.0}

    sorted_items = sorted(values_by_team.items(), key=lambda item: item[1])
    denominator = len(sorted_items) - 1
    scores: dict[str, float] = {}
    for index, (team_name, _) in enumerate(sorted_items):
        scores[team_name] = index / denominator
    return scores
