# Pickleball Paddle Simulator - Detailed Stage C Word Bundle

This document is a Word-friendly, copy-and-pasteable project handoff for the
current simulator codebase.

It is intentionally written as a long-form architecture and code summary so you
can:

- paste it into Word as project documentation
- give it to another GPT as project context
- use it as a technical brief for future upgrades
- understand the current business model, data model, engine logic, and UI flow

This is a summary bundle, not a raw full-code dump. It explains the code in
detail, points to the important files and functions, and describes the formulas
and data structures that currently drive the simulator.

========================================================================
1. PROJECT IDENTITY
========================================================================

Project name:
- Pickleball Paddle Simulator

Project type:
- Python classroom simulation app
- Streamlit multipage web UI
- SQLite persistence
- hosted-ready single-instance deployment
- role-based access with `admin` and `team_leader`

Current realism stage:
- quantitative OM/SCM core
- Stage A active portfolio and lifecycle
- Stage B product development pipeline, technology generations, delayed
  launches, retirement/replacement, and intra-team cannibalization
- Stage C product-level forecasting, S&OP discipline, cash control, borrowing,
  interest, and liquidity pressure

Current intended usage:
- one central hosted app instance
- admin/instructor creates accounts and runs rounds
- each team leader logs in from their own browser
- the simulation runs in repeated classroom rounds

Still intentionally excluded:
- marketing
- ambassador strategy
- `team_member` role
- retailer/channel negotiation
- multi-country operations
- Monte Carlo-heavy randomness
- full accounting statements
- taxes or equity financing

========================================================================
2. WHAT THE GAME MODULE IS
========================================================================

The simulator is now a multi-round classroom business game where each team runs
a pickleball paddle company.

The company is not modeled as one blended generic product anymore. Instead, the
team manages:

- a shared firm-level operating system
- an active product portfolio with up to 3 product slots
- a small innovation pipeline with up to 2 development projects
- lifecycle progression and product aging
- technology-generation transitions
- retirement/replacement decisions
- product-level demand competition
- product-level forecasting and S&OP discipline
- cash, debt, and liquidity pressure

So the simulator now behaves like:

- an operations management game
- a supply chain planning game
- a product portfolio management game
- a new product development timing game
- a forecast-vs-plan discipline game
- a simple financial control game

In short:
- students are running a small paddle business, not just entering one
  production number

========================================================================
3. CURRENT ARCHITECTURE
========================================================================

The project was not rebuilt from scratch. The existing architecture was
preserved and extended.

Main folders and files:

- `app.py`
  Home page and top-level framing

- `pages/`
  Streamlit multipage UI

- `models/schemas.py`
  Typed dataclasses and JSON/SQLite-friendly model serialization

- `engine/config.py`
  Tunable constants used by the round engine

- `engine/simulator.py`
  Main round engine, preview logic, validation logic, aggregation logic

- `utils/database.py`
  SQLite schema creation and additive migrations

- `utils/repository.py`
  Repository helpers for loading/saving application state

- `utils/auth.py`
  Auth/session helpers and page guards

- `utils/security.py`
  Password hashing and verification

- `utils/bootstrap.py`
  App/bootstrap initialization

- `data/defaults.py`
  Default market report and seeded archetype portfolio templates

- `README.md`
  Local run, hosted deployment, workflow, and model overview

The architecture still supports:

- local development and local testing
- one hosted deployment with a public URL
- SQLite-backed persistence
- role-based page behavior

========================================================================
4. ROLE MODEL
========================================================================

The simulator currently supports exactly two roles:

- `admin`
- `team_leader`

`admin` can:
- create and manage users
- edit the public market report
- review submissions
- run rounds
- reset runtime data
- see all team-level and product-level details

`team_leader` can:
- log in with their own team account
- view the public market report
- submit only their own team decisions
- view their own team results in detail
- view safe public ranking tables

`team_leader` cannot:
- run rounds
- reset state
- manage users
- impersonate another team

========================================================================
5. EVOLUTION OF THE SIMULATOR
========================================================================

The simulator has evolved in layers.

Initial version:
- one local app
- simple placeholder results

OM/SCM version:
- real quantitative round engine
- supplier mix
- raw materials
- capacity
- QC
- backlog

Stage A:
- up to 3 active product slots per team
- product lifecycle
- product-level demand allocation
- product-level results
- team-level rollup

Stage B:
- up to 2 development projects per team
- delayed launches
- technology generations
- launch readiness
- retirement and replacement
- intra-team cannibalization

Stage C:
- product-level forecasts
- forecast accuracy tracking
- S&OP discipline warnings
- cash and working-capital pressure
- planned borrowing plus automatic residual borrowing
- interest expense
- liquidity stress indicators

========================================================================
6. CURRENT GAMEPLAY LAYERS
========================================================================

The current simulator contains five major business layers:

