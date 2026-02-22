"""Tests for compose.py error paths and batch.py dry-run edge cases."""

import json
from argparse import Namespace
from unittest.mock import Mock, patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**kwargs):
    defaults = {"json": False, "account": "iCloud", "mailbox": "INBOX"}
    defaults.update(kwargs)
    return Namespace(**defaults)


# ---------------------------------------------------------------------------
# compose.py: cmd_draft error paths
# ---------------------------------------------------------------------------

class TestDraftErrors:
    def test_draft_no_account_dies(self, monkeypatch):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: None)

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(account=None, to="x@y.com", subject="S", body="B",
                                 template=None, cc=None, bcc=None))

    def test_draft_no_subject_no_template_dies(self, monkeypatch):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body="hello",
                                 template=None, cc=None, bcc=None))

    def test_draft_no_body_no_template_dies(self, monkeypatch):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject="hello", body=None,
                                 template=None, cc=None, bcc=None))

    def test_draft_template_not_found_dies(self, monkeypatch, tmp_path):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        # Create a valid templates file without the requested template
        tpl_file = str(tmp_path / "templates.json")
        with open(tpl_file, "w") as f:
            json.dump({"other": {"subject": "S", "body": "B"}}, f)

        monkeypatch.setattr("my_cli.commands.mail.compose.TEMPLATES_FILE", tpl_file)

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body=None,
                                 template="missing", cc=None, bcc=None))

    def test_draft_corrupt_template_file_dies(self, monkeypatch, tmp_path):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        tpl_file = str(tmp_path / "templates.json")
        with open(tpl_file, "w") as f:
            f.write("{corrupt json")

        monkeypatch.setattr("my_cli.commands.mail.compose.TEMPLATES_FILE", tpl_file)

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body=None,
                                 template="any", cc=None, bcc=None))

    def test_draft_no_templates_file_dies(self, monkeypatch, tmp_path):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")
        monkeypatch.setattr("my_cli.commands.mail.compose.TEMPLATES_FILE",
                            str(tmp_path / "nonexistent.json"))

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body=None,
                                 template="any", cc=None, bcc=None))


# ---------------------------------------------------------------------------
# batch.py: dry-run effective_count edge cases
# ---------------------------------------------------------------------------

class TestBatchMoveEffectiveCount:
    def test_dry_run_with_limit_caps_count(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="50")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="test@x.com", to_mailbox="Archive",
                          dry_run=True, limit=10)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "Would move 10 messages" in out  # effective_count = min(50, 10) = 10

    def test_dry_run_without_limit_uses_total(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="25")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="test@x.com", to_mailbox="Archive",
                          dry_run=True, limit=None)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "Would move 25 messages" in out  # effective_count = total = 25


class TestBatchDeleteEffectiveCount:
    def test_dry_run_with_limit_caps_count(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_delete

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="100")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="spam@x.com", older_than=None,
                          dry_run=True, limit=20, force=False)
        cmd_batch_delete(args)

        out = capsys.readouterr().out
        assert "Would delete 20 messages" in out  # effective_count = min(100, 20) = 20

    def test_dry_run_without_limit_uses_total(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_delete

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="42")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="spam@x.com", older_than=None,
                          dry_run=True, limit=None, force=False)
        cmd_batch_delete(args)

        out = capsys.readouterr().out
        assert "Would delete 42 messages" in out  # effective_count = total = 42


# ---------------------------------------------------------------------------
# todoist_integration.py: cmd_to_todoist
# ---------------------------------------------------------------------------

