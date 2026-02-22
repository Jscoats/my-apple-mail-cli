"""Tests for error handling and edge cases."""

from argparse import Namespace
from unittest.mock import Mock, patch
import os

import pytest

from my_cli.config import FIELD_SEPARATOR, validate_limit
from my_cli.util.mail_helpers import resolve_message_context


class TestResolveMessageContextErrors:
    """Test error handling in resolve_message_context."""

    def test_dies_when_account_not_set(self, tmp_path, monkeypatch):
        """Should die with clear message when account is not set."""
        # Mock config dir to ensure no defaults exist
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        args = Namespace(account=None, mailbox=None)

        with pytest.raises(SystemExit) as exc_info:
            resolve_message_context(args)
        assert exc_info.value.code == 1

    def test_uses_default_mailbox_when_none(self, tmp_path, monkeypatch):
        """Should use DEFAULT_MAILBOX when mailbox is None."""
        # Mock config dir
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        args = Namespace(account="TestAccount", mailbox=None)
        account, mailbox, _, _ = resolve_message_context(args)

        assert account == "TestAccount"
        assert mailbox == "INBOX"  # DEFAULT_MAILBOX

    def test_escapes_special_characters(self, tmp_path, monkeypatch):
        """Should escape AppleScript special characters in account/mailbox."""
        # Mock config dir
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        args = Namespace(account='Test"Account', mailbox='Mail\\Box')
        _, _, acct_escaped, mb_escaped = resolve_message_context(args)

        # The escape function should handle quotes and backslashes
        assert '"' not in acct_escaped or '\\"' in acct_escaped
        assert '\\' not in mb_escaped or '\\\\' in mb_escaped