1. Firm-level operations
- overtime
- capacity expansion
- raw-material ordering
- supplier mix
- expedited share
- backlog limit
- planned borrowing

2. Product-level active portfolio management
- product activation
- product name
- target segment
- price
- forecast
- production
- QC spend
- target FG inventory
- retirement flag

3. Development pipeline management
- future project definition
- segment target
- tech target
- planned launch timing
- investment
- testing intensity
- launch-now decision
- cancel decision

4. Market competition logic
- all active products from all teams compete for demand
- lifecycle and technology matter
- reputation matters
- cannibalization matters

5. Finance and planning discipline
- forecast vs actual demand
- forecast vs production mismatch
- cash balance
- short-term debt
- interest expense
- working-capital burden
- liquidity stress

========================================================================
7. CORE FILES TO UNDERSTAND FIRST
========================================================================

If another developer or GPT needs to understand the repo quickly, these are the
first files to inspect:

- `models/schemas.py`
- `utils/database.py`
- `utils/repository.py`
- `engine/config.py`
- `engine/simulator.py`
- `pages/2_Team_Decisions.py`
- `pages/3_Instructor_Panel.py`
- `pages/4_Results_Dashboard.py`
- `README.md`

Why these matter:

`models/schemas.py`
- defines what the simulator "knows"

`utils/database.py`
- defines what is persisted in SQLite and how old DBs migrate

`utils/repository.py`
- defines how pages and engine talk to the DB

`engine/config.py`
- contains the most important tunable numbers

`engine/simulator.py`
- contains the business logic

`pages/2_Team_Decisions.py`
- shows what the student/team actually inputs

`pages/3_Instructor_Panel.py`
- shows how the round is executed

`pages/4_Results_Dashboard.py`
- shows what output is exposed to admin vs team leader

========================================================================
8. MAIN DATABASE TABLES
========================================================================

The current SQLite schema includes these key tables:

- `users`
- `team_archetypes`
- `market_reports`
- `team_decisions`
- `product_lines`
- `product_decisions`
- `product_development_projects`
- `product_forecasts`
- `team_states`
- `round_results`
- `product_round_results`
- `forecast_accuracy_results`

What each table stores:

`users`
- username
- password hash
- role
- team assignment
- active flag

`team_archetypes`
- baseline firm identity
- cost/capacity/reputation/defect baseline
- segment-fit values
- suggested product templates

`market_reports`
- public round conditions
- technology environment

`team_decisions`
- shared firm-level decisions by round

`product_lines`
- persistent slot state across rounds

`product_decisions`
- round submission for each product slot

`product_development_projects`
- persistent NPD pipeline state

`product_forecasts`
- submitted product-level forecast values by round

`team_states`
- persistent cross-round business state

`round_results`
- aggregate team-level round outputs

`product_round_results`
- product-slot round outputs

`forecast_accuracy_results`
- per-product forecast-vs-actual diagnostics

========================================================================
9. MAIN PYTHON DATA MODELS
========================================================================

The main typed data structures live in `models/schemas.py`.

Important current dataclasses:

- `MarketReport`
- `AppUser`
- `ProductTemplate`
- `TeamArchetype`
- `ProductLine`
- `TeamDecision`
- `ProductDecision`
- `ProductDevelopmentProject`
- `OpenMaterialOrder`
- `ProductForecast`
- `ForecastAccuracyResult`
- `ProductRoundResult`
- `RoundResult`
- `PersistentTeamState`

These dataclasses are central because:
- repository helpers serialize and deserialize them
- the engine reads and returns them
- pages use them to render forms and tables

========================================================================
10. MARKET REPORT MODEL
========================================================================

`MarketReport` contains the public market environment for the round.

Core demand and cost fields:
- `round_number`
- `total_demand`
- `premium_share`
- `mid_share`
- `beginner_share`
- `material_cost_index`
- `supply_risk`
- `quality_sensitivity`
- `event`

Technology and market-transition fields:
- `current_market_generation`
- `technology_shift_rate`
- `premium_tech_adoption`
- `mid_market_tech_adoption`
- `beginner_price_pressure`

Why it matters:
- demand is split by segment using the segment shares
- supply risk influences sourcing and defects
- material cost index changes procurement cost
- quality sensitivity changes reputation consequences
- market generation and adoption shape product attractiveness

========================================================================
11. TEAM ARCHETYPES
========================================================================

`TeamArchetype` still exists, but it is no longer the main gameplay mechanism.

It now mainly provides baseline firm characteristics and suggested defaults.

Key fields:
- `base_cost`
- `base_capacity`
- `base_reputation`
- `base_defect_rate`
- `premium_fit`
- `mid_fit`
- `beginner_fit`

