# euler

A Discord bot for Elkins Math and Science. It schedules meetings, sends reminders before they start, and handles contest signups.

Built with Python, [discord.py](https://discordpy.readthedocs.io/), and SQLite (via `aiosqlite`). Slash commands only.

## Commands

Officer-only commands are gated on the officer role.

| Command | Who | What it does |
|---|---|---|
| `/meeting add <category> <start_time> <location>` | Officer | Schedule a meeting |
| `/meeting list` | Officer | Show all meetings with their `#id` |
| `/meeting move <meeting_id> <new_start_time>` | Officer | Reschedule a meeting (re-arms its reminder) |
| `/meeting remove <meeting_id>` | Officer | Delete a meeting |
| `/contest create <name> <contest_date> <location>` | Officer | Create a contest |
| `/contest list` | Officer | Show contests and per-subcontest signup counts |
| `/contest signup <contest_id> <category>` | Anyone | Sign up for one subcontest |
| `/contest withdraw <contest_id> <user> [category]` | Officer | Withdraw someone from one or all subcontests |
| `/contest roster <contest_id> [category]` | Officer | See who signed up, grouped by subcontest |
| `/roles` | Officer | Post or refresh the event notification reaction-role panel |

Only `/contest signup` is available to non-officers. Everything else is officer-only.

Meeting categories and contest subcontest categories are the same: Number Sense, General Mathematics, Calculator Applications, General Science. A member can sign up for multiple subcontests within the same contest.

Times are typed as `YYYY-MM-DD HH:MM` (24-hour), e.g. `2026-09-15 15:30`. They are stored as naive local time, so the machine running the bot needs the correct timezone.

## Reminders

A background loop checks every minute for meetings starting within the next hour that haven't been reminded yet. It posts a reminder in the reminder channel and mentions only the role for that meeting's category. Members opt in by receiving the relevant category role (for example through reaction roles or server onboarding). Each meeting is reminded once; moving a meeting re-arms it.

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
| `REMINDER_CHANNEL_ID` | Channel where reminders are posted |
| `ANNOUNCEMENTS_CHANNEL_ID` | Channel where `/roles` posts the reaction-role panel |
| `NUMBER_SENSE_ROLE_ID` | Existing role pinged for Number Sense reminders |
| `GENERAL_MATHEMATICS_ROLE_ID` | Existing role pinged for General Mathematics reminders |
| `CALCULATOR_APPLICATIONS_ROLE_ID` | Existing role pinged for Calculator Applications reminders |
| `GENERAL_SCIENCE_ROLE_ID` | Existing role pinged for General Science reminders |

Set a category role ID to `0` to post that category’s reminders without a role ping. The roles must be mentionable, or the bot needs the **Mention @everyone, @here and All Roles** permission.

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

## Project layout

```
main.py                    entry point: wires everything together, syncs commands, starts the bot
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
    time_parsing.py        shared time parsing helper
  features/
    __init__.py
    meetings.py            /meeting commands
    contests.py            /contest commands
    reminders.py           background reminder loop
    self_roles.py          /roles reaction-role panel
tests/
  __init__.py
  test_db.py               offline database tests
db/                        SQLite data files (created automatically; not committed)
euler.service              systemd unit for deployment
```

Each feature file registers its commands when imported; `main.py` imports them.

## Deploying on a Raspberry Pi

1. Copy the project to the Pi, create a venv, and install `requirements.txt`.
2. Create `.env` on the Pi.
3. Edit `User` and the paths in `euler.service`, then:

```sh
sudo cp euler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now euler
journalctl -u euler -f    # follow logs
```

## License

MIT. See [LICENSE](LICENSE).