class TestCmdToTodoist:
    def test_to_todoist_missing_token_dies(self, monkeypatch):
        """Test that missing Todoist API token causes SystemExit."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        monkeypatch.setattr(
            "my_cli.commands.mail.todoist_integration.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )
        monkeypatch.setattr(
            "my_cli.commands.mail.todoist_integration.get_config",
            lambda: {},  # no todoist_api_token
        )

        args = _make_args(id=42, project=None, priority=1, due=None)
        with pytest.raises(SystemExit):
            cmd_to_todoist(args)

    def test_to_todoist_happy_path(self, monkeypatch, capsys):
        """Test that cmd_to_todoist creates a task via the API."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist
        from my_cli.config import FIELD_SEPARATOR

        monkeypatch.setattr(
            "my_cli.commands.mail.todoist_integration.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )
        monkeypatch.setattr(
            "my_cli.commands.mail.todoist_integration.get_config",
            lambda: {"todoist_api_token": "test-token-123"},
        )

        # Mock AppleScript run to return message data
        mock_run = Mock(
            return_value=f"Test Subject{FIELD_SEPARATOR}sender@example.com{FIELD_SEPARATOR}2026-01-15"
        )
        monkeypatch.setattr("my_cli.commands.mail.todoist_integration.run", mock_run)

        # Mock the urllib HTTP call
        fake_response_data = {"id": "task-999", "content": "Test Subject", "url": "https://todoist.com/tasks/999"}
        fake_response = MagicMock()
        fake_response.__enter__ = lambda s: s
        fake_response.__exit__ = Mock(return_value=False)
        fake_response.read.return_value = json.dumps(fake_response_data).encode("utf-8")

        with patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen", return_value=fake_response):
            args = _make_args(id=42, project=None, priority=1, due=None)
            cmd_to_todoist(args)

        out = capsys.readouterr().out
        assert "Test Subject" in out
        assert "Created Todoist task" in out


# ---------------------------------------------------------------------------
# actions.py: cmd_unsubscribe
# ---------------------------------------------------------------------------

class TestCmdUnsubscribe:
    def test_unsubscribe_dry_run_shows_list_unsubscribe_url(self, monkeypatch, capsys):
        """Test that --dry-run shows the List-Unsubscribe URL from headers."""
        from my_cli.commands.mail.actions import cmd_unsubscribe
        from my_cli.config import FIELD_SEPARATOR

        monkeypatch.setattr(
            "my_cli.commands.mail.actions.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )

        # AppleScript returns subject + raw headers containing List-Unsubscribe
        unsub_url = "https://example.com/unsubscribe?token=abc123"
        raw_headers = (
            f"List-Unsubscribe: <{unsub_url}>\n"
            "From: newsletter@example.com\n"
        )
        mock_run = Mock(
            return_value=f"Newsletter Subject{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}{raw_headers}"
        )
        monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

        args = _make_args(id=99, dry_run=True, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert unsub_url in out
        assert "HTTPS" in out or "https" in out.lower()


# ---------------------------------------------------------------------------
# compose.py: cmd_draft happy path
# ---------------------------------------------------------------------------

class TestDraftHappyPath:
    def test_draft_creates_draft_successfully(self, monkeypatch, capsys):
        """Test that cmd_draft succeeds and prints the draft creation message."""
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="draft created")
        monkeypatch.setattr("my_cli.commands.mail.compose.run", mock_run)

        args = _make_args(to="recipient@example.com", subject="Hello there",
                          body="This is the email body.", template=None,
                          cc=None, bcc=None)
        cmd_draft(args)

        out = capsys.readouterr().out
        assert "Draft created successfully!" in out
        assert "To: recipient@example.com" in out
        assert "Subject: Hello there" in out
        assert mock_run.called

    def test_draft_with_cc_and_bcc_shows_recipients(self, monkeypatch, capsys):
        """Test that cmd_draft includes CC and BCC in the output."""
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="draft created")
        monkeypatch.setattr("my_cli.commands.mail.compose.run", mock_run)

        args = _make_args(to="recipient@example.com", subject="Meeting",
                          body="Let's meet.", template=None,
                          cc="cc@example.com", bcc="bcc@example.com")
        cmd_draft(args)

        out = capsys.readouterr().out
        assert "Draft created successfully!" in out
        assert "CC: cc@example.com" in out
        assert "BCC: bcc@example.com" in out

    def test_draft_output_mentions_mail_app(self, monkeypatch, capsys):
        """Test that the draft success message refers to Mail.app."""
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="draft created")
        monkeypatch.setattr("my_cli.commands.mail.compose.run", mock_run)

        args = _make_args(to="someone@example.com", subject="Test subject",
                          body="Test body text.", template=None,
                          cc=None, bcc=None)
        cmd_draft(args)

        out = capsys.readouterr().out
        assert "Mail.app" in out
        assert "manually click Send" in out


# ---------------------------------------------------------------------------
# batch.py: cmd_batch_read
# ---------------------------------------------------------------------------

class TestBatchRead:
    def test_batch_read_no_account_dies(self, monkeypatch):
        """Test that cmd_batch_read dies when no account is resolved."""
        from my_cli.commands.mail.batch import cmd_batch_read

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: None)

        with pytest.raises(SystemExit):
            cmd_batch_read(_make_args(account=None))

    def test_batch_read_marks_messages_and_reports_count(self, monkeypatch, capsys):
        """Test that cmd_batch_read reports the number of messages marked as read."""
        from my_cli.commands.mail.batch import cmd_batch_read

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="7")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(mailbox="INBOX")
        cmd_batch_read(args)

        out = capsys.readouterr().out
        assert "Marked 7 messages as read" in out
        assert "INBOX" in out
        assert "iCloud" in out

    def test_batch_read_zero_messages_reports_zero(self, monkeypatch, capsys):
        """Test that cmd_batch_read handles zero unread messages gracefully."""
        from my_cli.commands.mail.batch import cmd_batch_read

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="0")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(mailbox="INBOX")
        cmd_batch_read(args)

        out = capsys.readouterr().out
        assert "Marked 0 messages as read" in out

    def test_batch_read_non_digit_result_treated_as_zero(self, monkeypatch, capsys):
        """Test that non-digit AppleScript output is treated as zero count."""
        from my_cli.commands.mail.batch import cmd_batch_read

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="error")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(mailbox="INBOX")
        cmd_batch_read(args)

        out = capsys.readouterr().out
        assert "Marked 0 messages as read" in out