Suggested-default fields:
- `suggested_overtime_capacity_units`
- `suggested_capacity_expansion_units`
- `suggested_max_backorder_units`
- `suggested_raw_material_order_qty`
- `suggested_supplier_mix_offshore_pct`
- `suggested_supplier_mix_balanced_pct`
- `suggested_supplier_mix_premium_pct`
- `suggested_expedited_order_share_pct`
- `suggested_product_templates`

Archetypes now matter because they influence:
- cost baseline
- defect baseline
- capacity baseline
- segment competitiveness
- starting portfolio shape

========================================================================
12. PRODUCT TEMPLATE MODEL
========================================================================

`ProductTemplate` is the archetype-level default template for one active product
slot.

Important fields:
- `slot_name`
- `product_name`
- `is_active`
- `target_segment`
- `lifecycle_stage`
- `age_in_rounds`
- `base_defect_rate_modifier`
- `base_demand_fit_modifier`
- `suggested_selling_price_per_unit`
- `suggested_planned_production_units`
- `suggested_qc_budget_per_unit`
- `suggested_target_finished_goods_inventory`
- `tech_generation`
- `cannibalization_group`

This is how different archetypes can start with different portfolio structures
without hardcoding one strategy into the engine.

========================================================================
13. PRODUCT LINE MODEL
========================================================================

`ProductLine` is the persistent state of one active or inactive slot across
rounds.

Key fields:
- `product_id`
- `team_name`
- `product_name`
- `slot_name`
- `is_active`
- `target_segment`
- `lifecycle_stage`
- `age_in_rounds`
- `base_defect_rate_modifier`
- `base_demand_fit_modifier`
- `tech_generation`
- `cannibalization_group`
- `launch_round`
- `retirement_flag`
- `retired_round`
- `replacement_project_id`
- `inventory_units`
- `backlog_units`

What it represents:
- the persistent identity and state of a product slot

What changes round to round:
- age
- lifecycle stage
- inventory
- backlog
- retirement status
- product name if replaced

========================================================================
14. TEAM DECISION MODEL
========================================================================

`TeamDecision` stores the shared firm-level decisions for a round.

Current fields:
- `team_name`
- `archetype`
- `overtime_capacity_units`
- `capacity_expansion_units`
- `raw_material_order_qty`
- `supplier_mix_offshore_pct`
- `supplier_mix_balanced_pct`
- `supplier_mix_premium_pct`
- `expedited_order_share_pct`
- `max_backorder_units`
- `planned_borrowing_amount`

This model still includes compatibility logic from older stages:
- legacy categorical fields can still be mapped if old rows exist

Important helper methods:
- `supplier_mix_total()`
- `supplier_mix_valid()`
- `normalized_supplier_mix()`

========================================================================
15. PRODUCT DECISION MODEL
========================================================================

`ProductDecision` is the active round submission for one product slot.

Current fields:
- `product_id`
- `team_name`
- `slot_name`
- `product_name`
- `is_active`
- `target_segment`
- `selling_price_per_unit`
- `forecast_units`
- `planned_production_units`
- `qc_budget_per_unit`
- `target_finished_goods_inventory`
- `retire_flag`

This is now the main student-facing product decision object.

It connects directly to:
- forecast discipline
- product-level demand competition
- production planning
- QC and defect control
- inventory positioning
- retirement timing

========================================================================
16. DEVELOPMENT PROJECT MODEL
========================================================================

`ProductDevelopmentProject` is the persistent NPD pipeline object.

Current fields:
- `project_id`
- `team_name`
- `project_slot_name`
- `project_name`
- `target_segment`
- `target_tech_generation`
- `intended_slot_name`
- `required_investment`
- `cumulative_investment`
- `investment_this_round`
- `testing_intensity`
- `launch_readiness_score`
- `planned_launch_round`
- `earliest_launch_round`
- `status`
- `cannibalization_group`
- `projected_base_defect_modifier`
- `projected_demand_fit_modifier`
- `created_round`
- `launched_round`
- `canceled_round`
- `launch_now`
- `cancel_now`
- `replaced_product_name`

Helper methods:
- `is_defined()`
- `is_pipeline_active()`
- `is_launch_ready(round_number)`

========================================================================
17. PRODUCT FORECAST MODEL
========================================================================

Stage C added `ProductForecast`.

Fields:
- `round_number`
- `team_name`
- `product_id`
- `slot_name`
- `product_name`
- `forecast_units`

Purpose:
- store the submitted product-level demand forecast separately from the rest of
  the product decision structure
- make forecast persistence explicit
- support dashboard history and future extensions

========================================================================
18. FORECAST ACCURACY RESULT MODEL
========================================================================

Stage C added `ForecastAccuracyResult`.

Fields:
- `round_number`
- `team_name`
- `product_id`
- `slot_name`
- `product_name`
- `forecast_units`
- `actual_demand_units`
- `actual_sales_units`
- `forecast_error_units`
- `absolute_error_units`
- `forecast_bias_pct`
- `mape_or_wape_value`

Purpose:
- persist product-level forecast diagnostics after each round

