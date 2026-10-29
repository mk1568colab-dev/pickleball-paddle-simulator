"""One neutral market narrative, derived only from published round conditions."""

from math import isclose


def _segment_mix_sentence(public):
    shares = [("Beginner", public['beginner_share']),
              ("Mid-market", public['mid_share']), ("Premium", public['premium_share'])]
    positive = [(name, share) for name, share in shares if share > 0]
    if not positive:
        return 'A segment mix is not available.'
    ranked = sorted(positive, key=lambda item: item[1], reverse=True)
    leaders = [name for name, share in ranked if isclose(share, ranked[0][1], abs_tol=1e-9)]
    if len(leaders) == 3:
        sentence = 'Expected demand is evenly distributed across Beginner, Mid-market, and Premium paddles.'
    elif len(leaders) == 2:
        sentence = f'{leaders[0]} and {leaders[1]} paddles share the largest portion of expected demand.'
        others = [name for name, _ in ranked if name not in leaders]
        if others:
            sentence += f' {others[0]} paddles represent a smaller segment.'
    elif len(positive) == 1:
        sentence = f'Expected demand is concentrated entirely in {ranked[0][0]} paddles.'
    elif len(positive) == 3 and isclose(ranked[1][1], ranked[2][1], abs_tol=1e-9):
        sentence = (f'{ranked[0][0]} paddles represent the largest segment; '
                    f'{ranked[1][0]} and {ranked[2][0]} paddles account for equal, smaller portions.')
    else:
        sentence = f'{ranked[0][0]} paddles represent the largest segment, followed by '
        sentence += ' and then '.join(name for name, _ in ranked[1:]) + ' paddles.'
    absent = [name for name, share in shares if share <= 0]
    if absent:
        sentence += ' No demand is included for ' + ' or '.join(absent) + ' paddles in this outlook.'
    return sentence


def _level(value, low, middle, high, low_cutoff=.4, high_cutoff=.7,
           very_high=None, very_high_cutoff=.85):
    if very_high is not None and value >= very_high_cutoff:
        return very_high
    return low if value < low_cutoff else high if value >= high_cutoff else middle


def market_brief(public):
    """Describe current conditions, without advice, invented events or private demand."""
    low, high = public['demand_outlook_low'], public['demand_outlook_high']
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        demand = (f'The market-wide demand outlook for Round {public["round_number"]} is '
                  f'{low:,.0f} to {high:,.0f} paddles. This is an outlook, not confirmed demand '
                  'or guaranteed sales for individual firms.')
    else:
        demand = "This round's market-wide demand outlook has not been published."

    cost = _level(public['material_cost_index'],
                  'Material prices are below the baseline.',
                  'Material prices are close to the baseline.',
                  'Material prices are above the baseline.', low_cutoff=.95, high_cutoff=1.05)
    supply = {
        'low': 'Supply conditions are relatively stable, although materials still require delivery time.',
        'moderate': 'Supply conditions involve some delivery uncertainty; normal arrival dates are not guaranteed.',
        'high': 'Supply conditions are disrupted, with a higher risk of late material deliveries.',
    }[str(public['supply_risk']).lower()]
    quality = _level(public['quality_sensitivity'],
                     'Quality and service problems have a relatively limited influence on firms\' reputations.',
                     'Product defects and unserved demand have a moderate influence on firms\' reputations.',
                     'Product defects and unserved demand have a strong influence on firms\' reputations.',
                     very_high='Product defects and unserved demand have a particularly strong influence on firms\' reputations.')

    # The current coefficient widens price tolerance and reduces technology weight;
    # do not describe it as a penalty for every price increase.
    beginner = _level(public['beginner_price_pressure'],
                      'Beginner buyers show comparatively more interest in technology and a narrower range of acceptable prices.',
                      'Beginner buyers place relatively little weight on the latest technology and accept a moderate range of prices.',
                      'Beginner buyers place less weight on the latest technology and accept a broader range of prices.')
    technology = _level(public['technology_shift_rate'],
                       'Products behind the market benchmark face relatively limited additional obsolescence pressure.',
                       'Products behind the market benchmark face moderate additional obsolescence pressure.',
                       'Products behind the market benchmark face strong additional obsolescence pressure.',
                       low_cutoff=.15, high_cutoff=.30,
                       very_high='Products behind the market benchmark face particularly strong additional obsolescence pressure.',
                       very_high_cutoff=.50)
    adoption = []
    for label, key in [('Premium', 'premium_tech_adoption'), ('Mid-market', 'mid_market_tech_adoption')]:
        emphasis = _level(public[key], 'limited', 'moderate', 'strong', very_high='particularly strong')
        adoption.append(f'{label} buyers place {emphasis} emphasis on product technology relative to the market benchmark.')

    operating_conditions = cost + ' ' + supply
    if public.get('event', '').strip():
        operating_conditions += ' Market event: ' + public['event'].strip()
    paragraphs = [demand + ' ' + _segment_mix_sentence(public),
                  operating_conditions,
                  quality + f' The current market technology benchmark is Generation {public["current_market_generation"]}. '
                  + technology + ' ' + ' '.join(adoption) + ' ' + beginner]
    return '\n\n'.join(paragraphs)