# ---------------------------------------------------------------------------
# batch.py: cmd_batch_flag
# ---------------------------------------------------------------------------

class TestBatchFlag:
    def test_batch_flag_no_account_dies(self, monkeypatch):
        """Test that cmd_batch_flag dies when no account is resolved."""
        from my_cli.commands.mail.batch import cmd_batch_flag

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: None)

        with pytest.raises(SystemExit):
            cmd_batch_flag(_make_args(account=None, from_sender="sender@x.com"))

    def test_batch_flag_no_sender_dies(self, monkeypatch):
        """Test that cmd_batch_flag dies when --from-sender is missing."""
        from my_cli.commands.mail.batch import cmd_batch_flag

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_batch_flag(_make_args(from_sender=None))

    def test_batch_flag_flags_messages_and_reports_count(self, monkeypatch, capsys):
        """Test that cmd_batch_flag reports the number of flagged messages."""
        from my_cli.commands.mail.batch import cmd_batch_flag

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="5")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="newsletter@example.com")
        cmd_batch_flag(args)

        out = capsys.readouterr().out
        assert "Flagged 5 messages" in out
        assert "newsletter@example.com" in out
        assert "iCloud" in out

    def test_batch_flag_zero_messages_reports_zero(self, monkeypatch, capsys):
        """Test that cmd_batch_flag handles zero matching messages gracefully."""
        from my_cli.commands.mail.batch import cmd_batch_flag

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="0")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="nobody@example.com")
        cmd_batch_flag(args)

        out = capsys.readouterr().out
        assert "Flagged 0 messages" in out


# ---------------------------------------------------------------------------
# batch.py: cmd_batch_move execution path (non-dry-run)
# ---------------------------------------------------------------------------

class TestBatchMoveExecution:
    def test_batch_move_no_account_dies(self, monkeypatch):
        """Test that cmd_batch_move dies when no account is resolved."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: None)

        with pytest.raises(SystemExit):
            cmd_batch_move(_make_args(account=None, from_sender="s@x.com",
                                      to_mailbox="Archive", dry_run=False, limit=None))

    def test_batch_move_no_sender_dies(self, monkeypatch):
        """Test that cmd_batch_move dies when --from-sender is missing."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_batch_move(_make_args(from_sender=None, to_mailbox="Archive",
                                      dry_run=False, limit=None))

    def test_batch_move_no_dest_mailbox_dies(self, monkeypatch):
        """Test that cmd_batch_move dies when --to-mailbox is missing."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_batch_move(_make_args(from_sender="s@x.com", to_mailbox=None,
                                      dry_run=False, limit=None))

    def test_batch_move_actually_moves_messages(self, monkeypatch, capsys):
        """Test the live execution path of cmd_batch_move (not dry-run)."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_mailbox",
                            lambda account, mailbox: mailbox)

        # First call returns count (3 messages), second call returns move result
        # Move result: count on line 0, message IDs on subsequent lines
        move_result = "3\n1001\n1002\n1003"
        mock_run = Mock(side_effect=["3", move_result])
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        mock_log = Mock()
        monkeypatch.setattr("my_cli.commands.mail.batch.log_batch_operation", mock_log)

        args = _make_args(from_sender="sender@example.com", to_mailbox="Archive",
                          dry_run=False, limit=None)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "Moved 3 messages" in out
        assert "sender@example.com" in out
        assert "Archive" in out

        # Verify that log_batch_operation was called with correct parameters
        mock_log.assert_called_once_with(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[1001, 1002, 1003],
            source_mailbox=None,
            dest_mailbox="Archive",
            sender="sender@example.com",
        )

    def test_batch_move_zero_matching_messages_skips_move(self, monkeypatch, capsys):
        """Test that cmd_batch_move exits early when no messages match."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_mailbox",
                            lambda account, mailbox: mailbox)
        mock_run = Mock(return_value="0")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="nobody@example.com", to_mailbox="Archive",
                          dry_run=False, limit=None)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "No messages found" in out
        # run() should only have been called once (the count script, no move script)
        assert mock_run.call_count == 1

    def test_batch_move_execution_with_limit(self, monkeypatch, capsys):
        """Test that cmd_batch_move respects --limit during actual move."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_mailbox",
                            lambda account, mailbox: mailbox)

        move_result = "2\n2001\n2002"
        mock_run = Mock(side_effect=["10", move_result])
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        mock_log = Mock()
        monkeypatch.setattr("my_cli.commands.mail.batch.log_batch_operation", mock_log)

        args = _make_args(from_sender="bulk@example.com", to_mailbox="Bulk",
                          dry_run=False, limit=2)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "Moved 2 messages" in out