========================================================================
19. PRODUCT ROUND RESULT MODEL
========================================================================

`ProductRoundResult` is the round output for one product slot.

Important fields now include:
- product identity
- target segment
- lifecycle stage
- age
- tech generation
- price
- forecast units
- planned production
- actual production
- defect rate
- good units produced
- demand allocated
- actual demand units
- sales units
- lost sales units
- ending inventory
- fill rate
- forecast error metrics
- revenue
- production cost
- holding cost
- warranty cost
- allocated procurement cost
- allocated backlog cost
- allocated expansion cost
- contribution margin per unit
- profit contribution
- beginning inventory
- backlog start/end
- tech-gap metrics
- cannibalization in/out
- launch/retirement flags
- notes

This object is the most detailed record of what happened to one product in one
round.

========================================================================
20. TEAM ROUND RESULT MODEL
========================================================================

`RoundResult` is the aggregate team-level round summary.

Stage C fields now include:

Portfolio and innovation context:
- `active_product_count`
- `active_project_count`
- `launch_ready_project_count`
- `launched_project_count`
- `retired_product_count`

Forecast and planning metrics:
- `total_forecast_units`
- `total_actual_demand_units`
- `forecast_error_units`
- `absolute_forecast_error_units`
- `forecast_wape`
- `service_gap_units`

Operating metrics:
- `weighted_average_selling_price`
- `planned_production_units`
- `actual_production_units`
- `effective_capacity_units`
- `utilization_pct`
- `weighted_material_unit_cost`
- `defect_rate`
- `good_units_produced`
- `demand_allocated`
- `sales_units`
- `lost_sales_units`
- `backlog_units_end`
- `ending_inventory`
- `ending_raw_material_inventory`
- `fill_rate`

Financial metrics:
- `revenue`
- `procurement_cost`
- `production_cost`
- `holding_cost`
- `warranty_cost`
- `backlog_cost`
- `expansion_cost`
- `innovation_investment`
- `interest_expense`
- `working_capital_requirement`
- `planned_borrowing_amount`
- `automatic_borrowing_amount`
- `ending_cash_balance`
- `short_term_debt_balance`
- `liquidity_stress_flag`
- `total_cost`
- `profit`
- `contribution_margin_per_unit`

Strategic context:
- `reputation_after_round`
- `average_portfolio_tech_generation`
- `cannibalized_demand_units`
- `launch_events_text`
- `notes`

========================================================================
21. PERSISTENT TEAM STATE MODEL
========================================================================

`PersistentTeamState` carries the cross-round state of the business.

Current fields:
- `team_name`
- `archetype`
- `cash_balance`
- `inventory_units`
- `raw_material_inventory`
- `backlog_units`
- `capacity_units`
- `reputation_score`
- `completed_rounds`
- `last_decision`
- `open_material_orders`
- `cumulative_profit`
- `short_term_debt_balance`
- `interest_expense_last_round`
- `liquidity_warning_flag`
- `working_capital_stress_score`

This is where Stage C becomes truly persistent.

It means debt, cash, and liquidity pressure are not one-round temporary numbers.

========================================================================
22. SQLITE MIGRATION STRATEGY
========================================================================

The app still uses additive SQLite migrations in `utils/database.py`.

That means:
- the schema is created via `SCHEMA_SQL`
- older DBs are upgraded with `_ensure_columns(...)`
- the app avoids destructive rebuilds by default

Stage C added:
- new tables:
  - `product_forecasts`
  - `forecast_accuracy_results`
- new columns on:
  - `team_decisions`
  - `product_decisions`
  - `team_states`
  - `round_results`
  - `product_round_results`

This keeps older classroom data more compatible.

========================================================================
23. REPOSITORY LAYER RESPONSIBILITIES
========================================================================

The repository layer in `utils/repository.py` is the main boundary between UI,
engine, and SQLite.

Important responsibilities:

- load/save market reports
- load/save team archetypes
- load/save team decisions
- load/save product lines
- load/save product decisions
- load/save development projects
- load/save product forecasts
- load/save round results
- load/save product round results
- load/save forecast accuracy results
- load/save persistent team states
- reset runtime data

Important Stage C additions:
- `load_product_forecasts(...)`
- `save_product_forecasts(...)`
- `load_forecast_accuracy_results(...)`
- `save_forecast_accuracy_results(...)`

The repository layer also handles:
- legacy compatibility fields
- JSON fields inside `team_states`
- DB-friendly bool/integer conversion

========================================================================
24. ENGINE CONFIG CONSTANTS
========================================================================

The main tunable constants are in `engine/config.py`.

Major groups of constants:

Portfolio and market:
- product slots
- project slots
- segments
- lifecycle stages
- technology generations

Demand competitiveness:
- segment reference prices
- segment price tolerances
- segment quality multipliers
- product-segment alignment
- lifecycle demand multipliers
- lifecycle price-tolerance multipliers

