# Market Scenario Comparison

The same team strategies were run through each named market condition.

## Scenario Winners

| market_scenario | market_label | winning_team | winning_archetype | winning_strategy | winning_profit | winning_cash | winning_debt | average_profit | average_forecast_wape | liquidity_stress_team_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | Baseline market | Team 01 | Premium Quality | Premium quality | $11,496.32 | $70,028.46 | $0.00 | $4,845.58 | 29.7% | 3 |
| demand_boom | Demand boom | Team 01 | Premium Quality | Premium quality | $11,905.73 | $75,677.07 | $0.00 | $3,515.05 | 30.4% | 2 |
| supply_shock | Supply shock | Team 01 | Premium Quality | Premium quality | $8,157.45 | $56,867.45 | $0.00 | $3,177.76 | 34.5% | 3 |
| tech_shift | Fast tech shift | Team 01 | Premium Quality | Premium quality | $12,088.36 | $69,416.51 | $0.00 | $2,573.42 | 24.2% | 3 |
| price_recession | Price-pressure recession | Team 04 | Low-Cost Volume | Innovation leap | $9,542.38 | $23,440.45 | $28,000.00 | $-1,710.60 | 63.9% | 4 |
| quality_sensitive | Quality-sensitive market | Team 01 | Premium Quality | Premium quality | $10,980.17 | $67,287.22 | $0.00 | $4,505.12 | 31.6% | 3 |

## Strategy Robustness

| strategy | wins | average_rank | average_profit | liquidity_stress_count |
| --- | --- | --- | --- | --- |
| Premium quality | 5 | 1.33 | $9,553.02 | 0 |
| Innovation leap | 1 | 2.33 | $7,642.19 | 6 |
| Balanced S&OP | 0 | 3.0 | $4,886.18 | 1 |
| Aggressive growth | 0 | 4.5 | $-142.69 | 6 |
| Cash conservative | 0 | 4.5 | $428.27 | 0 |
| Low-cost volume | 0 | 5.33 | $-5,460.63 | 5 |

## Output Files

- `market_scenario_comparison.csv` summarizes one winner per market scenario.
- `market_scenario_team_results.csv` compares every team under every market scenario.
- Each scenario also has its own subfolder with full team, product, forecast, and state CSV files.
