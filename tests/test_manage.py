"""Tests for mailbox management commands (manage.py)."""

from argparse import Namespace
from unittest.mock import Mock
import subprocess

import pytest

from my_cli.commands.mail.manage import cmd_empty_trash


def test_cmd_empty_trash_single_account(monkeypatch, capsys):
    """Test empty-trash for a single account."""
    # Mock resolve_account to return the account
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="5")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

    # Mock subprocess.run for the UI script
    mock_subprocess = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("my_cli.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert "Erase dialog opened for iCloud (5 messages)" in captured.out
    assert "Confirm in Mail.app to permanently delete" in captured.out


def test_cmd_empty_trash_all_accounts(monkeypatch, capsys):
    """Test empty-trash with --all flag."""
    def mock_resolve_account(account):
        return None

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock subprocess.run for the UI script
    mock_subprocess = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("my_cli.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account=None, all=True, json=False)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert "Erase dialog opened for all accounts" in captured.out
    assert "Confirm in Mail.app to permanently delete" in captured.out


def test_cmd_empty_trash_already_empty(monkeypatch, capsys):
    """Test empty-trash when trash is already empty."""
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return 0 messages
    mock_run = Mock(return_value="0")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    captured = capsys.readouterr()
    assert "Trash is already empty for 'iCloud'" in captured.out


def test_cmd_empty_trash_json_output(monkeypatch, capsys):
    """Test empty-trash with JSON output."""
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="3")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

    # Mock subprocess.run for the UI script
    mock_subprocess = Mock(return_value=Mock(returncode=0, stderr=""))
    monkeypatch.setattr("my_cli.commands.mail.manage.subprocess.run", mock_subprocess)

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

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return 0 messages
    mock_run = Mock(return_value="0")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

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

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    args = Namespace(account=None, all=False, json=False)

    with pytest.raises(SystemExit):
        cmd_empty_trash(args)


def test_cmd_empty_trash_menu_not_found(monkeypatch):
    """Test empty-trash handles menu item not found error."""
    def mock_resolve_account(account):
        return "InvalidAccount"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="5")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

    # Mock subprocess.run to fail with "Can't get menu item"
    mock_subprocess = Mock(return_value=Mock(
        returncode=1,
        stderr="Can't get menu item InvalidAccount… of menu 1"
    ))
    monkeypatch.setattr("my_cli.commands.mail.manage.subprocess.run", mock_subprocess)

    args = Namespace(account="InvalidAccount", all=False, json=False)

    with pytest.raises(SystemExit):
        cmd_empty_trash(args)


def test_cmd_empty_trash_timeout(monkeypatch):
    """Test empty-trash handles timeout gracefully."""
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return message count
    mock_run = Mock(return_value="5")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

    # Mock subprocess.run to raise TimeoutExpired
    def mock_subprocess_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="osascript", timeout=15)

    monkeypatch.setattr("my_cli.commands.mail.manage.subprocess.run", mock_subprocess_timeout)

    args = Namespace(account="iCloud", all=False, json=False)

    with pytest.raises(SystemExit):
        cmd_empty_trash(args)


def test_cmd_empty_trash_nonzero_message_count_handling(monkeypatch, capsys):
    """Test empty-trash handles non-numeric message count gracefully."""
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to return non-numeric result
    mock_run = Mock(return_value="error")
    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    # Should treat non-numeric as 0 and report already empty
    captured = capsys.readouterr()
    assert "Trash is already empty for 'iCloud'" in captured.out


def test_cmd_empty_trash_applescript_error_handling(monkeypatch, capsys):
    """Test empty-trash handles AppleScript errors during count gracefully."""
    def mock_resolve_account(account):
        return "iCloud"

    monkeypatch.setattr("my_cli.commands.mail.manage.resolve_account", mock_resolve_account)

    # Mock the AppleScript run to raise SystemExit (die() was called)
    def mock_run_error(script):
        raise SystemExit(1)

    monkeypatch.setattr("my_cli.commands.mail.manage.run", mock_run_error)

    args = Namespace(account="iCloud", all=False, json=False)
    cmd_empty_trash(args)

    # Should treat error as count=0 and report already empty
    captured = capsys.readouterr()
    assert "Trash is already empty for 'iCloud'" in captured.out