class TestAppleScriptErrorHandling:
    """Test that command functions handle AppleScript errors and malformed data gracefully."""

    def test_applescript_error_propagates_as_system_exit(self, monkeypatch):
        """cmd_batch_move should propagate SystemExit when run() exits due to an AppleScript error."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        # Simulate run() encountering an AppleScript error and calling sys.exit(1)
        def failing_run(script, **kwargs):
            raise SystemExit(1)
        monkeypatch.setattr("my_cli.commands.mail.batch.run", failing_run)

        args = Namespace(
            account="iCloud", from_sender="spam@example.com",
            to_mailbox="Archive", dry_run=False, limit=None, json=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            cmd_batch_move(args)
        assert exc_info.value.code == 1

    def test_cmd_read_with_malformed_applescript_output(self, monkeypatch, capsys):
        """cmd_read should fall back gracefully when run() returns fewer fields than expected."""
        from my_cli.commands.mail.messages import cmd_read

        monkeypatch.setattr(
            "my_cli.commands.mail.messages.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )
        # Return only 3 fields — far fewer than the 16 cmd_read expects
        malformed_output = f"42{FIELD_SEPARATOR}Subject Only{FIELD_SEPARATOR}sender@example.com"
        monkeypatch.setattr("my_cli.commands.mail.messages.run", Mock(return_value=malformed_output))

        args = Namespace(account="iCloud", mailbox="INBOX", id=42, short=False, json=False)
        # Should NOT raise — cmd_read has a graceful fallback for < 16 fields
        cmd_read(args)

        captured = capsys.readouterr()
        # The fallback branch prints the raw result under "Message details:"
        assert "Message details:" in captured.out

    def test_batch_delete_missing_filter_args_dies(self, monkeypatch):
        """cmd_batch_delete should exit with code 1 when neither --older-than nor --from-sender is given."""
        from my_cli.commands.mail.batch import cmd_batch_delete

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")

        args = Namespace(
            account="iCloud", mailbox=None,
            older_than=None, from_sender=None,
            dry_run=False, force=False, limit=None, json=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            cmd_batch_delete(args)
        assert exc_info.value.code == 1


class TestValidateLimitEdgeCases:
    """Extended test coverage for validate_limit beyond basic tests."""

    def test_very_large_negative_clamped(self):
        """Should clamp very large negative values to 1."""
        assert validate_limit(-999999) == 1

    def test_max_boundary(self):
        """Should accept MAX_MESSAGE_LIMIT exactly."""
        assert validate_limit(100) == 100

    def test_max_plus_one_clamped(self):
        """Should clamp MAX_MESSAGE_LIMIT + 1 to max."""
        assert validate_limit(101) == 100

    def test_mid_range_unchanged(self):
        """Should pass through mid-range values unchanged."""
        assert validate_limit(50) == 50

    def test_one_is_minimum(self):
        """Should accept 1 as minimum valid value."""
        assert validate_limit(1) == 1


class TestBatchOperationDryRun:
    """Test that batch commands honour the dry_run flag and report what WOULD be done."""

    def test_batch_move_dry_run_reports_would_move(self, monkeypatch, capsys):
        """cmd_batch_move with dry_run=True should print 'Would move' without actually moving."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        # First run() call returns the count of matching messages; second should NOT be called.
        mock_run = Mock(return_value="7")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = Namespace(
            account="iCloud", from_sender="newsletter@example.com",
            to_mailbox="Archive", dry_run=True, limit=None, json=False,
        )
        cmd_batch_move(args)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "Would move" in captured.out
        assert "7" in captured.out
        # Only the count script should have been executed — not the move script
        assert mock_run.call_count == 1

    def test_batch_move_dry_run_respects_limit(self, monkeypatch, capsys):
        """cmd_batch_move with dry_run=True and --limit should cap the reported count."""
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        # 50 matching messages, but limit is 10
        mock_run = Mock(return_value="50")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = Namespace(
            account="iCloud", from_sender="bulk@example.com",
            to_mailbox="Bulk", dry_run=True, limit=10, json=False,
        )
        cmd_batch_move(args)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "10" in captured.out  # effective count capped at limit
        assert "50" not in captured.out  # full total should not appear in text output

    def test_batch_delete_dry_run_reports_would_delete(self, monkeypatch, capsys):
        """cmd_batch_delete with dry_run=True should print 'Would delete' without deleting."""
        from my_cli.commands.mail.batch import cmd_batch_delete

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        # Count script returns 15 matching messages
        mock_run = Mock(return_value="15")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = Namespace(
            account="iCloud", mailbox="INBOX",
            older_than=30, from_sender=None,
            dry_run=True, force=False, limit=None, json=False,
        )
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "Would delete" in captured.out
        assert "15" in captured.out
        # Delete script must NOT have been called — only the count script
        assert mock_run.call_count == 1


# ---------------------------------------------------------------------------
# inbox_tools.py: cmd_process_inbox
# ---------------------------------------------------------------------------

class TestCmdProcessInbox:
    """Smoke tests for cmd_process_inbox."""

    def test_process_inbox_empty_returns_no_messages(self, monkeypatch, capsys):
        """Test that cmd_process_inbox reports no unread messages when run() returns empty."""
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="")
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", limit=50, json=False)
        cmd_process_inbox(args)

        captured = capsys.readouterr()
        assert "No unread messages" in captured.out

    def test_process_inbox_categorizes_messages(self, monkeypatch, capsys):
        """Test that cmd_process_inbox parses and categorizes messages from run() output."""
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")

        # Build mock data: one person email, one noreply notification, one flagged
        sep = FIELD_SEPARATOR
        person_line = f"iCloud{sep}101{sep}Hello from Alice{sep}Alice <alice@example.com>{sep}2026-02-20{sep}false"
        noreply_line = f"iCloud{sep}102{sep}Your receipt{sep}noreply@shop.com{sep}2026-02-21{sep}false"
        flagged_line = f"iCloud{sep}103{sep}Urgent task{sep}boss@work.com{sep}2026-02-22{sep}true"
        mock_result = "\n".join([person_line, noreply_line, flagged_line])

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", limit=50, json=False)
        cmd_process_inbox(args)

        captured = capsys.readouterr()
        assert "3 unread" in captured.out
        assert "FLAGGED" in captured.out
        assert "PEOPLE" in captured.out
        assert "NOTIFICATIONS" in captured.out
        assert "103" in captured.out  # flagged message ID
        assert "101" in captured.out  # people message ID
        assert "102" in captured.out  # notification message ID