Supply chain:
- supplier material-cost multipliers
- supplier lead times
- supplier defect pressure
- supplier risk exposure
- supply-risk index
- expedited-order cost uplift
- expedited-order lead-time reduction

Operations:
- material/conversion cost shares
- overtime cost multiplier
- overtime defect penalty
- capacity expansion capex
- QC diminishing-returns parameters
- holding cost
- raw-material holding cost
- warranty cost
- backlog penalty

Technology and launch:
- tech gap bonuses/penalties
- launch defect penalty
- launch novelty bonus
- launch readiness threshold
- NPD required investment constants

Cannibalization:
- base cannibalization rate
- same-group factor
- same-segment factor
- lifecycle-gap factor
- tech-advantage factor
- transfer cap

Stage C finance and planning:
- `PERIODIC_INTEREST_RATE`
- `LIQUIDITY_LOW_CASH_THRESHOLD`
- `DEBT_TO_REVENUE_STRESS_THRESHOLD`
- `WORKING_CAPITAL_TO_REVENUE_STRESS_THRESHOLD`
- `LIQUIDITY_STRESS_REPUTATION_PENALTY`
- `FORECAST_LOW_COVERAGE_RATIO`
- `FORECAST_EXCESS_PRODUCTION_RATIO`
- `FORECAST_MISMATCH_WARNING_RATIO`

========================================================================
25. ENGINE ENTRY POINTS
========================================================================

The main engine file is `engine/simulator.py`.

Important externally used functions:

- `run_round(...)`
- `preview_team_decision(...)`
- `build_round_validation_rows(...)`

`run_round(...)`
- executes the actual classroom round

`preview_team_decision(...)`
- powers the live analytics on the Team Decisions page

`build_round_validation_rows(...)`
- powers the Instructor Panel pre-run summary

========================================================================
26. MAIN ROUND FLOW
========================================================================

The current `run_round(...)` logic is roughly:

1. load archetypes
2. initialize or load persistent team state
3. ensure each team has its product slots
4. resolve submitted product decisions
5. resolve submitted development projects
6. compute weighted supplier metrics
7. receive inbound raw-material orders
8. progress development projects
9. apply eligible launches and replacements
10. determine shared firm capacity and material feasibility
11. proportionally cap product production if needed
12. compute product defect rates
13. allocate product demand across all products from all teams
14. apply intra-team cannibalization
15. finalize product sales, backlog, lost sales, inventory, and costs
16. compute per-product forecast-vs-actual metrics
17. aggregate results to team level
18. compute team-level cash, debt, working capital, and liquidity stress
19. update persistent team state
20. update product lines
21. update development projects
22. return:
   - team results
   - product results
   - updated team states
   - updated product lines
   - updated projects
   - forecast accuracy results

========================================================================
27. PREVIEW FLOW
========================================================================

The Team Decisions page uses `preview_team_decision(...)`.

That function does two things:

1. builds a prepared team-level planning snapshot directly from the candidate
   decision
2. runs a simulated round using the current market and other saved teams so the
   submitting team can see likely outcomes before saving

This is how the app shows:
- product-level preview rows
- pipeline preview rows
- forecast-production gap
- projected feasible production
- projected ending inventory if forecast is right
- projected working capital
- projected cash before borrowing
- likely borrowing need
- warnings

========================================================================
28. VALIDATION FLOW
========================================================================

The Instructor Panel uses `build_round_validation_rows(...)`.

This function does not block the round. It produces diagnostics such as:

- active product count
- zero active portfolio flag
- supplier mix total
- supplier mix valid flag
- total forecast units
- total planned production
- forecast-production gap
- effective capacity
- projected max feasible production
- obvious infeasibility
- missing forecasts
- forecast-plan mismatch
- likely cash shortfall
- pipeline project count
- launch-ready projects
- launch requests
- multiple launch request flag

========================================================================
29. SUPPLIER AND MATERIAL LOGIC
========================================================================

Supplier mix is numeric, not categorical at runtime.

The engine computes weighted supplier metrics using the team-level supplier mix:

Weighted material unit cost:
- supplier mix weights
- supplier cost multipliers
- base cost
- material cost index
- expedited uplift

Weighted lead time:
- supplier base lead times
- supply risk adjustment
- expedited lead-time reduction

Weighted defect pressure:
- weighted by supplier mix

Weighted supply risk exposure:
- weighted by supplier mix

These are shared firm-level sourcing metrics applied across the portfolio.

========================================================================
30. PRODUCTION AND SHARED FIRM CONSTRAINTS
========================================================================

Capacity and raw materials remain shared at the team level.

The engine determines:

- installed capacity
- overtime-adjusted effective capacity
- beginning raw-material inventory
- inbound raw-material receipts
- total raw-material availability

Each team can submit product-level planned production by slot, but the sum
across products is constrained by:

