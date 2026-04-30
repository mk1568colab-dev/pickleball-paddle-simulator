# Pickleball Paddle Simulator

Hosted-ready Streamlit classroom simulator with:

- `admin` and `team_leader` accounts
- SQLite persistence
- quantitative OM/SCM gameplay
- Stage A portfolio and lifecycle logic
- Stage B development pipeline, technology generations, retirement, and cannibalization
- Stage C product-level forecasting, S&OP discipline, cash control, and borrowing
- ITE-oriented teaching support: scenario presets, submission locks, debrief diagnostics, CSV exports, and transparent formula guide
- one shared hosted app instance for classroom use

This version intentionally excludes `team_member`, marketing, ambassador strategy, retailer negotiation, multi-country operations, and Monte Carlo systems.

## Stage C Overview

Stage C upgrades the simulator from a portfolio-and-pipeline business into a portfolio-and-pipeline business that also has to forecast demand, align plans, and survive cash pressure.

Each team now manages:

- up to 3 active product slots: `A`, `B`, `C`
- up to 2 development project slots: `P1`, `P2`
- product-level demand forecasts for each active slot
- firm-level liquidity and borrowing decisions

The core Stage C ideas are:

- active products still compete in the market each round
- future products require investment before they can launch
- launch timing is delayed by readiness and earliest-launch rules
- technology generations affect market attractiveness
- older products can be retired or replaced
- newer products can cannibalize older products within the same team portfolio
- teams now submit product-level forecasts before they plan production
- the simulator now tracks forecast error, bias, and WAPE
- cash, short-term debt, interest expense, and working-capital pressure now matter

## First-Run Admin Setup

The default production workflow does not rely on shared seeded passwords.

When the app starts:

1. If there is no active `admin` account in the database, the app redirects to `Initial Setup`
2. The instructor creates the first admin account with:
   - admin username
   - admin password
   - confirm password
3. After that, normal login becomes available

The initial setup page disables itself automatically after the first active admin exists.

## Local Run

From this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open the URL Streamlit prints, usually:

```text
http://localhost:8501
```

`localhost` is for your own machine only. For classroom use across many student devices, deploy the app to one hosted URL.

## Hosted Run

This project is designed for one centrally hosted Streamlit instance. Students open that hosted URL in their browsers from school Wi-Fi, conference Wi-Fi, or cellular data.

Included host-ready files:

- `run_streamlit.py`
- `Procfile`
- `render.yaml`
- `.streamlit/config.toml`

Typical hosted startup command:

```bash
python run_streamlit.py
```

For a small host like Render:

1. Push this repo to GitHub
2. Create a web service or blueprint from the repo
3. Attach one persistent disk
4. Set a persistent SQLite path such as `/var/data/simulator.db`
5. Start the app with `python run_streamlit.py`

## Environment Variables

Supported environment variables:

- `SIMULATOR_DB_PATH`
  Sets the exact SQLite database file path
- `SIMULATOR_DATA_DIR`
  Sets the directory where `simulator.db` should be created
- `SIMULATOR_ENV`
  Use `prod` or `dev`
- `SIMULATOR_ENABLE_DEMO_ACCOUNTS`
  Only used in explicit development or demo mode
- `RENDER_DISK_PATH`
  Optional hosted disk directory fallback

Database path resolution order:

1. `SIMULATOR_DB_PATH`
2. `SIMULATOR_DATA_DIR/simulator.db`
3. `RENDER_DISK_PATH/simulator.db`
4. local fallback `data/simulator.db`

SQLite is appropriate for one small hosted app instance with one database file. This version is not intended for multiple app replicas sharing SQLite.

## Account Workflow

### Create The First Admin

- Launch the app
- Complete `Initial Setup`
- Sign in with the admin account you just created

### Create Team Leader Accounts

- Log in as `admin`
- Open `Admin User Management`
- Use `Create User`
- Set:
  - `username`
  - temporary password
  - role = `team_leader`
  - `team_name`
  - active or inactive status

### Reset A Password

- Log in as `admin`
- Open `Admin User Management`
- Edit the existing user
- Enter a new temporary password
- Save the account

Passwords are hashed in the database and cannot be viewed later.

### Change Your Own Password

Any logged-in `admin` or `team_leader` can open `My Account` and change their own password by entering:

- current password
- new password
- confirm new password

## Classroom Workflow

