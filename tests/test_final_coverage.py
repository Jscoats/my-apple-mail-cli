"""Tests targeting the final coverage gaps in messages.py and config.py.

Covers:
- messages.py: _ai_summarize_previews (lines 44-92), cmd_list --summary (207),
  find_message_account (346-368), cmd_read auto-scan fallback (383-393),
  search_messages preview padding (543-544), cmd_search --summary (587)
- config.py: save_todoist_processed (257-262)
"""

import json
from argparse import Namespace
from unittest.mock import MagicMock, Mock, patch

from mxctl.config import FIELD_SEPARATOR


def _args(**kwargs):
    defaults = {"json": False, "account": "iCloud", "mailbox": "INBOX"}
    defaults.update(kwargs)
    return Namespace(**defaults)


def _full_read_msg():
    """Return a valid 16-field read_message response."""
    return FIELD_SEPARATOR.join(
        [
            "12345",
            "msg-id-12345",
            "Test Subject",
            "sender@test.com",
            "Mon Mar 01 2026",
            "true",
            "false",
            "false",
            "false",
            "false",
            "false",
            "to@test.com,",
            "cc@test.com,",
            "reply@test.com",
            "Message body here.",
            "2",
        ]
    )


# ===========================================================================
# messages.py — _ai_summarize_previews
# ===========================================================================


