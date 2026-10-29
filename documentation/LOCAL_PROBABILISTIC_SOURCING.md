# Local Probabilistic Sourcing Lab

Status: local only, not deployed. The preview launcher creates new fictional
classrooms in a unique `.preview/probabilistic_sourcing_*` directory. It does not
copy, reset, or modify existing classroom databases. New shipping rules are opt-in
before a game has decisions, demand commitments, or results; existing games keep
their previous shipping behavior. Existing inbound orders retain recorded dates
and prices.

## Calibration, Policy Version 2

Version 2 changes ordering fees only. Existing version-1 classroom policies and
saved orders are read unchanged; the launcher creates a new game for version 2.
Shipping probabilities, supplier prices and holding rates are unchanged.

These are teaching parameters, not empirical pickleball-industry estimates.
At the equal-start base cost of USD 70 and market cost index 1.0:

| Supplier | Price index | RM unit price | Normal lead | On time: Low / Moderate / High |
|---|---:|---:|---:|---|
| Economy | 80 | USD 25.20 | 2 rounds | 90% / 75% / 55% |
| Standard | 100 | USD 31.50 | 1 round | 97% / 92% / 85% |
| Reliable | 115 | USD 36.22 | 1 round | 99.5% / 99% / 98% |

The existing currency rounding convention is retained. Material-cost pressure
scales unit prices, not the fixed order fee. Prices retain the model's existing
supplier quality differences.

| Supplier / Risk | No delay | +1 round | +2 rounds |
|---|---:|---:|---:|
| Economy / Low | 90% | 10% | 0% |
| Economy / Moderate | 75% | 20% | 5% |
| Economy / High | 55% | 30% | 15% |
| Standard / Low | 97% | 3% | 0% |
| Standard / Moderate | 92% | 8% | 0% |
| Standard / High | 85% | 13% | 2% |
| Reliable / Low | 99.5% | 0.5% | 0% |
| Reliable / Moderate | 99% | 1% | 0% |
| Reliable / High | 98% | 2% | 0% |

Orders placed in round R normally arrive in R + normal lead. Reliable always
arrives by R + 2. Risk changes the delay distribution, not the normal lead.
Each supplier's units arrive separately and join the common RM pool. Whole units
are allocated using largest remainders, with a stable supplier-order tie-break.

## Ordering and Holding Costs

- USD 300 base order fee plus USD 75 for each additional supplier with a positive
  allocated quantity in that round.
- Zero quantity incurs no fee. One supplier costs USD 300; two USD 375; three USD 450.
- The single total is allocated evenly across active supplier shipments for
  reporting: USD 187.50 each for two suppliers, USD 150 each for three. These are
  fee shares, not separate additional charges. Rounding remainders use supplier order.
- Existing version-1 games retain their original USD 300 per supplier rule.
- Replacing a saved submission is not another purchase. The final round plan
  determines the purchase and fee once when the round runs.
- Procurement includes material purchases plus these fees. The fee is separately
  reported as `ordering_cost`, a component of procurement, not an additional cost.
- No second fee on receipt, no material expedite option, and no quantity discount.
- Existing holding rates remain RM USD 2 per ending on-hand RM unit and FG USD 6
  per ending finished paddle, per round. In-transit units have no warehouse fee.

The 1:3 RM-to-FG holding-cost ratio is a useful classroom abstraction: finished
paddles embody materials and conversion and face product obsolescence. The rates
are intentionally strong incentives, not validated storage-cost estimates.
For illustration, 100 RM units cost USD 200 to hold for a round; 100 paddles cost
USD 600. At 150 extra RM units, one extra round of holding equals one USD 300
order fee. Larger orders can reduce ordering frequency but do not automatically
minimize total cost. Supplier delays, shortages, quality and tied-up cash matter.

The existing game expenses purchases when ordered, not GAAP inventory/COGS.
Buying ahead therefore lowers current-round profit as well as cash. Compare
multi-round outcomes and remaining stock when debriefing purchasing strategies.

## Reproducibility and Visibility

A private, persisted classroom seed generates one outcome per supplier and order
round. All teams in that classroom receive the same supplier disruption; it is
not a separate lottery per student. Risk is fixed when an order is placed.
Previewing, refreshing, or re-running the same inputs cannot reroll delivery.

Students see normal arrival, possible range, on-time probability at ordering,
and confirmed current arrivals. Future realized dates and the seed are withheld
from the decision screen, tracker and student results. Admin backups preserve
the seed and shipment metadata for replay. Admin Excel includes fees and shipment
details but excludes the seed. Backups and admin exports remain restricted files.

## Local Verification

Use the sibling `Kiki_Business_Simulation/.venv/Scripts/python.exe` runtime:

```text
scripts/preview_probabilistic_sourcing.py
scripts/test_probabilistic_sourcing.py
scripts/test_sourcing_controls.py
scripts/test_material_requirements.py
scripts/test_game_exports.py
```

The fictional student is `demo_022_1`, classroom `022 (Local Demo)`, password
`PreviewOnly123!`. The fictional administrator is `export_admin` with the same
demo-only password. The launcher selects an unused port starting at 8550 and
prints the URL and new database path. These are not production credentials.