1. Instructor completes the initial admin setup
2. Instructor creates or bulk imports `team_leader` accounts
3. Teams log in from their own browsers
4. Instructor updates the `Public Market Report` or applies a scenario preset
5. Instructor opens submissions for the current round in `Instructor Panel`
6. Teams submit firm-level operations, product-slot plans, product-level forecasts, and development-project decisions in `Team Decisions`
7. Instructor reviews the submission checklist and validation summary, then closes submissions
8. Instructor runs the round from `Instructor Panel`
9. Class reviews aggregate team results, product results, forecast accuracy, liquidity status, pipeline status, and debrief diagnostics in `Results Dashboard`

## ITE Classroom-Readiness Features

This version adds features intended to make the simulator easier to use as a classroom-tested game/software artifact.

### Scenario Presets

Admins can apply public market scenarios from `Public Market Report`.

Built-in presets include:

- `Stable Market`
- `Demand Boom`
- `Supply Shock`
- `Quality-Sensitive Market`
- `Technology Shift`
- `Price War`
- `Cash Crunch`

These presets update only public market-report inputs such as total demand, segment shares, material-cost pressure, supply risk, quality sensitivity, technology adoption, and beginner price pressure. They do not change private team state or hidden engine constants.

### Submission Open / Close Control

The `Instructor Panel` now includes a submission status control for the current round.

- When submissions are open, team leaders can save their own decisions.
- When submissions are closed, team leaders can still review their plan but cannot save changes.
- Admin users can still edit or inspect data when needed.

The same panel also shows a submission checklist by active team leader account.

### Teaching Debrief Diagnostics

The admin dashboard includes a `Teaching Debrief` tab that converts round outputs into classroom discussion prompts.

Examples of generated teaching points:

- liquidity discipline
- volume is not the same as profit
- forecast-vs-plan discipline
- service level and constraint management
- quality is an economic decision
- inventory risk
- innovation timing tradeoff
- portfolio cannibalization

These diagnostics are not a hidden scoring engine. They are instructor aids for debrief and reflection.

### Optional Balanced Teaching Score

The dashboard includes an optional score that balances multiple learning objectives:

```text
balanced_score =
    100 * (
        0.40 * profit_percentile
      + 0.20 * fill_rate_percentile
      + 0.20 * forecast_accuracy_percentile
      + 0.20 * liquidity_health_percentile
      - liquidity_stress_penalty
    )
```

This helps instructors avoid a pure short-term-profit game. It is useful when the learning objective is managerial balance across profit, service, planning discipline, and cash health.

### CSV Exports

The dashboard now provides CSV exports for classroom assessment and research evidence:

- latest team summary
- persistent team state
- debrief diagnostics
- optional balanced score
- forecast learning summary
- product forecast accuracy
- product results
- liquidity summary
- portfolio snapshot
- development pipeline

### Model Formula Guide

The `Model Formula Guide` page explains the simulator's main formulas in student-readable language:

- segment demand allocation
- product attractiveness
- forecast accuracy
- production feasibility
- defect rate and QC spend
- cash, borrowing, and liquidity stress
- optional balanced teaching score

This page supports transparency and makes the simulation easier to discuss in a paper, teaching note, or classroom debrief.

## Stage C Decision Model

Each team now submits three layers of decisions.

### Firm-Level Shared Decisions

These still apply across the whole firm:

- `overtime_capacity_units`
- `capacity_expansion_units`
- `raw_material_order_qty`
- `supplier_mix_offshore_pct`
- `supplier_mix_balanced_pct`
- `supplier_mix_premium_pct`
- `expedited_order_share_pct`
- `max_backorder_units`
- `planned_borrowing_amount`

These remain shared across all active products for the team.

### Product-Level Active Portfolio Decisions

Each active slot submits:

- `product_name`
- `is_active`
- `target_segment`
- `forecast_units`
- `selling_price_per_unit`
- `planned_production_units`
- `qc_budget_per_unit`
- `target_finished_goods_inventory`
- `retire_flag`

### Development Project Decisions

Each project slot can submit:

- `project_name`
- `target_segment`
- `target_tech_generation`
- `intended_slot_name`
- `planned_launch_round`
- `investment_this_round`
- `testing_intensity`
- `launch_now`
- `cancel_now`
- `cannibalization_group`
- `projected_base_defect_modifier`
- `projected_demand_fit_modifier`

## Lifecycle Rules

Every active product has:

- `age_in_rounds`
- `lifecycle_stage`

Lifecycle stage is currently rule-based and transparent:

- `launch`: age `0-1`
- `growth`: age `2-3`
- `maturity`: age `4-6`
- `decline`: age `7+`

