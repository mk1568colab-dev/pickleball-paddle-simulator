"""Shared live/replay reputation policy. Saved metric precision is authoritative."""
from math import isfinite

POLICY_ID = 'reputation_50_50_v1'
POLICY_BASIS = 'reputation_policy_recalculation_v1'
MIN_REPUTATION = 10.0
MAX_REPUTATION = 100.0
HISTORY_WEIGHT = 0.5
ENTRY_DEDUCTION = 10.0
OPENING_REPUTATION = 60.0


def entry_score(scores):
    values = sorted(float(value) for value in scores)
    if any(not isfinite(value) or not 0 <= value <= 100 for value in values):
        raise ValueError('Invalid reputation benchmark.')
    if values:
        position = .2 * (len(values)-1)
        lower = int(position)
        benchmark = values[lower] + (position-lower)*(values[min(lower+1,len(values)-1)]-values[lower])
    else:
        benchmark = OPENING_REPUTATION
    return round(max(MIN_REPUTATION, min(OPENING_REPUTATION, benchmark)-ENTRY_DEDUCTION), 2)


def reputation_step(previous, fill_rate, defect_rate, quality_sensitivity, production_units, *, has_service_demand=True):
    values = (previous, fill_rate, defect_rate, quality_sensitivity, production_units)
    if not all(isfinite(float(value)) for value in values):
        raise ValueError('Reputation inputs must be finite.')
    fill = max(0.0, min(1.0, round(float(fill_rate), 4)))
    defects = max(0.0, round(float(defect_rate), 4))
    quality = max(0.0, 1-defects/.05) if production_units > 0 else 0.0
    quality_weight = .2 + .1*max(-1.0, min(1.0, quality_sensitivity))
    performance = 100*((1-quality_weight)*fill**2 + quality_weight*quality)
    score = HISTORY_WEIGHT*previous + (1-HISTORY_WEIGHT)*performance if has_service_demand else previous
    return dict(previous=previous, performance=performance, quality_weight=quality_weight,
                reputation=round(max(MIN_REPUTATION, min(MAX_REPUTATION, score)), 2))


def replay_reputation(results, markets):
    """Re-evaluate fixed historical outcomes, not counterfactual sales or cash."""
    scores, backlogs, history, seen = {}, {}, [], set()
    for round_number in sorted({r['round_number'] for r in results}):
        if round_number not in markets:
            raise ValueError(f'Missing market report for round {round_number}.')
        start = entry_score(scores.values()) if scores else OPENING_REPUTATION
        for row in sorted((r for r in results if r['round_number'] == round_number), key=lambda r:r['team_name']):
            team = row['team_name']
            if (team, round_number) in seen:
                raise ValueError('Duplicate team/round result.')
            seen.add((team, round_number))
            prior = scores.get(team, start)
            step = reputation_step(prior, row['fill_rate'], row['defect_rate'],
                                   markets[round_number]['quality_sensitivity'], row['actual_production_units'],
                                   has_service_demand=row['demand_allocated']+backlogs.get(team,0)>0)
            scores[team] = step['reputation']
            backlogs[team] = row['backlog_units_end']
            history.append(dict(team=team, round=round_number, **step))
    return scores, history
