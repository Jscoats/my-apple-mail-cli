"""Pytest configuration and shared fixtures."""

from argparse import Namespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_run(monkeypatch):
    """Mock applescript.run() with configurable canned output.

    Also mocks inbox_iterator_all_accounts to avoid template dependency.
    """
    mock = Mock(return_value="")
    monkeypatch.setattr("mxctl.util.applescript.run", mock)

    # Mock the template function to return a simple script
    def mock_template(inner_ops, cap=20, account=None):
        return 'tell application "Mail"\nset output to ""\nend tell'

    monkeypatch.setattr("mxctl.commands.mail.ai.inbox_iterator_all_accounts", mock_template)

    return mock


@pytest.fixture
def mock_args():
    """Factory fixture for creating argparse Namespace objects with defaults."""

    def _create(**overrides):
        defaults = {
            "json": False,
            "account": "iCloud",
            "mailbox": "INBOX",
        }
        defaults.update(overrides)
        return Namespace(**defaults)

    return _create