Lifecycle affects:

- demand attractiveness
- price tolerance
- defect stabilization

## Technology Generation Rules

Products and projects now carry a numeric technology generation, currently `Gen 1` to `Gen 4`.

The market report now also includes:

- `current_market_generation`
- `technology_shift_rate`
- `premium_tech_adoption`
- `mid_market_tech_adoption`
- `beginner_price_pressure`

Technology affects:

- demand attractiveness
- obsolescence pressure
- launch risk for newer products
- relative price tolerance

The effect is stronger in premium and mid segments than in beginner.

## Launch Readiness Rules

Development projects now progress over multiple rounds.

Each project has:

- `required_investment`
- `cumulative_investment`
- `launch_readiness_score`
- `planned_launch_round`
- `earliest_launch_round`
- `status`

Readiness is driven by:

- cumulative investment progress
- testing intensity
- technology complexity penalty

In the engine, a project becomes `launch_ready` only when:

- `cumulative_investment >= required_investment`
- `launch_readiness_score >= launch threshold`
- `current round >= earliest_launch_round`

Even after becoming `launch_ready`, the team still has to choose `launch_now` to actually launch it.

Only one launch per team per round is allowed in Stage B.

## Retirement And Replacement Rules

Teams can retire aging products with `retire_flag`.

Stage B also supports replacement:

- when a project launches into an occupied slot, it replaces the old product in that slot
- replaced inventory is liquidated at a markdown recovery rate
- the new product starts with:
  - lifecycle stage `launch`
  - age `0`
  - its project tech generation
  - its projected defect and demand-fit modifiers

Retired products no longer remain active in future rounds.

## Cannibalization Logic

Stage B models bounded intra-team cannibalization after initial market demand allocation.

Demand can transfer from an older product to a newer product when:

- both belong to the same team
- they are in the same cannibalization group or similar segment
- the receiving product is newer, stronger, or just launched
- the donor product is more mature or declining

Cannibalization is intentionally conservative and transparent. The engine stores:

- demand shifted in
- demand shifted out
- total team-level cannibalized demand

## Forecasting And S&OP Logic

Each active product now carries its own submitted demand forecast.

After the round runs, the simulator compares forecast and realized product demand using:

- `forecast_error_units = actual_demand_units - forecast_units`
- `absolute_error_units = abs(actual_demand_units - forecast_units)`
- `forecast_bias_pct = forecast_error_units / max(forecast_units, 1)`
- per-product `mape_or_wape_value = absolute_error_units / max(actual_demand_units, 1)`
- team-level `forecast_wape = sum(absolute_error_units) / max(sum(actual_demand_units), 1)`

The Team Decisions preview and Instructor Panel now surface planning-discipline warnings such as:

- production plan materially below forecast
- production plan materially above forecast
- raw-material ordering too low for the planned output
- high inventory target relative to forecast
- likely cash shortfall even before the round is executed

## Cash And Borrowing Logic

Stage C keeps finance intentionally simple and classroom-manageable.

The simulator now rolls forward:

- `cash_balance`
- `short_term_debt_balance`
- `interest_expense`
- `working_capital_requirement`
- `liquidity_stress_flag`

Round cash flow is modeled as:

- starting cash
- plus revenue collected
- plus planned borrowing
- minus procurement spend
- minus production conversion spend
- minus holding cost
- minus warranty cost
- minus backlog cost
- minus expansion capex
- minus development investment
- minus interest expense

If ending cash would go negative, the engine automatically creates short-term debt for the remaining deficit and floors cash at zero.

Liquidity stress is flagged when combinations of low cash, high debt, repeated borrowing, or heavy working-capital burden appear. The impact is intentionally modest.

## Stage C Engine Logic

The engine still keeps capacity, raw materials, backlog, reputation, and cash at the team level, but now runs demand, forecast accuracy, and results at the product level.

### Shared Firm Constraints

For each team, the simulator first calculates:

- installed capacity
- overtime-adjusted effective capacity
- raw-material inventory available this round
- inbound raw-material receipts
- weighted supplier cost, lead time, defect pressure, and risk exposure

### Project Progress

Before demand allocation, the engine:

- updates each project's cumulative investment
- recomputes launch readiness
- updates project status
- checks launch eligibility

### Launch And Replacement

If an eligible project is launched:

- the target slot becomes a new active product
- any replaced product in that slot is retired
- the new product inherits the project tech generation and modifiers
- the launched product starts in lifecycle stage `launch`

### Product-Level Production Allocation

