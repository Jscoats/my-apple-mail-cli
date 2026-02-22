"""Tests for enhanced stats and undo functionality."""

from unittest.mock import patch
import pytest
from my_cli.config import FIELD_SEPARATOR
from my_cli.commands.mail.analytics import cmd_stats



class TestEnhancedStats:
    """Test enhanced stats with --all flag."""

    @patch("my_cli.commands.mail.analytics.run")
    def test_stats_all_flag_shows_all_mailboxes(self, mock_run, mock_args, capsys):
        """Test that --all flag shows account-wide stats."""
        # Mock AppleScript output: grand totals on first line, then per-mailbox
        mock_run.return_value = (
            f"150{FIELD_SEPARATOR}25\n"  # Grand totals: 150 total, 25 unread
            f"INBOX{FIELD_SEPARATOR}100{FIELD_SEPARATOR}20\n"
            f"Sent Messages{FIELD_SEPARATOR}30{FIELD_SEPARATOR}0\n"
            f"Archive{FIELD_SEPARATOR}20{FIELD_SEPARATOR}5"
        )
        args = mock_args(account="iCloud", all=True, json=False, mailbox=None)

        cmd_stats(args)

        captured = capsys.readouterr()
        assert "Account: iCloud" in captured.out
        assert "Total: 150 messages, 25 unread" in captured.out
        assert "INBOX: 100 messages, 20 unread" in captured.out
        assert "Sent Messages: 30 messages, 0 unread" in captured.out
        assert "Archive: 20 messages, 5 unread" in captured.out

    @patch("my_cli.commands.mail.analytics.run")
    def test_stats_without_all_flag_single_mailbox(self, mock_run, mock_args, capsys):
        """Test that without --all flag, shows single mailbox stats."""
        mock_run.return_value = f"100{FIELD_SEPARATOR}20"  # 100 total, 20 unread
        args = mock_args(account="iCloud", all=False, json=False, mailbox="INBOX")

        cmd_stats(args)

        captured = capsys.readouterr()
        assert "INBOX [iCloud]: 100 messages, 20 unread" in captured.out


class TestUndoLogging:
    """Test undo operation logging."""

    def test_log_batch_operation_creates_entry(self, tmp_path, monkeypatch):
        """Test that logging a batch operation creates a proper entry."""
        import my_cli.commands.mail.undo as undo_module
        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[123, 456, 789],
            source_mailbox=None,
            dest_mailbox="Archive",
            sender="test@example.com",
        )

        # Reload and check
        operations = undo_module._load_undo_log()
        assert len(operations) == 1
        assert operations[0]["operation"] == "batch-move"
        assert operations[0]["account"] == "iCloud"
        assert operations[0]["message_ids"] == [123, 456, 789]
        assert operations[0]["dest_mailbox"] == "Archive"
        assert operations[0]["sender"] == "test@example.com"

    def test_undo_log_keeps_only_last_10_operations(self, tmp_path, monkeypatch):
        """Test that undo log is trimmed to MAX_UNDO_OPERATIONS."""
        import my_cli.commands.mail.undo as undo_module
        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Add 15 operations
        for i in range(15):
            undo_module.log_batch_operation(
                operation_type="batch-delete",
                account="iCloud",
                message_ids=[i],
                source_mailbox="Trash",
            )

        operations = undo_module._load_undo_log()
        assert len(operations) == 10  # Should keep only last 10

    def test_undo_list_shows_recent_operations(self, tmp_path, monkeypatch, mock_args, capsys):
        """Test that undo --list shows recent operations."""
        import my_cli.commands.mail.undo as undo_module
        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[100, 200],
            dest_mailbox="Archive",
            sender="test@example.com",
        )

        args = mock_args(json=False)
        undo_module.cmd_undo_list(args)

        captured = capsys.readouterr()
        assert "Recent batch operations" in captured.out
        assert "batch-move" in captured.out
        assert "2 messages" in captured.out

    def test_undo_list_empty_when_no_operations(self, tmp_path, monkeypatch, mock_args, capsys):
        """Test that undo --list shows appropriate message when empty."""
        import my_cli.commands.mail.undo as undo_module
        test_log = tmp_path / "mail-undo-empty.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        args = mock_args(json=False)
        undo_module.cmd_undo_list(args)

        captured = capsys.readouterr()
        assert "No recent batch operations to undo" in captured.out