class TestAiSummarizePreviews:
    """Cover _ai_summarize_previews (lines 44-92)."""

    def test_no_api_key_returns_raw_previews(self, monkeypatch):
        """Without ANTHROPIC_API_KEY, falls back to truncated previews."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from mxctl.commands.mail.messages import _ai_summarize_previews

        msgs = [{"preview": "Hello world"}, {"preview": "Another one"}]
        result = _ai_summarize_previews(msgs)
        assert len(result) == 2
        assert result[0] == "Hello world"
        assert result[1] == "Another one"

    def test_empty_api_key_returns_raw_previews(self, monkeypatch):
        """Empty ANTHROPIC_API_KEY falls back to truncated previews."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        from mxctl.commands.mail.messages import _ai_summarize_previews

        msgs = [{"preview": "Hello"}]
        result = _ai_summarize_previews(msgs)
        assert result == ["Hello"]

    def test_successful_api_call(self, monkeypatch):
        """Successful API call returns parsed summaries."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        from mxctl.commands.mail.messages import _ai_summarize_previews

        api_response = json.dumps({"content": [{"text": "Summary one\nSummary two"}]}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = api_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            msgs = [{"subject": "T1", "sender": "a@b.com", "preview": "Hello"}, {"subject": "T2", "sender": "c@d.com", "preview": "World"}]
            result = _ai_summarize_previews(msgs)

        assert len(result) == 2
        assert result[0] == "Summary one"
        assert result[1] == "Summary two"

    def test_api_returns_fewer_summaries_pads(self, monkeypatch):
        """When API returns fewer summaries than messages, pad with empty strings."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        from mxctl.commands.mail.messages import _ai_summarize_previews

        api_response = json.dumps({"content": [{"text": "Only one"}]}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = api_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            msgs = [
                {"subject": "A", "sender": "a@b.com", "preview": "x"},
                {"subject": "B", "sender": "c@d.com", "preview": "y"},
                {"subject": "C", "sender": "e@f.com", "preview": "z"},
            ]
            result = _ai_summarize_previews(msgs)

        assert len(result) == 3
        assert result[1] == ""
        assert result[2] == ""

    def test_api_returns_more_summaries_truncates(self, monkeypatch):
        """When API returns more summaries than messages, truncate to message count."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        from mxctl.commands.mail.messages import _ai_summarize_previews

        api_response = json.dumps({"content": [{"text": "S1\nS2\nS3\nS4"}]}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = api_response
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            msgs = [{"subject": "A", "sender": "a@b.com", "preview": "x"}, {"subject": "B", "sender": "c@d.com", "preview": "y"}]
            result = _ai_summarize_previews(msgs)

        assert len(result) == 2

    def test_api_error_falls_back_to_raw(self, monkeypatch):
        """Any exception during API call falls back to raw previews."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        from mxctl.commands.mail.messages import _ai_summarize_previews

        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            msgs = [{"preview": "fallback text"}]
            result = _ai_summarize_previews(msgs)

        assert result == ["fallback text"]

    def test_missing_preview_key(self, monkeypatch):
        """Messages without 'preview' key get empty string."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from mxctl.commands.mail.messages import _ai_summarize_previews

        msgs = [{}]
        result = _ai_summarize_previews(msgs)
        assert result == [""]


# ===========================================================================
# messages.py — find_message_account
# ===========================================================================


class TestFindMessageAccount:
    """Cover find_message_account (lines 346-368)."""

    def test_found_returns_tuple(self, monkeypatch):
        """When message found, returns (account, mailbox) tuple."""
        from mxctl.commands.mail.messages import find_message_account

        mock_run = Mock(return_value=f"iCloud{FIELD_SEPARATOR}INBOX")
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)
        result = find_message_account(12345)
        assert result == ("iCloud", "INBOX")

    def test_empty_result_returns_none(self, monkeypatch):
        """Empty result means message not found."""
        from mxctl.commands.mail.messages import find_message_account

        mock_run = Mock(return_value="")
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)
        result = find_message_account(12345)
        assert result is None

    def test_whitespace_result_returns_none(self, monkeypatch):
        """Whitespace-only result means not found."""
        from mxctl.commands.mail.messages import find_message_account

        mock_run = Mock(return_value="   \n  ")
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)
        result = find_message_account(12345)
        assert result is None

    def test_single_part_returns_none(self, monkeypatch):
        """Result with fewer than 2 parts returns None."""
        from mxctl.commands.mail.messages import find_message_account

        mock_run = Mock(return_value="iCloud")
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)
        result = find_message_account(12345)
        assert result is None


# ===========================================================================
# messages.py — cmd_read auto-scan fallback
# ===========================================================================


class TestCmdReadAutoScan:
    """Cover the auto-scan fallback in cmd_read (lines 383-393)."""

    def test_auto_scan_finds_in_alt_account(self, monkeypatch, capsys):
        """When message not in default account and no -a flag, scan finds it elsewhere."""
        from mxctl.commands.mail.messages import cmd_read

        call_count = 0

        def side_effect(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # read_message: not found in default account (< 16 fields)
                return ""
            elif call_count == 2:
                # find_message_account: found in ASU Email / INBOX
                return f"ASU Email{FIELD_SEPARATOR}INBOX"
            elif call_count == 3:
                # read_message in alt account: success
                return _full_read_msg()
            return ""

        mock_run = Mock(side_effect=side_effect)
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)

        args = _args(id="12345", short=False, account=None)
        cmd_read(args)

        captured = capsys.readouterr()
        assert "ASU Email" in captured.err

    def test_auto_scan_not_triggered_with_explicit_account(self, monkeypatch, capsys):
        """When user passes -a explicitly, auto-scan is skipped."""
        from mxctl.commands.mail.messages import cmd_read

        mock_run = Mock(return_value="")
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)

        args = _args(id="12345", short=False, account="ASU Email")
        cmd_read(args)

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "Not found" in captured.out
        # find_message_account should NOT have been called — only 1 run() call
        assert mock_run.call_count == 1

    def test_auto_scan_message_not_found_anywhere(self, monkeypatch, capsys):
        """When auto-scan also fails, show not-found message."""
        from mxctl.commands.mail.messages import cmd_read

        call_count = 0

        def side_effect(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ""  # not found in default
            elif call_count == 2:
                return ""  # find_message_account: not found anywhere
            return ""

        mock_run = Mock(side_effect=side_effect)
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)

        args = _args(id="99999", short=False, account=None)
        cmd_read(args)

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "Not found" in captured.out


# ===========================================================================
# messages.py — cmd_list with --summary flag
# ===========================================================================


class TestCmdListSummary:
    """Cover the use_ai_summary branch in cmd_list (line 207)."""

    def test_list_with_summary_flag(self, monkeypatch, capsys):
        """--summary flag triggers _ai_summarize_previews."""
        from mxctl.commands.mail import messages

        msg_line = (
            f"100{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}"
            f"sender@test.com{FIELD_SEPARATOR}2026-03-01{FIELD_SEPARATOR}"
            f"true{FIELD_SEPARATOR}false{FIELD_SEPARATOR}Preview text"
        )
        mock_run = Mock(return_value=msg_line)
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)
        monkeypatch.setattr(messages, "_ai_summarize_previews", lambda msgs: ["AI summary"])
        monkeypatch.setattr(messages, "save_message_aliases", lambda ids: None)

        args = _args(limit=20, unread=False, after=None, before=None, summary=True)
        messages.cmd_list(args)

        captured = capsys.readouterr()
        assert "AI summary" in captured.out


# ===========================================================================
# messages.py — cmd_search with --summary flag
# ===========================================================================


class TestCmdSearchSummary:
    """Cover the use_ai_summary branch in cmd_search (line 587)."""

    def test_search_with_summary_flag(self, monkeypatch, capsys):
        """--summary flag triggers _ai_summarize_previews in search."""
        from mxctl.commands.mail import messages

        msg_line = (
            f"100{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}"
            f"sender@test.com{FIELD_SEPARATOR}2026-03-01{FIELD_SEPARATOR}"
            f"true{FIELD_SEPARATOR}false{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}"
            f"iCloud{FIELD_SEPARATOR}Preview text"
        )
        mock_run = Mock(return_value=msg_line)
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)
        monkeypatch.setattr(messages, "_ai_summarize_previews", lambda msgs: ["AI search sum"])
        monkeypatch.setattr(messages, "save_message_aliases", lambda ids: None)

        args = _args(query="test", sender=False, limit=20, summary=True, mailbox=None)
        messages.cmd_search(args)

        captured = capsys.readouterr()
        assert "AI search sum" in captured.out


# ===========================================================================
# messages.py — search_messages preview padding (line 543-544)
# ===========================================================================


class TestSearchMessagesPadding:
    """Cover the preview padding path in search_messages (line 543-544)."""

    def test_search_pads_missing_preview(self, monkeypatch):
        """When search result has no trailing preview, padding adds the separator."""
        from mxctl.commands.mail.messages import search_messages

        # 9 fields expected: id, subject, sender, date, read, flagged, mailbox, account, preview
        # Missing preview = 7 separators instead of 8
        line_without_preview = FIELD_SEPARATOR.join(
            [
                "100",
                "Subject",
                "sender@test.com",
                "2026-03-01",
                "true",
                "false",
                "INBOX",
                "iCloud",
            ]
        )
        mock_run = Mock(return_value=line_without_preview)
        monkeypatch.setattr("mxctl.commands.mail.messages.run", mock_run)

        result = search_messages("test", field="subject", account="iCloud", mailbox="INBOX", limit=20)
        assert len(result) == 1
        assert result[0]["preview"] == ""


# ===========================================================================
# config.py — save_todoist_processed
# ===========================================================================


class TestSaveTodoistProcessed:
    """Cover save_todoist_processed (lines 257-262)."""

    def test_records_todoist_send(self, tmp_path, monkeypatch):
        """save_todoist_processed stores message_id → task mapping in state."""
        from mxctl import config

        state_file = tmp_path / "state.json"
        state_file.write_text("{}")
        monkeypatch.setattr(config, "STATE_FILE", str(state_file))

        config.save_todoist_processed(12345, "task_abc", "2026-03-02")

        state = json.loads(state_file.read_text())
        assert "todoist_processed" in state
        assert "12345" in state["todoist_processed"]
        assert state["todoist_processed"]["12345"]["task_id"] == "task_abc"
        assert state["todoist_processed"]["12345"]["created"] == "2026-03-02"

    def test_appends_to_existing_todoist_state(self, tmp_path, monkeypatch):
        """save_todoist_processed appends to existing todoist_processed entries."""
        from mxctl import config

        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({"todoist_processed": {"999": {"task_id": "old", "created": "2026-01-01"}}}))
        monkeypatch.setattr(config, "STATE_FILE", str(state_file))

        config.save_todoist_processed(12345, "task_new", "2026-03-02")

        state = json.loads(state_file.read_text())
        assert "999" in state["todoist_processed"]
        assert "12345" in state["todoist_processed"]
