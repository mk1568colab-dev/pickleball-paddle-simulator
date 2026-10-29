# Shared raw-material requirements (local implementation)

No deployment, git push, production connection, account reset or classroom-data import was performed.
The preview launcher always creates a new directory and database and binds Streamlit to 127.0.0.1.

## Controls and preservation

- New databases: Beginner 0.70, Mid 1.00, Premium 1.20 standard RM per paddle.
- Existing databases: additive schema only; legacy 1.00 for every design is retained. Accounts,
  saved decisions, results, cash and inventories are not reset or recalculated.
- Instructor Cockpit > Raw-Material Requirements controls the current unopened round.
- The save service checks the authenticated, active administrator in the selected classroom.
- Opening submissions snapshots the round's rules in the same transaction as the demand commitment.
  Closing submissions never unlocks them. Saved decisions or completed results also block changes.
- Rules carry forward. A new round may be changed before opening; previous rounds remain unchanged.
- A full game reset removes future round overrides but retains the original round-1 rules.
- Product material design is initialized from its opening/launch design and retained separately from
  student-editable target segment. A replacement launch receives its new design.

## Calculation and UI

Students change production in the existing Product Profile inputs. The read-only Shared Raw-Material
Plan immediately shows each active product's design, planned paddles, RM per paddle, RM requirement
and estimated material value, plus shared availability, shortage/remaining RM and procurement outlay.

Production scales to capacity and material constraints, then distributes feasible whole-paddle
remainders deterministically. The allocator uses integer hundredths for materials. Capacity and
production remain whole paddles. Unused fractional RM survives saving, loading and later rounds.
Materials received this round enter the shared pool; new orders still arrive in future rounds.

Material value is a current-quote planning estimate, not another cash charge or historical inventory
cost valuation. Ordering charges procurement once. Production conversion and QC remain separate.
Unit margins and working-capital estimates use the design-specific material requirement.
Product procurement and RM holding allocations use actual material consumption shares.

Existing SQLite columns declared INTEGER are non-STRICT and accept fractional REAL values; no
table rebuild is necessary. Python model loaders no longer truncate these material balances.

## Local preview and checks

Run `scripts/preview_material_requirements.py` with the existing project Python environment.
It creates two fictional teams and a test administrator, leaving Round 1 unopened for editing.
Local-only usernames: `materials_admin`, `materials_team1`, `materials_team2`.
Local-only password: `PreviewOnly123!`.

Focused checks: `scripts/test_material_requirements.py` covers permissions, lock behavior,
classroom isolation, legacy rules, fractional persistence, no target-segment bypass, retirement and
replacement, arrivals, capacity, UI updates and 500 deterministic randomized allocation cases.
The regression runner in `outputs/materials_app_20261026` stores individual test logs and a summary.

Before any future deployment, review the migration and choose a transition round deliberately.
Do not change the active classroom's rules mid-round.
