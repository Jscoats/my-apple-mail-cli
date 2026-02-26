"""Tests for the `mxctl count` command."""

import json
from unittest.mock import Mock

# ---------------------------------------------------------------------------
# cmd_count (accounts.py)
# ---------------------------------------------------------------------------


def test_count_all_accounts(monkeypatch, mock_args, capsys):
    """count with no -a flag returns total unread across all accounts."""
    from mxctl.commands.mail.accounts import cmd_count

    mock_run = Mock(return_value="7")
    monkeypatch.setattr("mxctl.commands.mail.accounts.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.accounts.resolve_account", lambda _: None)

    args = mock_args(account=None, mailbox=None)
    cmd_count(args)

    captured = capsys.readouterr()
    assert captured.out.strip() == "7"


def test_count_specific_account(monkeypatch, mock_args, capsys):
    """count -a returns unread for that account's INBOX."""
    from mxctl.commands.mail.accounts import cmd_count

    mock_run = Mock(return_value="3")
    monkeypatch.setattr("mxctl.commands.mail.accounts.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.accounts.resolve_account", lambda _: "iCloud")

    args = mock_args(account="iCloud", mailbox=None)
    cmd_count(args)

    captured = capsys.readouterr()
    assert captured.out.strip() == "3"


def test_count_specific_mailbox(monkeypatch, mock_args, capsys):
    """count -a -m returns unread in that specific mailbox."""
    from mxctl.commands.mail.accounts import cmd_count

    mock_run = Mock(return_value="5")
    monkeypatch.setattr("mxctl.commands.mail.accounts.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.accounts.resolve_account", lambda _: "iCloud")

    args = mock_args(account="iCloud", mailbox="Sent")
    cmd_count(args)

    captured = capsys.readouterr()
    assert captured.out.strip() == "5"


def test_count_zero_unread(monkeypatch, mock_args, capsys):
    """count returns '0' when there are no unread messages."""
    from mxctl.commands.mail.accounts import cmd_count

    mock_run = Mock(return_value="0")
    monkeypatch.setattr("mxctl.commands.mail.accounts.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.accounts.resolve_account", lambda _: None)

    args = mock_args(account=None, mailbox=None)
    cmd_count(args)

    captured = capsys.readouterr()
    assert captured.out.strip() == "0"


def test_count_json_all(monkeypatch, mock_args, capsys):
    """count --json with all accounts returns JSON with account='all'."""
    from mxctl.commands.mail.accounts import cmd_count

    mock_run = Mock(return_value="12")
    monkeypatch.setattr("mxctl.commands.mail.accounts.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.accounts.resolve_account", lambda _: None)

    args = mock_args(account=None, mailbox=None, json=True)
    cmd_count(args)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["unread"] == 12
    assert data["account"] == "all"


def test_count_json_account(monkeypatch, mock_args, capsys):
    """count -a --json returns JSON with account name and mailbox."""
    from mxctl.commands.mail.accounts import cmd_count

    mock_run = Mock(return_value="4")
    monkeypatch.setattr("mxctl.commands.mail.accounts.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.accounts.resolve_account", lambda _: "iCloud")

    args = mock_args(account="iCloud", mailbox=None, json=True)
    cmd_count(args)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["unread"] == 4
    assert data["account"] == "iCloud"
    assert data["mailbox"] == "INBOX"