Teams still submit product-level planned production by slot.

If the sum of product plans exceeds firm-level feasible production because of:

- capacity
- overtime limit
- raw-material availability

the engine proportionally caps production across the active products using largest-remainder integer rounding.

### Product-Level Defect Rate

Each product's defect rate now depends on:

- archetype base defect rate
- product `base_defect_rate_modifier`
- product `qc_budget_per_unit`
- shared supplier defect pressure
- supply risk
- utilization stress
- launch instability
- technology novelty penalty when appropriate

`qc_budget_per_unit` is also charged as a real per-unit production cost, so teams trade off lower defects against higher operating cost.

### Product-Level Demand Allocation

Demand is split into:

- premium
- mid
- beginner

Each active product competes for segment demand using:

- actual numeric selling price
- target segment alignment
- archetype segment fit
- product demand-fit modifier
- lifecycle multiplier
- team reputation
- service readiness
- technology generation relative to the market
- launch novelty when newly launched

Demand is allocated across all active products from all teams, not only at the team level.

### Cannibalization Pass

After initial demand allocation, the engine applies bounded intra-team cannibalization so a newer or stronger product can steal part of an older sibling product's demand.

### Product-Level Service And Inventory

Each product now has its own:

- beginning finished-goods inventory
- beginning backlog
- demand allocated
- sales units
- lost sales units
- ending finished-goods inventory
- fill rate
- profit contribution

Backorders remain constrained by the shared firm-level `max_backorder_units`.

### Team-Level Aggregation

After product results are computed, the engine aggregates them into a firm-level summary:

- total sales
- total revenue
- total cost
- total profit
- weighted defect rate
- fill rate
- ending total inventory
- ending raw-material inventory
- updated reputation
- updated cash
- updated installed capacity
- innovation investment
- launch and retirement event text
- forecast totals and forecast accuracy metrics
- ending cash, debt, interest, and working-capital burden

## Team Decisions Page

The `Team Decisions` page now has six main parts:

1. team identity
2. current team state
3. firm-level shared decisions and finance
4. active product portfolio and forecasts
5. development pipeline
6. analytics preview before save

The preview now shows:

- total forecast units
- total planned production across products
- forecast-production gap
- effective firm capacity
- raw-material sufficiency
- projected ending inventory if forecast is accurate
- projected working-capital burden
- projected ending cash before borrowing
- projected likely borrowing need
- projected portfolio mix by segment
- projected weighted defect rate
- projected weighted margin by product
- pipeline project count
- launch-ready project count
- average portfolio tech position versus market generation
- products at risk of obsolescence
- likely cannibalization exposure
- warnings when production exceeds shared constraints

## Results Dashboard

The dashboard now shows active portfolio, pipeline, forecast accuracy, and liquidity outputs.

### Admin View

- team-level ranking tables
- product-level results table
- forecast accuracy and planning-diagnostic tables
- liquidity and debt summary
- teaching debrief diagnostics
- optional balanced teaching score
- CSV export buttons for assessment and research use
- active portfolio snapshot by team
- lifecycle stage distribution
- development pipeline table
- launch and retirement log
- persistent team state

### Team Leader View

- own team aggregate results
- own forecast-vs-actual detail
- own cash and debt summary
- own active portfolio snapshot
- own development pipeline table
- own product results
- own launch and retirement events
- own debrief prompt
- public ranking table

## Database Schema

The SQLite database now contains these main tables:

- `users`
  username, password hash, role, team assignment, and active status
- `team_archetypes`
  archetype baselines plus suggested default portfolios
- `market_reports`
  public round conditions plus technology-shift fields
- `classroom_rounds`
  instructor-controlled open/closed submission status by round
- `team_decisions`
  firm-level shared portfolio constraints and planned borrowing by round
- `product_lines`
  persistent slot state for each team's active or retired products
- `product_decisions`
  product-slot decisions and per-product forecasts by round
- `product_forecasts`
  persisted product-level forecast submissions by round
- `product_development_projects`
  persistent development-pipeline slots and launch state
- `team_states`
  persistent team cash, debt, materials, capacity, reputation, backlog, and cumulative profit
- `round_results`
  aggregate firm-level round results including forecast and finance metrics
- `product_round_results`
  product-slot round results including launch, retirement, cannibalization, and forecast metrics
- `forecast_accuracy_results`
  per-product forecast-vs-actual diagnostics by round

## Roles And Access

`admin` can use:

