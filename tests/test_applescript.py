"""Tests for applescript module."""

import os

from my_cli.util.applescript import escape, sanitize_path


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
