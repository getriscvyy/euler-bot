"""Member command access rules stored in permissions.json.

The file is intentionally simple so it can be edited by hand. The /perms
commands update it as well. Only command paths listed in
CONFIGURABLE_COMMANDS can be changed.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from euler import config

log = logging.getLogger(__name__)

PERMISSIONS_PATH = os.path.join(config.BASE_DIR, "permissions.json")

CONFIGURABLE_COMMANDS = (
    "meeting add",
    "meeting list",
    "meeting move",
    "meeting remove",
    "contest create",
    "contest deadline",
    "contest remove",
    "contest list",
    "contest withdraw",
    "contest roster",
    "roles",
    "clock",
)

DEFAULT_MEMBER_COMMANDS = frozenset({"contest list"})
_CONFIGURABLE_SET = frozenset(CONFIGURABLE_COMMANDS)


def normalize_command(command: str) -> str:
    """Turn '/Contest   List' into 'contest list'."""
    return " ".join(command.strip().lstrip("/").lower().split())


def load_member_commands(path=PERMISSIONS_PATH) -> set[str]:
    """Return the member-accessible command paths from the config file."""
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return set(DEFAULT_MEMBER_COMMANDS)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read %s (%s); using defaults", path, exc)
        return set(DEFAULT_MEMBER_COMMANDS)

    command_list = data.get("member_commands") if isinstance(data, dict) else None
    if not isinstance(command_list, list):
        log.warning("Invalid permissions file %s; using defaults", path)
        return set(DEFAULT_MEMBER_COMMANDS)

    commands = set()
    for command in command_list:
        if not isinstance(command, str):
            continue
        normalized = normalize_command(command)
        if normalized in _CONFIGURABLE_SET:
            commands.add(normalized)
    return commands


def is_member_allowed(command: str, path=PERMISSIONS_PATH) -> bool:
    normalized = normalize_command(command)
    return (
        normalized in _CONFIGURABLE_SET
        and normalized in load_member_commands(path)
    )


def save_member_commands(commands, path=PERMISSIONS_PATH) -> None:
    """Atomically write the member command allowlist."""
    cleaned = sorted(
        {
            normalize_command(command)
            for command in commands
            if normalize_command(command) in _CONFIGURABLE_SET
        }
    )
    payload = json.dumps(
        {"member_commands": cleaned}, indent=2, ensure_ascii=False
    ) + "\n"
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def set_member_allowed(command: str, allowed: bool, path=PERMISSIONS_PATH) -> str:
    """Grant or revoke member access. Returns the normalized command path."""
    normalized = normalize_command(command)
    if normalized not in _CONFIGURABLE_SET:
        raise ValueError(f"Not a configurable command: {command}")

    commands = load_member_commands(path)
    if allowed:
        commands.add(normalized)
    else:
        commands.discard(normalized)
    save_member_commands(commands, path)
    return normalized


def reset_member_commands(command: str | None = None, path=PERMISSIONS_PATH):
    """Restore one command or every command to the code defaults."""
    if command is None:
        save_member_commands(DEFAULT_MEMBER_COMMANDS, path)
        return None

    normalized = normalize_command(command)
    if normalized not in _CONFIGURABLE_SET:
        raise ValueError(f"Not a configurable command: {command}")

    commands = load_member_commands(path)
    if normalized in DEFAULT_MEMBER_COMMANDS:
        commands.add(normalized)
    else:
        commands.discard(normalized)
    save_member_commands(commands, path)
    return normalized
