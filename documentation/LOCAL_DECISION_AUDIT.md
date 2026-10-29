# Decision Audit Log

Local-only implementation. No production deployment or access to production
classroom data was performed.

## Recorded events

Every successful explicit save/submit through Team Decisions creates a new
immutable revision, even when the decision values are unchanged. Sources are
`student_submission`, `admin_submission`, and `automatic_carry_forward`.
Automatic carry-forward identifies the actor as System and separately records the
administrator who initiated it when run through the instructor browser. It never
assigns the missing student's identity to an automated action.

Each revision records classroom and game ID, team, round, revision number, server
UTC timestamp, account ID/name/role, comparison basis, reason, and complete before
and after snapshots of the decision inputs. Field changes include group, slot,
field name, old/new presence, and JSON-encoded old/new values.

Inputs include firm sourcing/capacity/finance controls, product price/forecast/
production/QC/inventory/retirement controls, and development investment/testing/
launch/cancellation controls. Calculated engine outcomes belong to the existing
round results; they are not attributed to student edits.

Same-round revisions compare with the previous saved submission. A first
submission in a later round compares firm/product inputs with the last saved
round and development choices with the saved pipeline immediately before the
submission. Without prior saved inputs, values are marked as not previously
recorded. This does not claim to capture what was displayed in an unsaved draft.

## Coverage and preservation

- Only saved decisions are recorded, not keystrokes, browsing, failed saves or
  unsaved drafts. Old overwritten edits are not fabricated or backfilled.
- Audit tables are additive. Existing accounts, decisions, states and results are
  not rewritten by the audit migration.
- The submission and its audit rows share one SQLite transaction. A failed write
  rolls back both. Concurrent saves receive serial revisions with consistent
  before/after snapshots.
- Audit rows have no foreign key to mutable user/team records, so historical actor
  names survive account deletion or renaming. UPDATE and DELETE are rejected by
  audit-table triggers. This is application history, not cryptographically signed
  or administrator-proof forensic storage.
- Game resets retain the audit history and rotate the game ID, so reused team and
  round numbers are not confused with the previous game. The admin page defaults
  to the current game; select All games to inspect earlier runs.
- Ordinary low-level engine/seeding repository writes are not labeled as student
  submissions. The two classroom entry points are explicit submission and
  instructor automatic carry-forward.

## Viewing and exporting

Administrators use **Decision Audit Log** to filter team, round, source and game,
then inspect a revision's field changes and full saved snapshots. Students cannot
open this page. Times are explicitly UTC.

**Data Export & Backup** now includes **Decision Audit Events**, **Decision Audit
Changes**, and **Audit Coverage** worksheets. Full-history Excel and recovery ZIP
remain specific to the authenticated classroom. The ZIP includes audit tables and
their triggers. These files contain private account identifiers and should not be
distributed to students.

## Local checks

Run `scripts/test_decision_audit.py` with the app Python. Tests cover revisions,
actors, unchanged resubmissions, pipeline history, automatic no-investment plans,
rollback, migrations, authorization, reset retention, simultaneous saves, Excel,
recovery and admin/student UI behavior.

Run `scripts/preview_decision_audit.py` for fresh fictional 022/122 games on an
unused localhost port. The script refuses to seed existing databases. Each class
shows three student submissions and a system carry-forward, then opens the next
round for local UI checks. Demo admin: `export_admin`; student: `demo_022_1` or
`demo_122_1`. All demo passwords are `PreviewOnly123!`.
