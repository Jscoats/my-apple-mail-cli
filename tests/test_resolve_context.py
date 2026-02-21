"""Tests for resolve_message_context() from util/mail_helpers.py."""

from argparse import Namespace

import pytest

from my_cli.util.mail_helpers import resolve_message_context


def test_resolve_message_context_with_account(monkeypatch):
    """Test resolve_message_context with explicit account."""
    args = Namespace(account="iCloud", mailbox=None)

    # Mock resolve_account to return the explicit account
    def mock_resolve_account(account):
        return account

    monkeypatch.setattr("my_cli.util.mail_helpers.resolve_account", mock_resolve_account)

    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)

    assert account == "iCloud"
    assert mailbox == "INBOX"  # DEFAULT_MAILBOX
    assert acct_escaped == "iCloud"
    assert mb_escaped == "INBOX"


def test_resolve_message_context_with_custom_mailbox(monkeypatch):
    """Test resolve_message_context with custom mailbox."""
    args = Namespace(account="Example Account", mailbox="Sent Messages")

    def mock_resolve_account(account):
        return account

    monkeypatch.setattr("my_cli.util.mail_helpers.resolve_account", mock_resolve_account)

    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)

    assert account == "Example Account"
    assert mailbox == "Sent Messages"
    assert acct_escaped == "Example Account"
    assert mb_escaped == "Sent Messages"


def test_resolve_message_context_no_account(monkeypatch):
    """Test resolve_message_context dies when no account is set."""
    args = Namespace(account=None, mailbox=None)

    def mock_resolve_account(account):
        return None

    monkeypatch.setattr("my_cli.util.mail_helpers.resolve_account", mock_resolve_account)

    with pytest.raises(SystemExit):
        resolve_message_context(args)


def test_resolve_message_context_escapes_quotes(monkeypatch):
    """Test resolve_message_context escapes special characters."""
    args = Namespace(account='Account "Name"', mailbox='Mail "Box"')

    def mock_resolve_account(account):
        return account

    monkeypatch.setattr("my_cli.util.mail_helpers.resolve_account", mock_resolve_account)

    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)

    # escape() should escape double quotes
    assert acct_escaped == 'Account \\"Name\\"'
    assert mb_escaped == 'Mail \\"Box\\"'


def test_resolve_message_context_uses_default_mailbox(monkeypatch):
    """Test resolve_message_context falls back to INBOX when mailbox=None."""
    args = Namespace(account="Test", mailbox=None)

    def mock_resolve_account(account):
        return account

    monkeypatch.setattr("my_cli.util.mail_helpers.resolve_account", mock_resolve_account)

    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)

    assert mailbox == "INBOX"
    assert mb_escaped == "INBOX"