# ---------------------------------------------------------------------------
# inbox_tools.py: cmd_weekly_review
# ---------------------------------------------------------------------------

class TestCmdWeeklyReview:
    """Smoke tests for cmd_weekly_review."""

    def test_weekly_review_empty_returns_none_sections(self, monkeypatch, capsys):
        """Test that cmd_weekly_review shows None sections when run() returns empty for all."""
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")
        # run() is called three times: flagged, attachments, unreplied — all empty
        mock_run = Mock(return_value="")
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", days=7, json=False)
        cmd_weekly_review(args)

        captured = capsys.readouterr()
        assert "Weekly Review" in captured.out
        assert "Flagged Messages (0)" in captured.out
        assert "Messages with Attachments (0)" in captured.out
        assert "Unreplied from People (0)" in captured.out
        assert "None" in captured.out
        assert mock_run.call_count == 3

    def test_weekly_review_with_flagged_data(self, monkeypatch, capsys):
        """Test that cmd_weekly_review shows flagged messages when run() returns data."""
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")

        sep = FIELD_SEPARATOR
        flagged_line = f"201{sep}Important meeting{sep}boss@work.com{sep}2026-02-20"
        attach_line = f"202{sep}Report attached{sep}colleague@work.com{sep}2026-02-21{sep}2"

        # run() is called 3 times: flagged, attachments, unreplied
        mock_run = Mock(side_effect=[flagged_line, attach_line, ""])
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", days=7, json=False)
        cmd_weekly_review(args)

        captured = capsys.readouterr()
        assert "Flagged Messages (1)" in captured.out
        assert "Important meeting" in captured.out
        assert "Messages with Attachments (1)" in captured.out
        assert "Report attached" in captured.out


# ---------------------------------------------------------------------------
# inbox_tools.py: cmd_clean_newsletters
# ---------------------------------------------------------------------------

class TestCmdCleanNewsletters:
    """Smoke tests for cmd_clean_newsletters."""

    def test_clean_newsletters_empty_reports_no_messages(self, monkeypatch, capsys):
        """Test that cmd_clean_newsletters reports no messages when run() returns empty."""
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="")
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", mailbox="INBOX", limit=200, json=False)
        cmd_clean_newsletters(args)

        captured = capsys.readouterr()
        assert "No messages found" in captured.out

    def test_clean_newsletters_identifies_bulk_sender(self, monkeypatch, capsys):
        """Test that cmd_clean_newsletters identifies a sender with 3+ messages as newsletter."""
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")

        sep = FIELD_SEPARATOR
        # newsletter@example.com appears 4 times — should be flagged as newsletter
        lines = [
            f"newsletter@example.com{sep}true",
            f"newsletter@example.com{sep}false",
            f"newsletter@example.com{sep}true",
            f"newsletter@example.com{sep}false",
            f"alice@personal.com{sep}false",  # only 1 — not a newsletter
        ]
        mock_run = Mock(return_value="\n".join(lines))
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", mailbox="INBOX", limit=200, json=False)
        cmd_clean_newsletters(args)

        captured = capsys.readouterr()
        assert "newsletter@example.com" in captured.out
        assert "4 messages" in captured.out
        # alice@personal.com has only 1 message and no noreply pattern — should NOT appear
        assert "alice@personal.com" not in captured.out

    def test_clean_newsletters_no_newsletters_found(self, monkeypatch, capsys):
        """Test that cmd_clean_newsletters reports when no newsletters are found."""
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.resolve_account", lambda _: "iCloud")

        sep = FIELD_SEPARATOR
        # Only one message per sender — none qualify as newsletter
        lines = [
            f"alice@personal.com{sep}false",
            f"bob@personal.com{sep}true",
        ]
        mock_run = Mock(return_value="\n".join(lines))
        monkeypatch.setattr("my_cli.commands.mail.inbox_tools.run", mock_run)

        args = Namespace(account="iCloud", mailbox="INBOX", limit=200, json=False)
        cmd_clean_newsletters(args)

        captured = capsys.readouterr()
        assert "No newsletter senders identified" in captured.out