- effective capacity
- raw-material availability

If product plans exceed the firm constraint:
- production is proportionally capped

This means a team is managing a true shared system, not three independent
products.

========================================================================
31. PRODUCT DEFECT LOGIC
========================================================================

Product defect rate is computed from a transparent combination of:

- archetype base defect rate
- product base defect modifier
- supplier defect pressure
- supply-risk exposure
- utilization stress
- overtime penalty
- launch instability penalty
- technology novelty penalty
- QC reduction

QC reduction uses diminishing returns.

The general shape is:
- more QC spend helps
- but the marginal benefit tapers off

That keeps QC from being a trivial "spend to zero defects" slider.

========================================================================
32. LIFECYCLE RULES
========================================================================

Lifecycle stages are still rule-based:

- `launch`: age `0-1`
- `growth`: age `2-3`
- `maturity`: age `4-6`
- `decline`: age `7+`

Lifecycle affects:
- demand attractiveness
- price tolerance
- defect behavior
- cannibalization dynamics

Launch and growth are more attractive.
Decline carries drag.

========================================================================
33. TECHNOLOGY GENERATION RULES
========================================================================

Products and projects use integer technology generations:
- `Gen 1`
- `Gen 2`
- `Gen 3`
- `Gen 4`

The market also has:
- `current_market_generation`

Technology matters because:
- products older than the market lose attractiveness
- newer products can gain attractiveness
- premium and mid segments care more than beginner
- very new products can carry extra launch/novelty defect pressure

The effect is bounded. Old products are penalized gradually, not made worthless
instantly.

========================================================================
34. NPD PIPELINE AND LAUNCH READINESS
========================================================================

Projects do not launch immediately.

The engine computes:
- required investment
- cumulative investment progress
- testing contribution
- tech complexity penalty
- readiness score
- earliest launch round

A project becomes launch-ready only if:
- cumulative investment meets required investment
- readiness score exceeds threshold
- current round is at or after earliest launch round

Even then:
- the team still has to request `launch_now`

The engine also limits:
- max 1 launch per team per round

========================================================================
35. RETIREMENT AND REPLACEMENT
========================================================================

Products can be retired manually via `retire_flag`, or replaced when a new
project launches into a slot.

Retirement behavior:
- inventory is liquidated at a markdown recovery rate
- backlog is not carried forever on a retired line
- retired products stop competing after retirement

Replacement behavior:
- launched project takes over the slot
- new product starts at:
  - age `0`
  - lifecycle `launch`
  - project tech generation
  - project defect modifier
  - project demand-fit modifier

========================================================================
36. CANNIBALIZATION LOGIC
========================================================================

Cannibalization is modeled after initial market demand allocation.

Demand can shift from an older product to a newer sibling if:
- both belong to the same team
- receiver is newer/stronger or recently launched
- donor is more mature/declining
- same segment or same cannibalization group increases overlap
- tech advantage increases the transfer rate

This is bounded by a conservative transfer cap to avoid wild swings.

Stored results include:
- `cannibalization_in_units`
- `cannibalization_out_units`
- team-level `cannibalized_demand_units`

========================================================================
37. PRODUCT-LEVEL DEMAND ALLOCATION
========================================================================

Demand is allocated at the product level across all teams.

First, market demand is split into:
- premium
- mid
- beginner

Then each active product competes in each segment using an attractiveness score
built from:

- selling price versus segment reference price
- product target-segment alignment
- archetype segment fit
- product demand-fit modifier
- lifecycle multiplier
- technology attractiveness modifier
- team reputation
- service readiness
- launch novelty if newly launched

This means:
- demand is no longer allocated just to a team
- a specific product can win or lose in its own segment

========================================================================
38. PRODUCT-LEVEL FORECASTING
========================================================================

Stage C adds product-level forecasting.

Each active product slot submits:
- `forecast_units`

This creates a formal forecast that is separate from:
- planned production
- target inventory
- raw-material ordering

This is the beginning of real S&OP behavior:
- teams must estimate demand before they build

========================================================================
39. FORECAST METRICS
========================================================================

After demand is realized, the engine computes:

For each product:
- `forecast_error_units = actual_demand_units - forecast_units`
- `absolute_error_units = abs(actual_demand_units - forecast_units)`
- `forecast_bias_pct = forecast_error_units / max(forecast_units, 1)`
- `mape_or_wape_value = absolute_error_units / max(actual_demand_units, 1)`

For each team:
- `total_forecast_units`
- `total_actual_demand_units`
- `forecast_error_units`
- `absolute_forecast_error_units`
- `forecast_wape`

Current team WAPE logic:
- `sum(abs error) / max(sum actual demand), 1`

========================================================================
40. S&OP DISCIPLINE LOGIC
========================================================================

The simulator now checks forecast coherence against planning choices.