class TestBatchDelete:
    """Tests for batch-delete --from-sender support."""

    @patch("my_cli.commands.mail.batch.run")
    def test_batch_delete_from_sender_dry_run(self, mock_run, mock_args, capsys):
        """Test --from-sender dry run reports match count without deleting."""
        mock_run.return_value = "5"  # count script returns 5
        args = mock_args(
            account="iCloud", mailbox=None, older_than=None,
            from_sender="noreply@example.com", dry_run=True, force=False, limit=None, json=False,
        )
        from my_cli.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "5" in captured.out
        assert "noreply@example.com" in captured.out
        # Only one run() call — the count script, no delete
        assert mock_run.call_count == 1

    @patch("my_cli.commands.mail.batch.run")
    def test_batch_delete_from_sender_scans_all_mailboxes(self, mock_run, mock_args, capsys):
        """Test --from-sender without -m uses all-mailboxes script."""
        mock_run.side_effect = ["3", "3\n101\n102\n103"]  # count, then delete
        args = mock_args(
            account="iCloud", mailbox=None, older_than=None,
            from_sender="spam@example.com", dry_run=False, force=True, limit=None, json=False,
        )
        from my_cli.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Deleted 3" in captured.out
        # Delete script should iterate all mailboxes (no single mailbox "of account")
        delete_script = mock_run.call_args_list[1][0][0]
        assert "mailboxes of account" in delete_script
        assert 'mailbox "' not in delete_script

    @patch("my_cli.commands.mail.batch.run")
    def test_batch_delete_from_sender_with_mailbox(self, mock_run, mock_args, capsys):
        """Test --from-sender -m scopes to a single mailbox."""
        mock_run.side_effect = ["2", "2\n201\n202"]
        args = mock_args(
            account="iCloud", mailbox="Junk", older_than=None,
            from_sender="spam@example.com", dry_run=False, force=True, limit=None, json=False,
        )
        from my_cli.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Deleted 2" in captured.out
        delete_script = mock_run.call_args_list[1][0][0]
        assert 'mailbox "Junk"' in delete_script

    @patch("my_cli.commands.mail.batch.run")
    def test_batch_delete_combined_filters(self, mock_run, mock_args, capsys):
        """Test --from-sender + --older-than builds combined where clause."""
        mock_run.side_effect = ["1", "1\n301"]
        args = mock_args(
            account="iCloud", mailbox="INBOX", older_than=30,
            from_sender="old@example.com", dry_run=False, force=True, limit=None, json=False,
        )
        from my_cli.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        count_script = mock_run.call_args_list[0][0][0]
        assert "sender contains" in count_script
        assert "date received <" in count_script

    def test_batch_delete_no_filters_raises(self, mock_args):
        """Test that providing neither --from-sender nor --older-than exits."""
        from my_cli.commands.mail.batch import cmd_batch_delete
        args = mock_args(
            account="iCloud", mailbox="INBOX", older_than=None,
            from_sender=None, dry_run=False, force=False, limit=None, json=False,
        )
        with pytest.raises(SystemExit):
            cmd_batch_delete(args)

    def test_batch_delete_older_than_without_mailbox_raises(self, mock_args):
        """Test that --older-than alone without -m exits for safety."""
        from my_cli.commands.mail.batch import cmd_batch_delete
        args = mock_args(
            account="iCloud", mailbox=None, older_than=30,
            from_sender=None, dry_run=False, force=False, limit=None, json=False,
        )
        with pytest.raises(SystemExit):
            cmd_batch_delete(args)


class TestCmdUndo:
    """Smoke tests for cmd_undo execution."""

    def test_undo_batch_move_calls_run_with_move_script(self, tmp_path, monkeypatch, mock_args, capsys):
        """Test that cmd_undo for batch-move calls run() with a script that moves messages back."""
        import my_cli.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Seed one batch-move operation
        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[101, 102],
            dest_mailbox="Archive",
            sender="sender@example.com",
        )

        mock_run = patch("my_cli.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "2"
            args = mock_args(json=False)
            undo_module.cmd_undo(args)

        # Verify run() was called and the script moves messages back to INBOX
        assert mocked.call_count == 1
        script_called = mocked.call_args[0][0]
        assert "move" in script_called.lower()
        assert "Archive" in script_called or "archive" in script_called.lower()
        assert "INBOX" in script_called

        captured = capsys.readouterr()
        assert "Undid batch-move" in captured.out
        assert "2/2" in captured.out

    def test_undo_batch_delete_restores_from_trash(self, tmp_path, monkeypatch, mock_args, capsys):
        """Test that cmd_undo for batch-delete moves messages from Trash back to source."""
        import my_cli.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Seed one batch-delete operation
        undo_module.log_batch_operation(
            operation_type="batch-delete",
            account="iCloud",
            message_ids=[201, 202, 203],
            source_mailbox="INBOX",
            sender="deleted@example.com",
        )

        mock_run = patch("my_cli.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "3"
            args = mock_args(json=False)
            undo_module.cmd_undo(args)

        # Verify run() was called with a script referencing Trash
        assert mocked.call_count == 1
        script_called = mocked.call_args[0][0]
        assert "Trash" in script_called
        assert "move" in script_called.lower()

        captured = capsys.readouterr()
        assert "Undid batch-delete" in captured.out
        assert "3/3" in captured.out
