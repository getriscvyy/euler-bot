#!/usr/bin/env python3
"""Interactively create an Euler .env file from .env.example."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = PROJECT_ROOT / ".env.example"
DEFAULT_OUTPUT = PROJECT_ROOT / ".env"

ENV_KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    default: str = ""
    secret: bool = False
    kind: str = "text"
    allow_zero: bool = False


FIELDS = (
    Field("DISCORD_TOKEN", "Bot token", secret=True, kind="token"),
    Field("GUILD_ID", "Server ID", kind="id"),
    Field("OFFICER_ROLE_ID", "Officer role ID", kind="id"),
    Field("REMINDER_CHANNEL_ID", "Reminder channel ID", kind="id"),
    Field("ANNOUNCEMENTS_CHANNEL_ID", "Announcements channel ID", kind="id"),
    Field(
        "REACTION_ROLES_CHANNEL_ID",
        "Reaction-roles channel ID (separate from announcements)",
        kind="id",
    ),
    Field("TIMEZONE", "Club timezone", default="America/Chicago", kind="timezone"),
    Field(
        "NUMBER_SENSE_ROLE_ID",
        "Number Sense role ID (0 to skip)",
        default="0",
        kind="id",
        allow_zero=True,
    ),
    Field(
        "GENERAL_MATHEMATICS_ROLE_ID",
        "General Mathematics role ID (0 to skip)",
        default="0",
        kind="id",
        allow_zero=True,
    ),
    Field(
        "CALCULATOR_APPLICATIONS_ROLE_ID",
        "Calculator Applications role ID (0 to skip)",
        default="0",
        kind="id",
        allow_zero=True,
    ),
    Field(
        "GENERAL_SCIENCE_ROLE_ID",
        "General Science role ID (0 to skip)",
        default="0",
        kind="id",
        allow_zero=True,
    ),
)


def read_env(path: Path) -> dict[str, str]:
    """Read uncommented KEY=value pairs, ignoring comments and blanks."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ENV_KEY_RE.match(line.strip())
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def extract_id(raw: str) -> str | None:
    """Accept a raw Discord ID or a channel/role mention."""
    raw = raw.strip()
    mention = re.fullmatch(r"<(?:#|@&)(\d+)>", raw)
    if mention:
        return mention.group(1)
    if raw.isdigit():
        return raw
    return None


def validate_id(raw: str, *, allow_zero: bool) -> tuple[str | None, str | None]:
    value = extract_id(raw)
    if value is None:
        return None, "Enter a numeric Discord ID or copy a channel/role mention."
    if len(value) > 25:
        return None, "That ID is too long."
    number = int(value)
    if number == 0 and not allow_zero:
        return None, "That ID is not valid."
    return str(number), None


def validate_token(raw: str) -> tuple[str | None, str | None]:
    value = raw.strip()
    if not value:
        return None, "A bot token is required."
    if any(character.isspace() for character in value):
        return None, "A bot token cannot contain spaces."
    return value, None


def validate_timezone(raw: str) -> tuple[str | None, str | None]:
    value = raw.strip()
    if not value:
        return None, "A timezone is required."
    if any(character.isspace() for character in value):
        return None, "A timezone cannot contain spaces."
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return None, f"Unknown timezone {value!r}. Try America/Chicago."
    return value, None


def validate_value(field: Field, raw: str) -> tuple[str | None, str | None]:
    if field.kind == "token":
        return validate_token(raw)
    if field.kind == "id":
        return validate_id(raw, allow_zero=field.allow_zero)
    return validate_timezone(raw)


def ask_field(field: Field, current: str) -> str:
    default = current or field.default
    shown_default = "" if field.secret else default
    suffix = ""
    if field.secret and current:
        suffix = " (set; press Enter to keep)"
    elif shown_default:
        suffix = f" [{shown_default}]"

    while True:
        if field.secret:
            raw = getpass.getpass(f"{field.label}{suffix}: ")
        else:
            raw = input(f"{field.label}{suffix}: ")
        raw = raw.strip()
        if not raw:
            if not default:
                print("  A value is required.")
                continue
            value, error = validate_value(field, default)
        else:
            value, error = validate_value(field, raw)

        if error:
            print(f"  {error}")
            continue
        return value


def render_env(template: str, values: dict[str, str]) -> str:
    """Replace matching KEY= lines in the template, preserving comments/layout."""
    lines = []
    for line in template.splitlines():
        match = ENV_KEY_RE.match(line)
        if match and match.group(1) in values:
            lines.append(f"{match.group(1)}={values[match.group(1)]}")
        else:
            lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


def confirm_overwrite(path: Path, *, force: bool) -> bool:
    if not path.exists() or force:
        return True
    answer = input(f"{path} already exists. Overwrite it? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Interactively fill an Euler .env file from .env.example."
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help=f"env template to read (default: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"env file to write (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing env file without asking",
    )
    args = parser.parse_args(argv)

    template_path = args.template.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    if not template_path.is_file():
        print(f"Template not found: {template_path}", file=sys.stderr)
        return 1
    if output_path.is_dir():
        print(f"Output path is a directory: {output_path}", file=sys.stderr)
        return 1
    if output_path == template_path:
        print("Output path must be different from the template.", file=sys.stderr)
        return 1
    template = template_path.read_text(encoding="utf-8")
    template_keys = {
        match.group(1)
        for line in template.splitlines()
        if (match := ENV_KEY_RE.match(line))
    }
    missing = [field.key for field in FIELDS if field.key not in template_keys]
    if missing:
        print(
            "Template is missing required keys: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    if not confirm_overwrite(output_path, force=args.force):
        print("No changes made.")
        return 0

    existing = read_env(output_path)

    print(
        "\nEuler .env setup\n"
        "Bot token: Developer Portal -> Bot -> Reset Token (input is hidden).\n"
        "IDs: enable Discord Developer Mode, then right-click a server, channel,\n"
        "or role and choose Copy ... ID. Press Ctrl+C to cancel.\n"
    )

    values = {field.key: ask_field(field, existing.get(field.key, "")) for field in FIELDS}

    if output_path.exists():
        backup_path = output_path.with_name(output_path.name + ".bak")
        write_private(backup_path, output_path.read_text(encoding="utf-8"))
        print(f"\nBacked up existing env file to {backup_path}")

    write_private(output_path, render_env(template, values))

    print(f"\nWrote {output_path} with permissions 600.")
    print(f"Token: {'set' if values['DISCORD_TOKEN'] else 'missing'}")
    for field in FIELDS[1:]:
        print(f"{field.key}: {values[field.key]}")
    print("\nOptional reminder settings remain commented in the template.")
    if output_path.name == ".env":
        print("Next: python -m main")
    else:
        print(f"Next: EULER_ENV_FILE={output_path} python -m main")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled; no changes made.", file=sys.stderr)
        raise SystemExit(130)
