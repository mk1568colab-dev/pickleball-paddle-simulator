# Student Market Report Rules

Local-only presentation change. No production deployment or student database
update is required. `engine/market_brief.py` reads the public round settings and
returns three English paragraphs. It does not read team decisions, cash,
inventory, rankings or unrevealed actual demand. There are no external AI calls,
random wording choices or separately generated reports for individual students.
All students in the same classroom and round receive the same report. Different
classrooms may have different market settings and therefore different reports.

## Sentence Selection

Quality and technology signals use four bands, separating strong conditions from
particularly strong conditions without increasing the number of sentences.

| Input | Limited | Moderate | Strong | Particularly strong |
|---|---|---|---|---|
| Quality sensitivity | x < 0.40 | 0.40 <= x < 0.70 | 0.70 <= x < 0.85 | x >= 0.85 |
| Technology shift rate | x < 0.15 | 0.15 <= x < 0.30 | 0.30 <= x < 0.50 | x >= 0.50 |
| Premium technology adoption | x < 0.40 | 0.40 <= x < 0.70 | 0.70 <= x < 0.85 | x >= 0.85 |
| Mid-market technology adoption | x < 0.40 | 0.40 <= x < 0.70 | 0.70 <= x < 0.85 | x >= 0.85 |

Quality describes reputation effects, technology shift describes additional
obsolescence pressure, and adoption describes the segment's emphasis on technology.
The market technology generation remains a direct value, not a sentence band.

The other numeric sentence rules remain unchanged:

| Input | Lower band | Middle band | Upper band |
|---|---|---|---|
| Material cost index | x < 0.95: prices below baseline | 0.95 <= x < 1.05: prices close to baseline | x >= 1.05: prices above baseline |
| Beginner price-pressure coefficient | x < 0.40: comparatively more technology interest, narrower acceptable-price range | 0.40 <= x < 0.70: relatively little technology weight, moderate price range | x >= 0.70: less technology weight, broader price range |

The beginner descriptions follow the current engine, which widens price tolerance
and reduces technology weight as this coefficient increases. The coefficient's
name must not be interpreted as a universal penalty for raising prices.

Supply risk is categorical rather than numeric:

- Low: "Supply conditions are relatively stable, although materials still require delivery time."
- Moderate: "Supply conditions involve some delivery uncertainty; normal arrival dates are not guaranteed."
- High: "Supply conditions are disrupted, with a higher risk of late material deliveries."

## Direct Values and Composition

- Round number, published demand range and market technology generation are
  inserted directly into sentences. A demand midpoint is not supplied as a forecast.
- Segment shares determine the demand ranking. Equal shares are described as ties;
  zero-demand segments are identified. Raw share coefficients are not displayed.
- An unpublished demand outlook is identified as unpublished, without hiding the
  other market conditions.
- Instructor-authored market-event text is included unchanged, when present.
  It is public text and should be written in English for an all-English report.
- Paragraph 1: demand outlook and segment mix.
- Paragraph 2: material prices, supply conditions and any instructor market event.
- Paragraph 3: quality/reputation, technology benchmark, obsolescence pressure,
  and customer preferences by segment.

These thresholds classify language only. They do not round, replace or change the
simulation inputs. For example, quality sensitivity values of 0.71 and 0.80 select the same wording while
remaining different numeric inputs in the engine. Thresholds are presentation
choices, not empirically estimated market boundaries.

Actual demand remains private until the existing completion/reveal process marks
the round complete. Completed-round demand remains visible in its existing table.
The instructor retains the numeric setup controls. Report prose gives current
conditions, not team-specific advice or claims of change from a previous round.

## Tests

`scripts/test_market_brief.py` covers sentence bands, exact boundaries, segment
ties, three-paragraph composition, repeated-input consistency, different rounds,
team-independent output, private-demand exclusion, student/admin page behavior,
and post-round actual-demand disclosure. `scripts/test_demand_protocol.py` covers
the existing demand locking and reveal workflow. All database tests use disposable
files, not classroom records.