Examples of current warnings:
- forecast significantly above production
- production significantly above forecast
- raw-material ordering too low relative to production
- target FG inventory too high relative to forecast
- likely cash shortfall before borrowing

These warnings appear:
- in the Team Decisions live preview
- in the Instructor Panel validation summary

The round is not hard-blocked for these planning errors.
They are surfaced as warnings and consequences instead.

========================================================================
41. CASH LOGIC
========================================================================

Stage C makes `cash_balance` a real control variable.

The current round cash flow uses:

Starting cash
+ planned borrowing
+ revenue
- procurement cost
- production conversion cost
- holding cost
- warranty cost
- backlog cost
- expansion cost
- development investment
- interest expense

The engine computes:
- ending cash before borrowing
- automatic borrowing if cash would go negative
- final ending cash

This is intentionally simple and classroom-manageable.

No full statements are built.

========================================================================
42. BORROWING LOGIC
========================================================================

Borrowing has two layers:

1. planned borrowing
- entered by the team in `planned_borrowing_amount`

2. automatic residual borrowing
- if ending cash would still be negative, the engine automatically borrows the
  remaining deficit

That means the team can:
- proactively borrow
- or rely on emergency borrowing if their plan is too aggressive

Interest expense is currently modeled simply:
- debt balance times a periodic interest rate

========================================================================
43. WORKING CAPITAL AND LIQUIDITY
========================================================================

Working capital is intentionally simplified.

Current working-capital burden includes:
- finished-goods inventory value
- raw-material inventory value
- a light burden from short-term debt

Liquidity stress is flagged from combinations of:
- low ending cash
- high debt relative to revenue
- high working-capital burden relative to revenue
- repeated borrowing

Current effects:
- dashboard warning visibility
- persistent team-state warning flag
- modest reputation penalty when liquidity stress is severe

The penalty is intentionally not too harsh.

========================================================================
44. TEAM DECISIONS PAGE
========================================================================

The main team submission UI is `pages/2_Team_Decisions.py`.

Current sections:

1. Team Identity
- team selection or assigned team display
- archetype selection/lock behavior

2. Current Team State
- installed capacity
- FG inventory
- raw-material inventory
- backlog
- reputation
- cash balance
- short-term debt
- last-round interest expense
- tech position vs market

3. Firm-Level Operations and Finance
- overtime capacity
- capacity expansion
- max backorder
- raw-material order quantity
- expedited share
- planned borrowing amount
- supplier mix

4. Active Product Portfolio and Forecasts
- three product-slot cards
- product name
- active flag
- target segment
- retire after round
- selling price
- forecast units
- planned production
- QC budget
- target FG inventory

5. Development Pipeline
- two project cards
- project name
- target segment
- target tech generation
- intended slot
- planned launch round
- investment this round
- testing intensity
- cannibalization group
- projected defect modifier
- projected demand-fit modifier
- launch now
- cancel

6. Planning Analytics Preview
- total forecast units
- effective capacity
- total planned production
- forecast-production gap
- utilization
- projected feasible output
- projected ending FG inventory if forecast hits
- raw-material sufficiency
- weighted lead time
- weighted material cost
- projected defect rate
- projected weighted margin
- projected innovation spend
- projected working capital
- projected cash before borrowing
- likely borrowing need
- launch-ready projects
- products in decline
- likely cannibalization
- warning banners
- scenario tables

========================================================================
45. INSTRUCTOR PANEL
========================================================================

The admin round-control page is `pages/3_Instructor_Panel.py`.

Its job is now:
- review submissions
- review planning/feasibility risks
- run the round
- reset runtime data when needed

Current summary metrics:
- current round
- teams submitted
- invalid supplier mix count
- infeasible plan count
- missing forecasts count
- forecast mismatch count
- likely cash shortfall teams
- pipeline project count
- launch-ready project count

Current detail tables:
- validation detail
- saved firm decisions
- saved product decisions
- saved development projects
- current portfolio snapshot

When the round runs, the panel saves:
- team round results
- product round results
- forecast accuracy results
- updated team states
- updated product lines
- updated development projects

========================================================================
46. RESULTS DASHBOARD
========================================================================

The main results page is `pages/4_Results_Dashboard.py`.

Admin view now includes tabs:
- Team Summary
- Forecast Accuracy
- Product Detail
- Liquidity / Debt
- Portfolio Snapshot
- Development Pipeline
- Launch / Retirement Log

Team leader view now includes:
- Team Summary
- Forecast Accuracy
- Active Portfolio
- Development Pipeline
- Product Results
- Launch / Retirement Log

Admin can see:
- all teams
- full product tables
- forecast accuracy ranking
- debt/liquidity summary
- persistent state

Team leader sees:
- own forecast-vs-actual rows
- own product results
- own team aggregate result
- own team state
- safe public rankings

========================================================================
47. HOME PAGE
========================================================================

`app.py` is still a lightweight home page, but it has been updated to describe
the current simulator stage.

