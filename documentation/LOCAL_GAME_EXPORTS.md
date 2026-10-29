# Classroom Data Export and Recovery Backup

Local implementation only. No deployment or production data access was performed.

## Instructor workflow

Sign in to the intended classroom as its administrator. Open **Data Export &
Backup**, then **Prepare Downloads**. Download the Excel workbook and the recovery
ZIP separately. Both describe the same database snapshot and show its UTC time.
Prepare again to include later submissions or results. Switch classrooms and sign
in again to export the other section; no account in one classroom receives another
classroom's files.

The Excel workbook includes every stored row in the game tables. Results, firm and
product decisions, forecasts, market settings, demand commitments and submission
windows retain their recorded round numbers. Current team state, portfolio,
development pipeline and account roster are snapshots, not historical edit logs.
Open material orders also have an expanded worksheet. Password hashes are excluded
from Excel. Formula-like names remain literal text. Long text is split into a
separate worksheet without truncation. Underlying numeric values are preserved.

Neither file recovers unsaved drafts or overwritten revisions from before audit
logging was enabled. New successful submissions appear in Decision Audit Events
and Decision Audit Changes, with coverage information in Audit Coverage. Earlier
pipeline edits cannot be reconstructed where the schema did not retain them.
Historical investment totals remain available in round results.

## Privacy and consistency

- Administrator authorization is checked against the active classroom database,
  not a role or classroom supplied to the export function.
- The export page avoids bootstrap writes. Export source connections use SQLite
  read-only mode, with a read transaction and the SQLite backup API.
- A consistent standalone SQLite file includes committed WAL records without
  depending on WAL/SHM files. Excel and ZIP use that same snapshot.
- A round with saved results but an unfinished demand-completion marker is refused
  until processing completes. Prepare recovery checkpoints after round processing.
- Download bytes are session-local, not held in a global Streamlit cache. Switching
  classrooms clears them; the page also checks their classroom/user scope.
- Both downloads contain private identifiers and unrevealed demand. The ZIP also
  includes password hashes and is **not encrypted**. Store it securely and do not
  distribute it to students or commit it to source control.

## Recovery

The ZIP contains `classroom.sqlite3`, `manifest.json` and `RESTORE_README.txt`.
The manifest identifies the original classroom, timestamp, schema fingerprint,
record counts and database SHA-256 checksum. A checksum detects corruption; it is
not a cryptographic signature of the sender.

The backup includes one classroom's full database, including accounts, hashes,
inputs, rules, results and current states. It excludes other classroom databases,
the shared classroom registry, application source, assets and hosting settings.
Retain the corresponding application source as well.

Run from the application source directory:

```text
python scripts/restore_classroom_backup.py BACKUP.zip NEW_FOLDER/recovered.db
```

Recovery validates ZIP members, format, size, checksum, SQLite integrity, table
counts and administrator presence before exclusively creating a **new** file.
Existing files are never overwritten. It does not register or replace classrooms.
Use the ZIP's instructions to inspect the copy as a standalone localhost instance.
Recovery into a live server remains a separate supervised maintenance operation.

## Local verification

`scripts/test_game_exports.py` covers full saved-round exports, source immutability,
classroom isolation, credentials, authorization, browser-page roles, WAL records,
partial-round rejection, literal formula-like text, long text, recovery equivalence,
corrupt archives and overwrite refusal. All tests use fresh temporary databases.

`scripts/preview_game_exports.py` starts a loopback-only demo with fictional
classrooms 022 (three completed rounds) and 122 (two completed rounds), two teams
each. It refuses to seed an existing database. Demo administrator: `export_admin`;
local-only password: `PreviewOnly123!`.
