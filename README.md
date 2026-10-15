# euler

A Discord bot for Elkins Math and Science. It schedules meetings, sends reminders before they start, and handles contest signups.

Built with Python, [discord.py](https://discordpy.readthedocs.io/), and SQLite (via `aiosqlite`). Slash commands only.

## Commands

Officer-only commands are gated on the officer role.

| Command | Who | What it does |
|---|---|---|
| `/meeting add <category> <start_time> <location>` | Officer | Schedule a meeting |
| `/meeting list` | Anyone | Show all meetings with their `#id` |
| `/meeting move <meeting_id> <new_start_time>` | Officer | Reschedule a meeting (re-arms its reminder) |
| `/meeting remove <meeting_id>` | Officer | Delete a meeting |
| `/contest create <name> <contest_date> <location>` | Officer | Create a contest |
| `/contest list` | Anyone | Show contests and signup counts |
| `/contest signup <contest_id>` | Anyone | Sign yourself up |
| `/contest withdraw <contest_id>` | Anyone | Remove yourself |
| `/contest roster <contest_id>` | Officer | See who signed up |

Meeting categories: Number Sense, General Mathematics, Calculator Applications, General Science.

Times are typed as `YYYY-MM-DD HH:MM` (24-hour), e.g. `2026-09-15 15:30`. They are stored as naive local time, so the machine running the bot needs the correct timezone.

## Reminders

A background loop checks every minute for meetings starting within the next hour that haven't been reminded yet. Everyone with the member role gets a DM. Anyone whose DMs are closed is pinged in the reminder channel instead. Each meeting is reminded once; moving a meeting re-arms it.

## Setup

### 1. Discord application

In the [Developer Portal](https://discord.com/developers/applications):

1. Create an application and add a bot.
2. Under **Bot → Privileged Gateway Intents**, enable **Server Members Intent**.
3. Under **OAuth2 → URL Generator**, tick the `bot` and `applications.commands` scopes, with permission to send messages, and open the URL to invite the bot to your server.

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
| `MEMBER_ROLE_ID` | Role that receives reminder DMs |
| `REMINDER_CHANNEL_ID` | Channel for fallback pings when a DM fails |

### 3. Install and run

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
python -m test_db
```

## Project layout

```
main.py              entry point: wires everything together, syncs commands, starts the bot
bot_instance.py      the single shared Discord client and command tree
config.py            env vars and constants
auth.py              is_officer(): the only place permission logic lives
utils.py             shared helpers (time parsing)
db/database.py       all SQL; the only file that knows SQLite exists
features/
  meetings.py        /meeting commands
  contests.py        /contest commands
  reminders.py       background reminder loop
test_db.py           offline database tests
euler.service        systemd unit for deployment
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