- `Home`
- `Public Market Report`
- `Team Decisions`
- `Instructor Panel`
- `Results Dashboard`
- `Admin User Management`
- `Model Formula Guide`
- `My Account`

`team_leader` can use:

- `Home`
- `Public Market Report` as read-only
- `Team Decisions` for their own assigned team only
- `Results Dashboard` with safe filtered visibility
- `Model Formula Guide`
- `My Account`

`team_leader` cannot:

- run rounds
- reset runtime data
- manage users
- submit decisions for another team

## Offline Strategy Simulation Runner

You can run multi-team "what if" scenarios without changing the classroom database.
The runner uses the real Stage C engine in memory and writes CSV/Markdown outputs.

```powershell
.\.venv\Scripts\python.exe scripts\run_strategy_simulation.py --teams 6 --rounds 4
```

Optional examples:

```powershell
.\.venv\Scripts\python.exe scripts\run_strategy_simulation.py --teams 10 --rounds 5
.\.venv\Scripts\python.exe scripts\run_strategy_simulation.py --teams 4 --rounds 3 --strategies balanced_sop innovation_leap low_cost_volume
.\.venv\Scripts\python.exe scripts\run_strategy_simulation.py --teams 6 --rounds 4 --market-scenario supply_shock
.\.venv\Scripts\python.exe scripts\run_strategy_simulation.py --teams 6 --rounds 4 --compare-market-scenarios
.\.venv\Scripts\python.exe scripts\run_strategy_simulation.py --batch-runs 100 --min-teams 4 --max-teams 10 --rounds 4
```

Outputs are written under `simulation_outputs/strategy_run_YYYYMMDD_HHMMSS/`:

- `summary.md`
  instructor-readable ranking and interpretation summary
- `team_results.csv`
  firm-level round history with profit, cash, debt, forecast accuracy, and service metrics
- `product_results.csv`
  product-slot sales, inventory, lifecycle, technology, defects, and cannibalization
- `forecast_accuracy.csv`
  product-level forecast versus actual demand
- `final_team_states.csv`
  final cash, debt, capacity, reputation, inventory, and carryover state

The default strategy presets are:

- `premium_quality`
- `low_cost_volume`
- `balanced_sop`
- `innovation_leap`
- `cash_conservative`
- `aggressive_growth`

The market scenario presets are:

- `baseline`
- `demand_boom`
- `volume_surge`
- `supply_shock`
- `tech_shift`
- `price_recession`
- `quality_sensitive`

When `--compare-market-scenarios` is used, the runner creates one subfolder per
market scenario plus:

- `market_scenario_summary.md`
  cross-scenario winner and strategy robustness summary
- `market_scenario_comparison.csv`
  one final winner row per market condition
- `market_scenario_team_results.csv`
  every team under every market condition for spreadsheet analysis

When `--batch-runs` is used, the runner creates randomized but deterministic
experiment settings from the selected seed. It varies market demand, demand
growth, segment mix, material-cost pressure, supply risk, technology pressure,
quality sensitivity, the number of teams, and the pairing between archetypes and
strategy presets. Batch outputs include:

- `batch_summary.md`
  high-level robustness summary
- `batch_run_summary.csv`
  one row per simulation run
- `batch_final_team_results.csv`
  final-round result for every team in every simulation
- `batch_strategy_robustness.csv`
  aggregate strategy performance across all batch runs
- `batch_team_round_results.csv`
  all firm-level round histories across the batch
- `batch_product_round_results.csv`
  all product-level results across the batch
- `batch_forecast_accuracy.csv`
  all product-level forecast accuracy results across the batch

## Security Notes

- passwords are stored only as secure hashes
- existing passwords are never displayed after creation
- inactive users cannot log in
- page guards protect admin-only controls
- `team_leader` team assignment comes from the authenticated account, not from a manual text field

## Demo Accounts

Production mode does not create shared default passwords.

Demo accounts are seeded only when both of these are true:

- `SIMULATOR_ENV=dev`
- `SIMULATOR_ENABLE_DEMO_ACCOUNTS=true`

That option exists only for explicit demo or development use.

## Simplifications Left For Later Stages

Stage C intentionally still does not include:

- marketing
- ambassador strategy
- retailer or channel negotiation
- multi-country operations
- patent or IP systems
- complex stochastic Monte Carlo simulation
- delayed channel rollout by geography
- full financial statements
- taxes, equity issuance, or advanced treasury management

This keeps the model classroom-manageable while still adding real portfolio, pipeline, forecasting, cash-control, and replacement tradeoffs.
