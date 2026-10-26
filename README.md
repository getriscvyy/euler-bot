# euler

A Discord bot for Elkins Math and Science. It schedules meetings and contests, sends reminders before they start, and handles contest signups.

Built with Python, [discord.py](https://discordpy.readthedocs.io/), and SQLite (via `aiosqlite`). Slash commands only.

## Commands

Officer-only commands are gated on the officer role.

| Command | Who | What it does |
|---|---|---|
| `/meeting add <category> <start_time> <location>` | Officer | Schedule a meeting |
| `/meeting list` | Officer | Show all meetings with their `#id` |
| `/meeting move <meeting_id> <new_start_time>` | Officer | Reschedule a meeting (re-arms its reminder) |
| `/meeting remove <meeting_id>` | Officer | Delete a meeting |
| `/contest create <name> <contest_date> <location> [signup_deadline]` | Officer | Create a contest, optionally with a signup deadline |
| `/contest remove <contest_id>` | Officer | Delete a contest and all its signups |
| `/contest list` | Officer | Show contests, deadlines, and per-subcontest signup counts |
| `/contest deadline <contest_id> <deadline>` | Officer | Set a signup deadline, or use `clear` to remove it |
| `/contest signup <contest_id> [number_sense] [general_mathematics] [calculator_applications] [general_science]` | Anyone | Add or remove yourself from any combination of subcontests in one command |
| `/contest withdraw <contest_id> <user> [category]` | Officer | Withdraw someone from one or all subcontests |
| `/contest roster <contest_id> [category]` | Officer | See who signed up, grouped by subcontest |
| `/roles` | Officer | Post or refresh the event notification reaction-role panel |
| `/clock` | Officer | Compare the bot host clock with Discord time |
| `/man` | Anyone | Show the member manual; officers receive the officer manual by DM |

Only `/contest signup` and `/man` are available to non-officers. Everything else is officer-only.

`/man` sends non-officers the contest signup and reminder guide as an ephemeral message. Officers receive the full officer manual by DM, with an ephemeral fallback if DMs are closed.

For `/contest signup`, set each category to `True` to add it or `False` to remove it. Omit categories you don't want to change. Signups are rejected after the contest's deadline. For example:

```text
/contest signup contest_id:3 number_sense:True general_mathematics:True
```

registers the member for both Number Sense and General Mathematics with one command.

Meeting categories and contest subcontest categories are the same: Number Sense, General Mathematics, Calculator Applications, General Science. A member can sign up for multiple subcontests within the same contest.

All times are entered and displayed in the club timezone, `America/Chicago`. Times are typed as `YYYY-MM-DD HH:MM` (24-hour), e.g. `2026-09-15 15:30`. The server's own timezone does not matter. Use `/clock` if you need to check the host clock.

## Reminders

A background loop checks every minute for meetings and contests starting within the next hour that haven't been reminded yet. It posts reminders in the reminder channel:

- Meeting reminders mention only the role for that meeting's category.
- Contest reminders mention only the category roles that have at least one signup.

Members opt in by receiving the relevant category role (for example through reaction roles or server onboarding). Each meeting and contest is reminded once; moving a meeting re-arms its meeting reminder.

## Signup deadlines

Use the optional `signup_deadline` on `/contest create`, or change it later with `/contest deadline <contest_id> <deadline>`. Set it to `clear` to remove it.

Once the deadline passes, `/contest signup` is rejected for everyone; officers can still use `/contest withdraw` to remove signups manually. `/contest list` shows the deadline and whether signups are closed.

## Setup

### 1. Discord application

In the [Developer Portal](https://discord.com/developers/applications):

1. Create an application and add a bot.
2. Under **Bot → Privileged Gateway Intents**, enable **Server Members Intent**.
3. Under **OAuth2 → URL Generator**, tick the `bot` and `applications.commands` scopes, with permissions to send messages and manage roles, and open the URL to invite the bot to your server.

### 2. Configuration

```sh
cp .env.example .env
```

Fill in `.env` (turn on Developer Mode in Discord settings to get the **Copy ID** options):

| Variable | What it is |
|---|---|
| `DISCORD_TOKEN` | Bot token (Developer Portal → Bot) |
| `GUILD_ID` | Your server's ID |
| `OFFICER_ROLE_ID` | Role allowed to run officer commands |
| `REMINDER_CHANNEL_ID` | Channel where meeting and contest reminders are posted |
| `ANNOUNCEMENTS_CHANNEL_ID` | Channel where `/roles` posts the reaction-role panel |
| `TIMEZONE` | Club timezone, default `America/Chicago` |
| `NUMBER_SENSE_ROLE_ID` | Existing role pinged for Number Sense reminders |
| `GENERAL_MATHEMATICS_ROLE_ID` | Existing role pinged for General Mathematics reminders |
| `CALCULATOR_APPLICATIONS_ROLE_ID` | Existing role pinged for Calculator Applications reminders |
| `GENERAL_SCIENCE_ROLE_ID` | Existing role pinged for General Science reminders |

Optional settings:

| Variable | What it is |
|---|---|
| `EULER_DB_PATH` | Use a different SQLite file, e.g. `db/dev.sql` |
| `DEV_MODE` | Enables the `/dev` test commands. Requires a separate `EULER_DB_PATH` |
| `EULER_ENV_FILE` | Shell-only override for the env file, e.g. `.env.dev` |

The real `.env` file lives in the project root and is intentionally ignored by Git. Only `.env.example` (placeholders) is committed. Never commit a bot token or a filled-in `.env`.

Set a category role ID to `0` to skip that category’s role ping/panel entry. The roles must be mentionable, or the bot needs the **Mention @everyone, @here and All Roles** permission.

### 3. Reaction roles

Run `/roles` in Discord as an officer. The bot posts a panel in `ANNOUNCEMENTS_CHANNEL_ID` with one reaction per configured category. Members react to receive that event role and remove their reaction to drop it.

The bot needs **Manage Roles**, and its highest role must be above every event role it assigns.

### 4. Install and run

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m main
```

The database file is created automatically on first start.

## Testing

The database layer has offline tests that need no Discord connection. They use a throwaway `db/test.sql`, recreated on every run:

```sh
python -m tests.test_db
```

### Testing without touching production data

Create a separate dev env file and use a **separate bot token and test guild**:

```sh
cp .env.example .env.dev
# Edit .env.dev: test token, test guild/channel/role IDs, then add:
#   DEV_MODE=true
#   EULER_DB_PATH=db/dev.sql
EULER_ENV_FILE=.env.dev python -m main
```

`.env.dev` is git-ignored. `DEV_MODE=true` refuses to start against the default production database, so test contests and meetings cannot pollute real data.

Dev commands (officer-only, registered only in dev mode):

| Command | What it does |
|---|---|
| `/dev status` | Show the active DB path and timezone |
| `/dev dm` | Send the invoking officer a test DM |
| `/dev contest` | Create a test contest starting in 30 minutes |
| `/dev meeting` | Create a test meeting starting in 30 minutes |
| `/dev reminders` | Run the reminder checks immediately |

Do not run the dev instance with the same token as the production bot at the same time; Discord only allows one active gateway session per bot token.

## Project layout

```
main.py                    entry point: wires everything together, syncs commands, starts the bot
.env.example               template for local configuration; copy to .env
euler/
  __init__.py
  bot_instance.py          the single shared Discord client and command tree
  config.py                env vars and constants
  constants.py             shared event categories and emojis
  auth.py                  is_officer() / require_officer(): permission logic
  db/
    __init__.py
    database.py            all SQL; the only file that knows SQLite exists
  utils/
    __init__.py
    time_parsing.py        time parsing and America/Chicago clock helpers
  features/
    __init__.py
    meetings.py            /meeting commands
    contests.py            /contest commands
    reminders.py           background meeting/contest reminder loop
    self_roles.py          /roles reaction-role panel
    diagnostics.py         /clock host-clock check
    manual.py              /man member and officer manuals
    dev.py                 /dev test commands (only loaded in dev mode)
tests/
  __init__.py
  test_db.py               offline database tests
db/                        SQLite data files (created automatically; not committed)
euler.service              systemd unit for deployment
```

Each feature file registers its commands when imported; `main.py` imports them.

## Deploying on a Raspberry Pi

1. Copy the project to the Pi, create a venv, and install `requirements.txt`.
2. Create `.env` on the Pi with `TIMEZONE=America/Chicago`.
3. Keep the host clock synced with NTP (`timedatectl` / `systemd-timesyncd`), then verify with `/clock`.
4. Edit `User` and the paths in `euler.service`, then:

```sh
sudo cp euler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now euler
journalctl -u euler -f    # follow logs
```

## License

MIT. See [LICENSE](LICENSE).
