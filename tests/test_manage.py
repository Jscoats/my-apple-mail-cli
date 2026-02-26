"""Tests for mailbox management commands (manage.py)."""

import subprocess
from argparse import Namespace
from unittest.mock import Mock

import pytest

from mxctl.commands.mail.manage import cmd_create_mailbox, cmd_delete_mailbox, cmd_empty_trash


def test_cmd_empty_trash_single_account(monkeypatch, capsys):
    """Test empty-trash for a single account."""

    # Mock resolve_account to return the account
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="5")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    # Mock subprocess.run for the UI script
    mock_subprocess = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("mxctl.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert "Erase dialog opened for iCloud (5 messages)" in captured.out
    assert "Confirm in Mail.app to permanently delete" in captured.out


def test_cmd_empty_trash_all_accounts(monkeypatch, capsys):
    """Test empty-trash with --all flag."""

    def mock_resolve_account(account):
        return None

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock subprocess.run for the UI script
    mock_subprocess = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("mxctl.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account=None, all=True, json=False)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert "Erase dialog opened for all accounts" in captured.out
    assert "Confirm in Mail.app to permanently delete" in captured.out


def test_cmd_empty_trash_already_empty(monkeypatch, capsys):
    """Test empty-trash when trash is already empty."""

    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return 0 messages
    mock_run = Mock(return_value="0")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert "Trash is already empty for 'iCloud'" in captured.out


def test_cmd_empty_trash_json_output(monkeypatch, capsys):
    """Test empty-trash with JSON output."""

    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="3")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    # Mock subprocess.run for the UI script
    mock_subprocess = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("mxctl.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account="iCloud", all=False, json=True)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert '"account": "iCloud"' in captured.out
    assert '"status": "confirmation_pending"' in captured.out
    assert '"messages": 3' in captured.out


def test_cmd_empty_trash_json_already_empty(monkeypatch, capsys):
    """Test empty-trash JSON output when already empty."""

    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return 0 messages
    mock_run = Mock(return_value="0")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", all=False, json=True)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert '"account": "iCloud"' in captured.out
    assert '"status": "already_empty"' in captured.out
    assert '"messages": 0' in captured.out


def test_cmd_empty_trash_no_account_no_all_flag(monkeypatch):
    """Test empty-trash fails when neither account nor --all is provided."""

    def mock_resolve_account(account):
        return None

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    args = Namespace(account=None, all=False, json=False)

    with pytest.raises(SystemExit):
        cmd_empty_trash(args)


def test_cmd_empty_trash_menu_not_found(monkeypatch):
    """Test empty-trash handles menu item not found error."""

    def mock_resolve_account(account):
        return "InvalidAccount"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="5")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    # Mock subprocess.run to fail with "Can't get menu item"
    mock_subprocess = Mock(return_value=Mock(returncode=1, stderr="Can't get menu item InvalidAccount… of menu 1"))
    monkeypatch.setattr("mxctl.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account="InvalidAccount", all=False, json=False)

    with pytest.raises(SystemExit):
        cmd_empty_trash(args)


def test_cmd_empty_trash_timeout(monkeypatch):
    """Test empty-trash handles timeout gracefully."""

    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="5")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    # Mock subprocess.run to raise TimeoutExpired
    def mock_subprocess_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="osascript", timeout=15)

    monkeypatch.setattr("mxctl.commands.mail.manage.subprocess.run", mock_subprocess_timeout)

    args = Namespace(account="iCloud", all=False, json=False)

    with pytest.raises(SystemExit):
        cmd_empty_trash(args)


def test_cmd_empty_trash_nonzero_message_count_handling(monkeypatch, capsys):
    """Test empty-trash handles non-numeric message count gracefully."""

    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return non-numeric result
    mock_run = Mock(return_value="error")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    # Should treat non-numeric as 0 and report already empty
    captured = capsys.readouterr()
    assert "Trash is already empty for 'iCloud'" in captured.out


def test_cmd_empty_trash_applescript_error_handling(monkeypatch, capsys):
    """Test empty-trash handles AppleScript errors during count gracefully."""

    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to raise SystemExit (die() was called)
    def mock_run_error(script):
        raise SystemExit(1)

    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run_error)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    # Should treat error as count=0 and report already empty
    captured = capsys.readouterr()
    assert "Trash is already empty for 'iCloud'" in captured.out


# ---------------------------------------------------------------------------
# cmd_create_mailbox
# ---------------------------------------------------------------------------


def test_cmd_create_mailbox_success(monkeypatch, capsys):
    """Test create-mailbox calls run() and reports creation."""
    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", lambda _: "iCloud")

    mock_run = Mock(return_value="created")
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", name="MyProject", json=False)
    cmd_create_mailbox(args)

    # run() should have been called once with the create script
    assert mock_run.call_count == 1
    script = mock_run.call_args[0][0]
    assert "make new mailbox" in script
    assert "MyProject" in script

    captured = capsys.readouterr()
    assert "MyProject" in captured.out
    assert "created" in captured.out.lower()


def test_cmd_create_mailbox_no_account_dies(monkeypatch):
    """Test create-mailbox exits when no account is resolved."""
    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", lambda _: None)

    args = Namespace(account=None, name="MyProject", json=False)
    with pytest.raises(SystemExit):
        cmd_create_mailbox(args)


# ---------------------------------------------------------------------------
# cmd_delete_mailbox
# ---------------------------------------------------------------------------


def test_cmd_delete_mailbox_without_force_dies(monkeypatch):
    """Test delete-mailbox exits without --force flag."""
    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", lambda _: "iCloud")

    args = Namespace(account="iCloud", name="OldMailbox", force=False, json=False)
    with pytest.raises(SystemExit):
        cmd_delete_mailbox(args)


def test_cmd_delete_mailbox_with_force_proceeds(monkeypatch, capsys):
    """Test delete-mailbox proceeds and calls run() when --force is given."""
    monkeypatch.setattr("mxctl.commands.mail.manage.resolve_account", lambda _: "iCloud")

    # First call returns count, second call performs the delete
    mock_run = Mock(side_effect=["3", "deleted"])
    monkeypatch.setattr("mxctl.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", name="OldMailbox", force=True, json=False)
    cmd_delete_mailbox(args)

    # run() should have been called twice (count + delete)
    assert mock_run.call_count == 2

    captured = capsys.readouterr()
    assert "OldMailbox" in captured.out
    assert "deleted" in captured.out.lower()