It now communicates that the app supports:
- portfolio and pipeline logic
- technology generations
- cannibalization
- forecasting
- cash/debt/liquidity logic

This is helpful because the home page acts as onboarding for both admin and
team leaders.

========================================================================
48. AUTHENTICATION AND SECURITY
========================================================================

Auth is preserved.

The app still uses:
- custom username/password login
- password hashing
- session-based authenticated state
- role-based page guards

Security behavior:
- passwords are never stored in plain text
- old passwords cannot be displayed later
- team leaders cannot submit for another team
- admin-only pages are protected

This Stage C work did not redesign auth.

========================================================================
49. HOSTING AND STORAGE MODEL
========================================================================

The app still supports:
- local run via Streamlit
- one hosted public URL

Storage remains:
- SQLite

Configuration still supports:
- `SIMULATOR_DB_PATH`
- `SIMULATOR_DATA_DIR`
- `SIMULATOR_ENV`
- hosted disk path fallback

This means:
- local testing and hosted deployment use the same core codebase

========================================================================
50. TESTING AND VERIFICATION STATUS
========================================================================

The Stage C pass was verified with:

- Python compile check:
  - `python -m compileall app.py engine models pages utils`

- Stage C engine smoke test:
  - temporary SQLite DB
  - saved forecasts
  - round execution
  - forecast accuracy persistence
  - cash and debt update

- headless Streamlit startup test:
  - verified HTTP 200

This gives reasonable confidence that:
- models compile
- repository changes work
- engine returns Stage C outputs
- UI still boots

========================================================================
51. CURRENT LIMITATIONS AND SIMPLIFICATIONS
========================================================================

What is still intentionally simplified:

- no marketing
- no ambassador logic
- no team_member role
- no retailer/channel negotiation
- no country-specific operations
- no Monte Carlo-heavy demand uncertainty
- no taxes
- no equity issuance
- no AP/AR aging
- no full balance sheet or P&L statement
- no detailed procurement contract model
- max 3 active product slots
- max 2 development projects
- max 1 launch per team per round

These simplifications are deliberate so the simulator stays classroom-manageable.

========================================================================
52. WHAT STAGE C ADDED MOST RECENTLY
========================================================================

Most recent upgrade added:

- `ProductForecast` model
- `ForecastAccuracyResult` model
- `product_forecasts` table
- `forecast_accuracy_results` table
- `planned_borrowing_amount` on team decisions
- `forecast_units` on product decisions
- forecast metrics in product and team results
- debt and liquidity fields in persistent team state
- planning-preview analytics on the Team Decisions page
- liquidity and forecast summary on the Results Dashboard
- planning-risk summary in the Instructor Panel

========================================================================
53. SUGGESTED GPT HANDOFF PROMPT
========================================================================

You can paste this into another GPT if you want it to continue from the current
repo.

----------------------------------------------------------------------

I am working on an existing Python + Streamlit + SQLite classroom simulator repo.

Current architecture must be preserved:
- Streamlit multipage app
- SQLite persistence
- admin and team_leader authentication
- hosted-ready single-instance deployment

Current simulator stage:
- quantitative OM/SCM core
- Stage A active portfolio with 3 product slots
- Stage B development pipeline with 2 project slots, lifecycle, technology generations, delayed launches, retirement/replacement, and intra-team cannibalization
- Stage C product-level forecasting, S&OP discipline, cash, borrowing, interest, and liquidity pressure

Important files:
- app.py
- models/schemas.py
- data/defaults.py
- utils/database.py
- utils/repository.py
- engine/config.py
- engine/simulator.py
- pages/1_Public_Market_Report.py
- pages/2_Team_Decisions.py
- pages/3_Instructor_Panel.py
- pages/4_Results_Dashboard.py
- README.md

Current model summary:
- team-level shared firm constraints
- product-level active portfolio
- development pipeline
- lifecycle progression
- technology-generation effects
- delayed launches
- retirement and replacement
- intra-team cannibalization
- product-level demand forecasts
- forecast accuracy metrics
- cash balance, short-term debt, interest expense, working-capital burden, and liquidity stress

What is intentionally not included yet:
- marketing
- ambassador strategy
- retailer/channel negotiation
- multi-country operations
- Monte Carlo-heavy randomness
- full accounting statements

Please inspect the repo first and extend the current structure instead of redesigning it.

----------------------------------------------------------------------

========================================================================
54. FINAL NOTE
========================================================================

This document is meant to be:
- long enough to serve as a real project handoff
- structured enough to paste into Word cleanly
- detailed enough for another GPT or developer to understand the current
  simulator without reading the whole repo first

If you later want a second bundle that is even more detailed, the next step
would be:
- a file-by-file code walkthrough with pseudo-code and selected function
  explanations

If you want the full raw code itself bundled for Word, that should be created as
a separate document from the actual current source files.
