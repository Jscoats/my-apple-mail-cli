"""Tests for applescript module."""

import os
from unittest.mock import Mock

import pytest

from my_cli.util.applescript import escape, run, sanitize_path


class TestEscape:
    """Test string escaping for AppleScript."""

    def test_normal_string(self):
        assert escape("hello world") == "hello world"

    def test_quotes(self):
        assert escape('say "hello"') == 'say \\"hello\\"'

    def test_backslashes(self):
        assert escape("path\\to\\file") == "path\\\\to\\\\file"

    def test_newlines_lf(self):
        assert escape("line1\nline2") == "line1\\nline2"

    def test_newlines_cr(self):
        assert escape("line1\rline2") == "line1\\rline2"

    def test_none_returns_empty(self):
        assert escape(None) == ""

    def test_null_bytes_stripped(self):
        assert escape("hello\x00world") == "helloworld"

    def test_combined_escaping(self):
        assert escape('path\\name\n"quote"') == 'path\\\\name\\n\\"quote\\"'


class TestSanitizePath:
    """Test path sanitization."""

    def test_tilde_expansion(self):
        result = sanitize_path("~/test")
        assert result == os.path.join(os.path.expanduser("~"), "test")

    def test_relative_path(self):
        result = sanitize_path("./test")
        assert result == os.path.abspath("./test")

    def test_absolute_path(self):
        result = sanitize_path("/tmp/test")
        assert result == "/tmp/test"


class TestRunSmartQuotes:
    """Test that smart-quoted AppleScript errors trigger friendly messages."""

    def test_smart_quote_account_not_found(self, monkeypatch, capsys):
        """Smart-quoted can\u2019t get account triggers friendly error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Can\u2019t get account \"Foo\". (-1728)"

        monkeypatch.setattr("my_cli.util.applescript.subprocess.run", lambda *a, **kw: mock_result)

        with pytest.raises(SystemExit):
            run("dummy script")

        captured = capsys.readouterr()
        assert "Account not found" in captured.err

    def test_smart_quote_message_not_found(self, monkeypatch, capsys):
        """Smart-quoted can\u2019t get message triggers friendly error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Can\u2019t get message 1 of mailbox \"INBOX\". (-1719)"

        monkeypatch.setattr("my_cli.util.applescript.subprocess.run", lambda *a, **kw: mock_result)

        with pytest.raises(SystemExit):
            run("dummy script")

        captured = capsys.readouterr()
        assert "Message not found" in captured.err

    def test_straight_quote_still_works(self, monkeypatch, capsys):
        """ASCII straight-quoted can't get account still works."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Can't get account \"Bar\". (-1728)"

        monkeypatch.setattr("my_cli.util.applescript.subprocess.run", lambda *a, **kw: mock_result)

        with pytest.raises(SystemExit):
            run("dummy script")

        captured = capsys.readouterr()
        assert "Account not found" in captured.err
