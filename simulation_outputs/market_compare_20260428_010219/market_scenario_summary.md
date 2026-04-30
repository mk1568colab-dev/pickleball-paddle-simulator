# Market Scenario Comparison

The same team strategies were run through each named market condition.

## Scenario Winners

| market_scenario | market_label | profit_winner | profit_winner_strategy | profit_winner_profit | balanced_winner | balanced_winner_strategy | balanced_score | service_winner | forecast_winner | cash_winner | average_profit | average_forecast_wape | liquidity_stress_team_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | Baseline market | Team 05 | Cash conservative | $7,701.04 | Team 05 | Cash conservative | 80.0 | Team 02 | Team 02 | Team 05 | $-1,365.89 | 48.3% | 4 |
| demand_boom | Demand boom | Team 05 | Cash conservative | $7,452.93 | Team 05 | Cash conservative | 76.0 | Team 02 | Team 02 | Team 05 | $-1,675.71 | 76.3% | 4 |
| volume_surge | Volume surge | Team 05 | Cash conservative | $5,426.33 | Team 05 | Cash conservative | 76.0 | Team 02 | Team 02 | Team 05 | $-1,565.12 | 80.8% | 4 |
| supply_shock | Supply shock | Team 05 | Cash conservative | $3,387.76 | Team 05 | Cash conservative | 76.0 | Team 02 | Team 02 | Team 05 | $-4,172.42 | 46.0% | 4 |
| tech_shift | Fast tech shift | Team 05 | Cash conservative | $7,203.83 | Team 01 | Premium quality | 68.0 | Team 01 | Team 01 | Team 05 | $-900.21 | 50.3% | 4 |
| price_recession | Price-pressure recession | Team 05 | Cash conservative | $4,159.93 | Team 05 | Cash conservative | 88.0 | Team 02 | Team 04 | Team 05 | $-12,711.52 | 51.4% | 4 |
| quality_sensitive | Quality-sensitive market | Team 05 | Cash conservative | $7,328.46 | Team 05 | Cash conservative | 80.0 | Team 02 | Team 02 | Team 05 | $-1,586.98 | 49.1% | 4 |

## Multi-Objective Strategy Robustness

| strategy | profit_wins | balanced_wins | average_rank | average_profit | average_balanced_score | liquidity_stress_count |
| --- | --- | --- | --- | --- | --- | --- |
| Cash conservative | 7 | 6 | 1.0 | $6,094.33 | 77.7 | 0 |
| Premium quality | 0 | 1 | 3.0 | $-1,198.74 | 43.4 | 0 |
| Balanced S&OP | 0 | 0 | 2.14 | $2,244.51 | 67.4 | 7 |
| Aggressive growth | 0 | 0 | 4.29 | $-8,682.92 | 33.7 | 7 |
| Low-cost volume | 0 | 0 | 5.43 | $-10,923.90 | 32.6 | 7 |
| Innovation leap | 0 | 0 | 5.14 | $-8,085.72 | 13.1 | 7 |

Balanced score weights: 40% profit, 20% fill rate, 20% forecast accuracy, 20% cash-minus-debt, with a small liquidity-stress penalty.

## Output Files

- `market_scenario_comparison.csv` summarizes one winner per market scenario.
- `market_scenario_team_results.csv` compares every team under every market scenario.
- Each scenario also has its own subfolder with full team, product, forecast, and state CSV files.
