# euler

A Discord bot for Elkins Math and Science. It schedules meetings and contests, announces new events, sends reminders before they start, and handles contest signups.

Built with Python, [discord.py](https://discordpy.readthedocs.io/), and SQLite (via `aiosqlite`). Slash commands only.

## Commands

Officer-only commands are gated on the officer role.

| Command | Who | What it does |
|---|---|---|
| `/meeting add <category> <start_time> <location>` | Officer | Schedule a meeting and announce it |
| `/meeting list` | Officer | Show all meetings with their `#id` |
| `/meeting move <meeting_id> <new_start_time>` | Officer | Reschedule a meeting (re-arms its reminder) |
| `/meeting remove <meeting_id>` | Officer | Delete a meeting |
| `/contest create <name> <contest_date> <location> [signup_deadline]` | Officer | Create a contest, open signups, and announce it |
| `/contest remove <contest_id>` | Officer | Delete a contest and all its signups |
| `/contest list` | Officer | Show contests, deadlines, and per-subcontest signup counts |
| `/contest deadline <contest_id> <deadline>` | Officer | Set a signup deadline, or use `clear` to remove it |
| `/contest signup <contest_id> [number_sense] [general_mathematics] [calculator_applications] [general_science]` | Anyone | Add or remove yourself from any combination of subcontests in one command |
| `/contest withdraw <contest_id> <user> [category]` | Officer | Withdraw someone from one or all subcontests |
| `/contest roster <contest_id> [category]` | Officer | See who signed up, grouped by subcontest |
| `/roles` | Officer | Post or refresh the reaction-role panel in the reaction-roles channel |
| `/clock` | Officer | Compare the bot host clock with Discord time |
| `/man` | Anyone | Show the member manual; officers receive the officer manual by DM |
| `/about` | Anyone | Show bot information and credits |

Only `/contest signup`, `/man`, and `/about` are available to non-officers. Everything else is officer-only.

`/man` sends non-officers the contest signup and reminder guide as an ephemeral message. Officers receive the full officer manual by DM, with an ephemeral fallback if DMs are closed.

For `/contest signup`, set each category to `True` to add it or `False` to remove it. Omit categories you don't want to change. Signups are rejected after the contest's deadline. For example:

```text
/contest signup contest_id:3 number_sense:True general_mathematics:True
```

registers the member for both Number Sense and General Mathematics with one command.

Meeting categories and contest subcontest categories are the same: Number Sense, General Mathematics, Calculator Applications, General Science. A member can sign up for multiple subcontests within the same contest.

All times are entered and displayed in the club timezone, `America/Chicago`. Times are typed as `YYYY-MM-DD HH:MM` (24-hour), e.g. `2026-09-15 15:30`. The server's own timezone does not matter. Use `/clock` if you need to check the host clock.

## Announcements

When an officer creates a meeting or contest, the bot immediately posts an announcement in `ANNOUNCEMENTS_CHANNEL_ID`:

- Meeting announcements ping the role for that meeting's category.
- Contest announcements ping all configured category roles, include the signup command (and deadline when set), and open signups immediately.

## Reminders

A background loop checks every minute. Meeting reminders post **10 minutes** before a meeting; contest reminders post **60 minutes** before a contest. Both post in the reminder channel:

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
python scripts/setup_env.py
```

The setup script prompts for the required values, hides the bot token while you type, accepts either raw IDs or channel/role mentions, validates the timezone, and writes `.env` with `600` permissions. If `.env` already exists, it saves a `.env.bak` backup first. Optional settings stay commented out.

To do it manually, copy `.env.example` to `.env` and fill it in. Turn on Developer Mode in Discord settings to get the **Copy ID** options:

| Variable | What it is |
|---|---|
| `DISCORD_TOKEN` | Bot token (Developer Portal → Bot) |
| `GUILD_ID` | Your server's ID |
| `OFFICER_ROLE_ID` | Role allowed to run officer commands |
| `REMINDER_CHANNEL_ID` | Channel where meeting and contest reminders are posted |
| `ANNOUNCEMENTS_CHANNEL_ID` | Channel where new meetings/contests are announced with role pings |
| `REACTION_ROLES_CHANNEL_ID` | Dedicated channel where `/roles` posts the reaction-role panel |
| `TIMEZONE` | Club timezone, default `America/Chicago` |
| `NUMBER_SENSE_ROLE_ID` | Existing role pinged for Number Sense announcements/reminders |
| `GENERAL_MATHEMATICS_ROLE_ID` | Existing role pinged for General Mathematics announcements/reminders |
| `CALCULATOR_APPLICATIONS_ROLE_ID` | Existing role pinged for Calculator Applications announcements/reminders |
| `GENERAL_SCIENCE_ROLE_ID` | Existing role pinged for General Science announcements/reminders |

Optional settings:

| Variable | What it is |
|---|---|
| `EULER_DB_PATH` | Use a different SQLite file, e.g. `db/dev.sql` |
| `DEV_MODE` | Enables the `/dev` test commands. Requires a separate `EULER_DB_PATH` |
| `EULER_ENV_FILE` | Shell-only override for the env file, e.g. `.env.dev` |
| `MEETING_REMINDER_LEAD_MINUTES` | Minutes before a meeting to remind, default `10` |
| `CONTEST_REMINDER_LEAD_MINUTES` | Minutes before a contest to remind, default `60` |

The real `.env` file lives in the project root and is intentionally ignored by Git. Only `.env.example` (placeholders) is committed. Never commit a bot token or a filled-in `.env`.

Set a category role ID to `0` to skip that category’s announcement/reminder ping and panel entry. The roles must be mentionable, or the bot needs the **Mention @everyone, @here and All Roles** permission.

### 3. Reaction roles

Run `/roles` in Discord as an officer. The bot posts a panel in `REACTION_ROLES_CHANNEL_ID` with one reaction per configured category. This is separate from the announcements channel, so event announcements don't bury the panel. Members react to receive that event role and remove their reaction to drop it.

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
python scripts/setup_env.py --output .env.dev
# Then uncomment/add these in .env.dev:
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
| `/dev contest` | Create a test contest in the contest reminder window |
| `/dev meeting` | Create a test meeting in the meeting reminder window |
| `/dev reminders` | Run the reminder checks immediately |

Do not run the dev instance with the same token as the production bot at the same time; Discord only allows one active gateway session per bot token.

## Project layout

```
main.py                    entry point: wires everything together, syncs commands, starts the bot
.env.example               template for local configuration
scripts/
  setup_env.py             interactive .env generator
euler/
  __init__.py
  bot_instance.py          the single shared Discord client and command tree
  config.py                env vars and constants
  constants.py             shared event categories and emojis
  auth.py                  is_officer() / require_officer(): permission logic
  announcements.py         creation announcements and category role pings
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
    about.py               /about bot information and credits
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
2. Run `python scripts/setup_env.py` on the Pi to create `.env`.
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