# ---------------------------------------------------------------------------
# attachments.py: cmd_save_attachment
# ---------------------------------------------------------------------------

class TestCmdSaveAttachment:
    """Smoke tests for cmd_save_attachment."""

    def test_save_attachment_by_name(self, monkeypatch, capsys, tmp_path):
        """Test that cmd_save_attachment saves an attachment file by name."""
        from my_cli.commands.mail.attachments import cmd_save_attachment

        monkeypatch.setattr(
            "my_cli.commands.mail.attachments.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )

        att_name = "report.pdf"
        # list_script returns: subject line + attachment names
        list_result = f"Important Email\n{att_name}"
        # save_script returns: "saved"
        mock_run = Mock(side_effect=[list_result, "saved"])
        monkeypatch.setattr("my_cli.commands.mail.attachments.run", mock_run)

        # Create a fake saved file so the existence check passes
        fake_file = tmp_path / att_name
        fake_file.write_bytes(b"PDF content")

        # Patch os.path.isfile to return True for our fake path
        original_isfile = os.path.isfile
        def patched_isfile(p):
            if p == str(tmp_path / att_name):
                return True
            return original_isfile(p)
        monkeypatch.setattr("my_cli.commands.mail.attachments.os.path.isfile", patched_isfile)

        args = Namespace(
            account="iCloud", mailbox="INBOX", id=42,
            attachment=att_name, output_dir=str(tmp_path), json=False,
        )
        cmd_save_attachment(args)

        captured = capsys.readouterr()
        assert att_name in captured.out
        assert "Saved attachment" in captured.out

    def test_save_attachment_no_attachment_dies(self, monkeypatch):
        """Test that cmd_save_attachment exits when message has no attachments."""
        from my_cli.commands.mail.attachments import cmd_save_attachment

        monkeypatch.setattr(
            "my_cli.commands.mail.attachments.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )

        # list_script returns only subject line — no attachments
        mock_run = Mock(return_value="Empty Email")
        monkeypatch.setattr("my_cli.commands.mail.attachments.run", mock_run)

        args = Namespace(
            account="iCloud", mailbox="INBOX", id=42,
            attachment="file.pdf", output_dir="/tmp", json=False,
        )
        with pytest.raises(SystemExit):
            cmd_save_attachment(args)

    def test_save_attachment_by_index(self, monkeypatch, capsys, tmp_path):
        """Test that cmd_save_attachment resolves attachment by 1-based index."""
        from my_cli.commands.mail.attachments import cmd_save_attachment

        monkeypatch.setattr(
            "my_cli.commands.mail.attachments.resolve_message_context",
            lambda _: ("iCloud", "INBOX", "iCloud", "INBOX"),
        )

        att_name = "invoice.pdf"
        list_result = f"Subject Line\n{att_name}\nother.txt"
        mock_run = Mock(side_effect=[list_result, "saved"])
        monkeypatch.setattr("my_cli.commands.mail.attachments.run", mock_run)

        fake_file = tmp_path / att_name
        fake_file.write_bytes(b"data")

        original_isfile = os.path.isfile
        def patched_isfile(p):
            if p == str(tmp_path / att_name):
                return True
            return original_isfile(p)
        monkeypatch.setattr("my_cli.commands.mail.attachments.os.path.isfile", patched_isfile)

        args = Namespace(
            account="iCloud", mailbox="INBOX", id=42,
            attachment="1",  # index 1 → invoice.pdf
            output_dir=str(tmp_path), json=False,
        )
        cmd_save_attachment(args)

        captured = capsys.readouterr()
        assert att_name in captured.out
        assert "Saved attachment" in captured.out
