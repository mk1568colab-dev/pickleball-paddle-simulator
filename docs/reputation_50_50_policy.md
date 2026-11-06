# Reputation policy: 50/50

Current reputation blends 50% previous reputation and 50% this round's service and quality performance, bounded to 10-100.

- Service component: squared fill rate. Lost sales and backlog are not penalized again.
- Quality component: `max(0, 1 - defect_rate / 0.05)`, or zero when no units are produced.
- Quality weight: `0.20 + 0.10 * quality_sensitivity`; service uses the remaining weight.
- No separate liquidity deduction from reputation. Financial consequences are unchanged.
- With no demand or starting backlog to serve, reputation holds, subject to the bounds.
- Fill and defect rates use the saved four-decimal precision, so replay matches future live calculations.
- Opening firms retain the common 60-point start. Late entrants use the active incumbents' 20th percentile minus 10, bounded to 10-50.

## Existing games

Deployment changes future calculation only. It does not automatically rewrite current reputation or historical results.
The instructor must explicitly run the guarded replay tool for each approved classroom while rounds are paused:

```text
python scripts/recalculate_reputation.py --classroom CLASSROOM_ID:GAME_ID:LAST_COMPLETED_ROUND:ADMIN_USERNAME
```

The default is a read-only preview. Repeat `--classroom` for multiple classrooms. Add `--apply` only after reviewing the preview.
All selected classrooms undergo preflight checks; each classroom is then updated in its own atomic transaction.
If a later classroom fails, already completed classrooms remain committed and rerunning is safe.

Each update creates an SQLite backup, changes only current reputation and its state timestamp, and appends an administrative audit event with the full per-round replay trace. Existing accounts, cash, products, investments, decisions and historical results remain unchanged. This evaluates recorded outcomes, not hypothetical sales under different past reputations.

The replay starts opening firms at 60 and applies the entry deduction once when a later firm first appears in the recorded results. Teams with no recorded result receive the current late-entry score. Earlier one-off reputation corrections are superseded by this full replay, not subtracted again. The old one-off deduction tool refuses to run after this policy is applied.

Replaying twice is a no-op. A wrong game ID, changed round, missing market or missing team state aborts without partial changes inside that classroom. Audit markers are game-specific, so a reset game cannot inherit a previous game's replay status. Historical reports retain their original reputation; current Team Decisions shows the corrected score.
