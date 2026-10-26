"""Offline permission tests (no Discord connection). Run from the project root:

    python -m tests.test_permissions
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from euler import config, permissions
from euler.auth import require_officer
from euler.features import perms as perms_feature


class FakeRole:
    def __init__(self, role_id):
        self.id = role_id


class FakeUser:
    def __init__(self, role_ids):
        self.id = 42
        self.roles = [FakeRole(role_id) for role_id in role_ids]


class FakeCommand:
    def __init__(self, qualified_name):
        self.qualified_name = qualified_name


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeInteraction:
    def __init__(self, role_ids=(), command_name=None):
        self.user = FakeUser(role_ids)
        self.command = FakeCommand(command_name) if command_name else None
        self.response = FakeResponse()


def test_store(directory):
    path = Path(directory) / "permissions.json"

    # A missing file uses the code defaults.
    assert permissions.load_member_commands(path) == {"contest list"}
    assert permissions.is_member_allowed("/CONTEST   LIST", path)
    assert not permissions.is_member_allowed("contest signup", path)
    assert not permissions.is_member_allowed("perms set", path)

    # Hand-edited names are normalized; public and /perms commands are ignored.
    path.write_text(
        json.dumps(
            {
                "member_commands": [
                    "/Contest List",
                    "meeting   list",
                    "contest signup",
                    "perms list",
                    7,
                ]
            }
        ),
        encoding="utf-8",
    )
    assert permissions.load_member_commands(path) == {
        "contest list",
        "meeting list",
    }

    # Broken or unexpected files fall back to the defaults.
    for raw in ("{oops", "[]", '{"member_commands": "contest list"}'):
        path.write_text(raw, encoding="utf-8")
        with patch.object(permissions.log, "warning"):
            assert permissions.load_member_commands(path) == {"contest list"}

    # Saving normalizes, sorts, and ignores commands that are not configurable.
    permissions.save_member_commands(
        ["meeting list", "/Contest List", "contest signup"], path
    )
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "member_commands": ["contest list", "meeting list"]
    }
    assert not path.with_name(path.name + ".tmp").exists()

    # Grant, revoke, and reject non-configurable commands.
    assert (
        permissions.set_member_allowed("meeting list", True, path)
        == "meeting list"
    )
    assert permissions.is_member_allowed("meeting list", path)
    assert (
        permissions.set_member_allowed("contest list", False, path)
        == "contest list"
    )
    assert not permissions.is_member_allowed("contest list", path)
    assert permissions.load_member_commands(path) == {"meeting list"}

    for command in ("contest signup", "man", "about", "perms list", "dev status"):
        try:
            permissions.set_member_allowed(command, True, path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{command} should not be configurable")

    # Resetting one command restores only that command's default.
    permissions.reset_member_commands("meeting list", path)
    assert permissions.load_member_commands(path) == set()
    permissions.set_member_allowed("contest list", False, path)
    permissions.reset_member_commands("contest list", path)
    assert permissions.is_member_allowed("contest list", path)
    assert not permissions.is_member_allowed("meeting list", path)

    # Resetting everything returns to the default allowlist.
    permissions.set_member_allowed("meeting list", True, path)
    permissions.reset_member_commands(path=path)
    assert permissions.load_member_commands(path) == {"contest list"}

    # A failed atomic replace leaves the old file intact and no temp file.
    original = path.read_text(encoding="utf-8")
    with patch.object(permissions.os, "replace", side_effect=OSError("disk full")):
        try:
            permissions.set_member_allowed("meeting list", True, path)
        except OSError:
            pass
        else:
            raise AssertionError("save should raise OSError")
    assert path.read_text(encoding="utf-8") == original
    assert not path.with_name(path.name + ".tmp").exists()


async def test_officer_gate():
    with patch.object(config, "OFFICER_ROLE_ID", 999):
        officer = FakeInteraction([999], "contest create")
        assert await require_officer(officer) is True
        assert officer.response.messages == []

        member = FakeInteraction([], "contest list")
        with patch.object(
            permissions, "is_member_allowed", return_value=True
        ) as allowed:
            assert await require_officer(member) is True
            allowed.assert_called_once_with("contest list")
        assert member.response.messages == []

        denied = FakeInteraction([], "contest create")
        with patch.object(permissions, "is_member_allowed", return_value=False):
            assert await require_officer(denied) is False
        assert denied.response.messages == [
            ("Officers only.", {"ephemeral": True})
        ]

        no_command = FakeInteraction([], None)
        with patch.object(permissions, "is_member_allowed") as allowed:
            assert await require_officer(no_command) is False
            allowed.assert_not_called()


async def test_perms_commands():
    group = perms_feature.tree.get_command("perms")
    assert group is not None
    assert {command.name for command in group.commands} == {"list", "set", "reset"}

    # Non-officers cannot even list or change permissions.
    for callback, args in (
        (perms_feature.perms_list.callback, ()),
        (perms_feature.perms_set.callback, ("contest list", "member")),
        (perms_feature.perms_reset.callback, ("contest list",)),
    ):
        denied = FakeInteraction([], "perms list")
        with patch.object(perms_feature, "is_officer", return_value=False):
            await callback(denied, *args)
        assert denied.response.messages == [
            ("Officers only.", {"ephemeral": True})
        ]

    # The list separates member and officer-only commands.
    listed = FakeInteraction([], "perms list")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "load_member_commands",
        return_value={"contest list"},
    ):
        await perms_feature.perms_list.callback(listed)
    content, kwargs = listed.response.messages[0]
    assert kwargs == {"ephemeral": True}
    assert "Members can use:" in content
    assert "`/contest list`" in content
    assert "`/meeting list`" in content
    assert "Always available" in content

    # Grant access.
    granted = FakeInteraction([], "perms set")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "set_member_allowed",
        return_value="contest list",
    ) as set_allowed:
        await perms_feature.perms_set.callback(
            granted, "contest list", "member"
        )
    set_allowed.assert_called_once_with("contest list", True)
    assert granted.response.messages[0][0] == (
        "`/contest list` is now available to members."
    )

    # Revoke access.
    revoked = FakeInteraction([], "perms set")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "set_member_allowed",
        return_value="contest list",
    ) as set_allowed:
        await perms_feature.perms_set.callback(
            revoked, "contest list", "officer"
        )
    set_allowed.assert_called_once_with("contest list", False)
    assert revoked.response.messages[0][0] == (
        "`/contest list` is now available to officers only."
    )

    # A non-configurable command gets a friendly error.
    invalid = FakeInteraction([], "perms set")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "set_member_allowed",
        side_effect=ValueError,
    ):
        await perms_feature.perms_set.callback(
            invalid, "contest signup", "member"
        )
    assert "not configurable" in invalid.response.messages[0][0]

    # A write failure is reported instead of crashing the command.
    unwritable = FakeInteraction([], "perms set")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "set_member_allowed",
        side_effect=OSError,
    ):
        await perms_feature.perms_set.callback(
            unwritable, "contest list", "member"
        )
    assert "Could not save" in unwritable.response.messages[0][0]

    # Resetting one command reports its default access.
    reset_one = FakeInteraction([], "perms reset")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "reset_member_commands",
        return_value="contest list",
    ) as reset, patch.object(
        perms_feature.permissions, "is_member_allowed", return_value=True
    ):
        await perms_feature.perms_reset.callback(reset_one, "contest list")
    reset.assert_called_once_with("contest list")
    assert "reset to its default: members" in reset_one.response.messages[0][0]

    # Omitting the command resets everything.
    reset_all = FakeInteraction([], "perms reset")
    with patch.object(perms_feature, "is_officer", return_value=True), patch.object(
        perms_feature.permissions,
        "reset_member_commands",
        return_value=None,
    ) as reset:
        await perms_feature.perms_reset.callback(reset_all, None)
    reset.assert_called_once_with(None)
    assert "All command permissions reset" in reset_all.response.messages[0][0]

    # Autocomplete offers matching configurable commands only.
    choices = await perms_feature._command_autocomplete(None, "list")
    assert [choice.value for choice in choices] == [
        "meeting list",
        "contest list",
    ]


async def main():
    with tempfile.TemporaryDirectory() as directory:
        test_store(directory)
    await test_officer_gate()
    await test_perms_commands()
    print("permission checks passed")


if __name__ == "__main__":
    asyncio.run(main())
