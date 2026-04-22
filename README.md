# Pickleball Paddle Simulator

Lightweight Streamlit classroom simulator with:

- `admin` and `team_leader` accounts
- SQLite persistence
- a basic OM round engine
- hosted deployment support for one shared classroom app instance

This version intentionally excludes `team_member`, marketing logic, and ambassador strategy.

## What The App Does

- `admin` users create accounts, manage the public market report, run rounds, and review all results
- `team_leader` users log in from their own browsers, submit only their own team decision, and review their own results plus public rankings
- the OM engine evaluates price, production quantity, capacity plan, quality level, and inventory posture
- team inventory, capacity, reputation, and cumulative profit persist across rounds

## First-Run Admin Setup

The default production workflow no longer relies on seeded shared passwords.

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

1. Push the repo to GitHub
2. Create a web service from the repo
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
  Only used in explicit development/demo mode
- `RENDER_DISK_PATH`
  Optional hosted disk directory fallback

Database path resolution order:

1. `SIMULATOR_DB_PATH`
2. `SIMULATOR_DATA_DIR/simulator.db`
3. `RENDER_DISK_PATH/simulator.db`
4. local fallback `data/simulator.db`

SQLite is appropriate for one small hosted app instance with one database file. This version is not intended for multiple app replicas sharing SQLite.

## Account Lifecycle

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
  - active/inactive status

### Reset A Password

- Log in as `admin`
- Open `Admin User Management`
- Use `Edit Existing User`
- enter a new temporary password
- save the account

Passwords are hashed in the database and cannot be viewed later.

### Change Your Own Password

Any logged-in `admin` or `team_leader` can open `My Account` and change their own password by entering:

- current password
- new password
- confirm new password

## One-Time Credential Display

Because stored passwords cannot be revealed later:

- when an admin creates a user, the app shows a one-time credential card
- when an admin resets a password, the app shows the new one-time credential card again
- when an admin bulk imports team leaders, the app shows a summary plus an optional CSV download of the newly created or updated credentials from that import event only

The database never stores retrievable plain text passwords.

## Bulk CSV Import

`Admin User Management` includes a bulk import tool for `team_leader` accounts.

Required CSV columns:

```csv
username,password,team_name,is_active
team_alpha_lead,AlphaLeader123,Team Alpha,true
team_beta_lead,BetaLeader123,Team Beta,true
```

Rules:

- imported users are always created as `team_leader`
- `team_name` is required
- passwords are validated and hashed before saving
- if `Update existing usernames if found` is off, existing usernames are skipped
- if that checkbox is on, existing `team_leader` users are updated
- existing non-`team_leader` usernames are not overwritten by bulk import

The import summary reports:

- created count
- updated count
- skipped count
- error rows

## Roles And Page Access

`admin` can use:

- `Home`
- `Public Market Report`
- `Team Decisions`
- `Instructor Panel`
- `Results Dashboard`
- `Admin User Management`
- `My Account`

`team_leader` can use:

- `Home`
- `Public Market Report` as read-only
- `Team Decisions` for their own assigned team only
- `Results Dashboard` with safe filtered visibility
- `My Account`

`team_leader` cannot:

- run rounds
- reset runtime data
- manage users
- submit decisions for another team

## Classroom Workflow

1. Instructor completes the initial admin setup
2. Instructor creates or bulk imports `team_leader` accounts
3. Teams log in from their own browsers
4. Instructor updates the `Public Market Report`
5. Teams submit decisions in `Team Decisions`
6. Instructor runs the round from `Instructor Panel`
7. Class reviews outcomes in `Results Dashboard`

## Database Schema

The SQLite database contains these main tables:

- `users`
  Stores username, password hash, role, team assignment, and active status
- `team_archetypes`
  Stores OM archetype reference data
- `market_reports`
  Stores public round conditions
- `team_decisions`
  Stores one decision per team per round
- `team_states`
  Stores persistent inventory, capacity, reputation, and cumulative profit
- `round_results`
  Stores computed round outcomes

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

That option exists only for explicit demo/development use.
