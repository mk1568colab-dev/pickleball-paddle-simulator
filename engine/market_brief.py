"""Planning guidance derived exclusively from publicly disclosed inputs."""


def market_brief(public):
    low, high = public["demand_outlook_low"], public["demand_outlook_high"]
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        return "The instructor has not published this round's demand outlook yet.", []
    midpoint = round((low + high) / 2)
    shares = [("Beginner", public["beginner_share"]),
              ("Mid-market", public["mid_share"]), ("Premium", public["premium_share"])]
    total = sum(share for _, share in shares)
    rows = [{"Segment": name, "Low scenario": round(low * share / total),
             "Midpoint scenario": round(midpoint * share / total),
             "High scenario": round(high * share / total)} for name, share in shares] if total > 0 else []
    largest = max(shares, key=lambda item: item[1])[0]
    cost_index = public["material_cost_index"]
    cost_message = (
        "Materials are more expensive than the baseline; check margins before adding volume."
        if cost_index > 1.05 else
        "Material costs are below the baseline, creating room to review pricing or margins."
        if cost_index < 0.95 else
        "Material costs are close to the baseline."
    )
    risk_message = {
        "high": "Supply risk is high; review expected arrivals, supplier mix, and inventory buffers.",
        "low": "Supply risk is low, but ordered materials still need time to arrive.",
    }.get(str(public["supply_risk"]).lower(),
          "Supply risk is moderate; compare expected arrivals with your production plan.")
    quality_message = (
        "Quality is especially important in this market; weigh quality spending against margin and cash."
        if public["quality_sensitivity"] >= 0.7 else
        "Consider quality alongside price, product fit, and service when positioning your paddles."
    )
    summary = (
        f"Round {public['round_number']} has a market-wide outlook of {low:,.0f}-{high:,.0f} units, "
        f"with {midpoint:,} units as a midpoint planning scenario, not a guaranteed outcome. "
        f"{largest} is the largest segment in the published mix. "
        f"{cost_message} {risk_message} {quality_message} "
        f"The published market technology benchmark is generation {public['current_market_generation']}; "
        "compare it with your active products and development pipeline. "
        "Use the low-demand case to review cash and inventory exposure, and the high-demand case "
        "to review capacity and service. Segment estimates describe the whole market, not your team's demand."
    )
    if public.get("event"):
        summary += f" Market event: {public['event']}"
    return summary, rows
