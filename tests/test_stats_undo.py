"""Tests for enhanced stats and undo functionality."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from mxctl.commands.mail.analytics import cmd_stats
from mxctl.config import FIELD_SEPARATOR


class TestEnhancedStats:
    """Test enhanced stats with --all flag."""

    @patch("mxctl.commands.mail.analytics.run")
    def test_stats_all_flag_shows_all_mailboxes(self, mock_run, mock_args, capsys):
        """Test that --all flag shows account-wide stats."""
        # Mock AppleScript output: grand totals on first line, then per-mailbox
        # Format: acctName|mbName|total|unread (4 fields per mailbox line)
        mock_run.return_value = (
            f"150{FIELD_SEPARATOR}25\n"  # Grand totals: 150 total, 25 unread
            f"iCloud{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}100{FIELD_SEPARATOR}20\n"
            f"iCloud{FIELD_SEPARATOR}Sent Messages{FIELD_SEPARATOR}30{FIELD_SEPARATOR}0\n"
            f"iCloud{FIELD_SEPARATOR}Archive{FIELD_SEPARATOR}20{FIELD_SEPARATOR}5"
        )
        args = mock_args(account="iCloud", all=True, json=False, mailbox=None)

        cmd_stats(args)

        captured = capsys.readouterr()
        assert "Account: iCloud" in captured.out
        assert "Total: 150 messages, 25 unread" in captured.out
        assert "INBOX: 100 messages, 20 unread" in captured.out
        assert "Sent Messages: 30 messages, 0 unread" in captured.out
        assert "Archive: 20 messages, 5 unread" in captured.out

    @patch("mxctl.commands.mail.analytics.resolve_account", return_value=None)
    @patch("mxctl.commands.mail.analytics.run")
    def test_stats_all_no_account_shows_all_accounts(self, mock_run, mock_resolve, mock_args, capsys):
        """Test that --all without -a aggregates across all configured accounts."""
        # No account scoping — output includes multiple accounts
        mock_run.return_value = (
            f"250{FIELD_SEPARATOR}30\n"  # Grand totals
            f"iCloud{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}100{FIELD_SEPARATOR}20\n"
            f"Gmail{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}150{FIELD_SEPARATOR}10\n"
        )
        args = mock_args(account=None, all=True, json=False, mailbox=None)

        cmd_stats(args)

        captured = capsys.readouterr()
        assert "All Accounts" in captured.out
        assert "Total: 250 messages, 30 unread" in captured.out
        assert "[iCloud] INBOX" in captured.out
        assert "[Gmail] INBOX" in captured.out

    @patch("mxctl.commands.mail.analytics.run")
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
        import mxctl.commands.mail.undo as undo_module
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
        import mxctl.commands.mail.undo as undo_module
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
        import mxctl.commands.mail.undo as undo_module
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
        import mxctl.commands.mail.undo as undo_module
        test_log = tmp_path / "mail-undo-empty.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        args = mock_args(json=False)
        undo_module.cmd_undo_list(args)

        captured = capsys.readouterr()
        assert "No recent batch operations to undo" in captured.out


class TestBatchDelete:
    """Tests for batch-delete --from-sender support."""

    @patch("mxctl.commands.mail.batch.run")
    def test_batch_delete_from_sender_dry_run(self, mock_run, mock_args, capsys):
        """Test --from-sender dry run reports match count without deleting."""
        mock_run.return_value = "5"  # count script returns 5
        args = mock_args(
            account="iCloud", mailbox=None, older_than=None,
            from_sender="noreply@example.com", dry_run=True, force=False, limit=None, json=False,
        )
        from mxctl.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "5" in captured.out
        assert "noreply@example.com" in captured.out
        # Only one run() call — the count script, no delete
        assert mock_run.call_count == 1

    @patch("mxctl.commands.mail.batch.run")
    def test_batch_delete_from_sender_scans_all_mailboxes(self, mock_run, mock_args, capsys):
        """Test --from-sender without -m uses all-mailboxes script."""
        mock_run.side_effect = ["3", "3\n101\n102\n103"]  # count, then delete
        args = mock_args(
            account="iCloud", mailbox=None, older_than=None,
            from_sender="spam@example.com", dry_run=False, force=True, limit=None, json=False,
        )
        from mxctl.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Deleted 3" in captured.out
        # Delete script should iterate all mailboxes (no single mailbox "of account")
        delete_script = mock_run.call_args_list[1][0][0]
        assert "mailboxes of account" in delete_script
        assert 'mailbox "' not in delete_script

    @patch("mxctl.commands.mail.batch.run")
    def test_batch_delete_from_sender_with_mailbox(self, mock_run, mock_args, capsys):
        """Test --from-sender -m scopes to a single mailbox."""
        mock_run.side_effect = ["2", "2\n201\n202"]
        args = mock_args(
            account="iCloud", mailbox="Junk", older_than=None,
            from_sender="spam@example.com", dry_run=False, force=True, limit=None, json=False,
        )
        from mxctl.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        captured = capsys.readouterr()
        assert "Deleted 2" in captured.out
        delete_script = mock_run.call_args_list[1][0][0]
        assert 'mailbox "Junk"' in delete_script

    @patch("mxctl.commands.mail.batch.run")
    def test_batch_delete_combined_filters(self, mock_run, mock_args, capsys):
        """Test --from-sender + --older-than builds combined where clause."""
        mock_run.side_effect = ["1", "1\n301"]
        args = mock_args(
            account="iCloud", mailbox="INBOX", older_than=30,
            from_sender="old@example.com", dry_run=False, force=True, limit=None, json=False,
        )
        from mxctl.commands.mail.batch import cmd_batch_delete
        cmd_batch_delete(args)

        count_script = mock_run.call_args_list[0][0][0]
        assert "sender contains" in count_script
        assert "date received <" in count_script

    def test_batch_delete_no_filters_raises(self, mock_args):
        """Test that providing neither --from-sender nor --older-than exits."""
        from mxctl.commands.mail.batch import cmd_batch_delete
        args = mock_args(
            account="iCloud", mailbox="INBOX", older_than=None,
            from_sender=None, dry_run=False, force=False, limit=None, json=False,
        )
        with pytest.raises(SystemExit):
            cmd_batch_delete(args)

    def test_batch_delete_older_than_without_mailbox_raises(self, mock_args):
        """Test that --older-than alone without -m exits for safety."""
        from mxctl.commands.mail.batch import cmd_batch_delete
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
        import mxctl.commands.mail.undo as undo_module

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

        mock_run = patch("mxctl.commands.mail.undo.run")
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
        import mxctl.commands.mail.undo as undo_module

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

        mock_run = patch("mxctl.commands.mail.undo.run")
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


class TestUndoStaleness:
    """Tests for the 30-minute freshness window and --force flag."""

    def test_undo_rejects_stale_entry_without_force(self, tmp_path, monkeypatch, mock_args):
        """Stale entry (>30 min old) should cause die() without --force."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Write a stale entry directly (60 minutes ago)
        stale_ts = (datetime.now() - timedelta(minutes=60)).isoformat()
        test_log.write_text(json.dumps([{
            "timestamp": stale_ts,
            "operation": "batch-delete",
            "account": "iCloud",
            "message_ids": [999],
            "source_mailbox": "INBOX",
            "dest_mailbox": None,
            "sender": None,
            "older_than_days": None,
        }]))

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

    def test_undo_force_bypasses_staleness(self, tmp_path, monkeypatch, mock_args, capsys):
        """--force should run the undo even if the entry is older than 30 minutes."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        stale_ts = (datetime.now() - timedelta(minutes=60)).isoformat()
        test_log.write_text(json.dumps([{
            "timestamp": stale_ts,
            "operation": "batch-delete",
            "account": "iCloud",
            "message_ids": [999],
            "source_mailbox": "INBOX",
            "dest_mailbox": None,
            "sender": None,
            "older_than_days": None,
        }]))

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "1"
            args = mock_args(json=False, force=True)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "Undid batch-delete" in captured.out

    def test_undo_stale_message_mentions_age_and_force(self, tmp_path, monkeypatch, mock_args, capsys):
        """Stale-entry error message should mention minutes and --force."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        stale_ts = (datetime.now() - timedelta(minutes=45)).isoformat()
        test_log.write_text(json.dumps([{
            "timestamp": stale_ts,
            "operation": "batch-move",
            "account": "iCloud",
            "message_ids": [888],
            "source_mailbox": None,
            "dest_mailbox": "Archive",
            "sender": "old@example.com",
            "older_than_days": None,
        }]))

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "minutes ago" in captured.err
        assert "--force" in captured.err

    def test_undo_fresh_entry_executes_normally(self, tmp_path, monkeypatch, mock_args, capsys):
        """Fresh entry (<30 min old) should execute without --force."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Log a fresh operation
        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[111],
            dest_mailbox="Archive",
            sender="test@example.com",
        )

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "1"
            args = mock_args(json=False, force=False)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "Undid batch-move" in captured.out


class TestEntryAgeFreshness:
    """Tests for _entry_age_minutes and _is_fresh helper functions."""

    def test_entry_age_minutes_no_timestamp(self):
        """_entry_age_minutes returns None when timestamp is missing (line 26)."""
        import mxctl.commands.mail.undo as undo_module

        result = undo_module._entry_age_minutes({})
        assert result is None

    def test_entry_age_minutes_invalid_timestamp(self):
        """_entry_age_minutes returns None for garbage timestamp (lines 30-31)."""
        import mxctl.commands.mail.undo as undo_module

        result = undo_module._entry_age_minutes({"timestamp": "not-a-date"})
        assert result is None

    def test_entry_age_minutes_valid_timestamp(self):
        """_entry_age_minutes returns positive float for a recent timestamp."""
        import mxctl.commands.mail.undo as undo_module

        ts = datetime.now().isoformat()
        result = undo_module._entry_age_minutes({"timestamp": ts})
        assert result is not None
        assert result >= 0

    def test_is_fresh_no_timestamp_returns_false(self):
        """_is_fresh returns False when age is None (line 38)."""
        import mxctl.commands.mail.undo as undo_module

        result = undo_module._is_fresh({})
        assert result is False

    def test_is_fresh_stale_entry_returns_false(self):
        """_is_fresh returns False for entry older than UNDO_MAX_AGE_MINUTES."""
        import mxctl.commands.mail.undo as undo_module

        stale_ts = (datetime.now() - timedelta(minutes=60)).isoformat()
        result = undo_module._is_fresh({"timestamp": stale_ts})
        assert result is False

    def test_is_fresh_fresh_entry_returns_true(self):
        """_is_fresh returns True for entry younger than UNDO_MAX_AGE_MINUTES."""
        import mxctl.commands.mail.undo as undo_module

        fresh_ts = datetime.now().isoformat()
        result = undo_module._is_fresh({"timestamp": fresh_ts})
        assert result is True


class TestLoadUndoLogEdgeCases:
    """Tests for _load_undo_log edge cases."""

    def test_load_undo_log_invalid_json(self, tmp_path, monkeypatch):
        """_load_undo_log returns [] for corrupted JSON (lines 53-54)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        test_log.write_text("{invalid json content!!")
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        result = undo_module._load_undo_log()
        assert result == []

    def test_load_undo_log_include_stale(self, tmp_path, monkeypatch):
        """_load_undo_log(include_stale=True) returns stale entries too."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        stale_ts = (datetime.now() - timedelta(minutes=60)).isoformat()
        test_log.write_text(json.dumps([{
            "timestamp": stale_ts,
            "operation": "batch-move",
            "account": "iCloud",
            "message_ids": [1],
        }]))
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Without include_stale: empty (stale entry filtered)
        result_fresh = undo_module._load_undo_log(include_stale=False)
        assert len(result_fresh) == 0

        # With include_stale: returns the entry
        result_all = undo_module._load_undo_log(include_stale=True)
        assert len(result_all) == 1


class TestLogFenceOperation:
    """Tests for log_fence_operation (lines 99-105)."""

    def test_fence_operation_creates_fence_entry(self, tmp_path, monkeypatch):
        """log_fence_operation creates a fence sentinel entry."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_fence_operation("batch-read")

        operations = undo_module._load_undo_log(include_stale=True)
        assert len(operations) == 1
        assert operations[0]["type"] == "fence"
        assert operations[0]["operation"] == "batch-read"
        assert "timestamp" in operations[0]


class TestUndoListFences:
    """Tests for cmd_undo_list with fence entries and mixed entries."""

    def test_undo_list_shows_fence_as_no_undo(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo_list marks fence entries as [no undo] (lines 127, 131)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Create a normal operation first
        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[1, 2],
            dest_mailbox="Archive",
            sender="test@x.com",
        )
        # Then a fence
        undo_module.log_fence_operation("batch-read")

        args = mock_args(json=False)
        undo_module.cmd_undo_list(args)

        captured = capsys.readouterr()
        assert "[no undo]" in captured.out
        assert "batch-read" in captured.out
        assert "batch-move" in captured.out

    def test_undo_list_shows_older_than_days(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo_list shows older_than_days when present (line 131)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_batch_operation(
            operation_type="batch-delete",
            account="iCloud",
            message_ids=[1],
            source_mailbox="INBOX",
            older_than_days=30,
        )

        args = mock_args(json=False)
        undo_module.cmd_undo_list(args)

        captured = capsys.readouterr()
        assert "older than 30 days" in captured.out


class TestCmdUndoEdgeCases:
    """Tests for cmd_undo edge cases — fences, empty logs, unknown ops."""

    def test_undo_empty_log_dies(self, tmp_path, monkeypatch, mock_args):
        """cmd_undo with empty log dies with message (line 147)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo-empty.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

    def test_undo_fence_without_force_dies(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo on fence entry without --force dies with message (lines 170-176)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_fence_operation("batch-flag")

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "batch-flag" in captured.err
        assert "cannot be undone" in captured.err

    def test_undo_fence_with_force_skips_to_next_entry(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo --force on fence pops it and executes next entry (lines 177-180)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Log an undoable operation, then a fence on top
        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[101],
            dest_mailbox="Archive",
            sender="s@x.com",
        )
        undo_module.log_fence_operation("batch-read")

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "1"
            args = mock_args(json=False, force=True)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "Undid batch-move" in captured.out

    def test_undo_fence_only_with_force_dies(self, tmp_path, monkeypatch, mock_args):
        """cmd_undo --force with only a fence and nothing behind it dies (line 179)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_fence_operation("batch-flag")

        args = mock_args(json=False, force=True)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

    def test_undo_no_message_ids_dies(self, tmp_path, monkeypatch, mock_args):
        """cmd_undo with empty message_ids dies (line 187)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        # Manually write an entry with empty message_ids
        test_log.write_text(json.dumps([{
            "timestamp": datetime.now().isoformat(),
            "operation": "batch-move",
            "account": "iCloud",
            "message_ids": [],
            "dest_mailbox": "Archive",
        }]))

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

    def test_undo_unknown_operation_type_dies(self, tmp_path, monkeypatch, mock_args):
        """cmd_undo with unknown operation type dies (line 305)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        test_log.write_text(json.dumps([{
            "timestamp": datetime.now().isoformat(),
            "operation": "batch-unknown",
            "account": "iCloud",
            "message_ids": [1, 2],
        }]))

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

    def test_undo_batch_move_zero_restored(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo batch-move with 0 messages found shows 'Nothing to restore' (line 234)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[101, 102],
            dest_mailbox="Archive",
            sender="s@x.com",
        )

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "0"
            args = mock_args(json=False, force=False)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "Nothing to restore" in captured.out

    def test_undo_batch_move_no_dest_mailbox_dies(self, tmp_path, monkeypatch, mock_args):
        """cmd_undo batch-move with no dest_mailbox dies (line 197)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        test_log.write_text(json.dumps([{
            "timestamp": datetime.now().isoformat(),
            "operation": "batch-move",
            "account": "iCloud",
            "message_ids": [1],
            "dest_mailbox": None,
        }]))

        args = mock_args(json=False, force=False)
        with pytest.raises(SystemExit):
            undo_module.cmd_undo(args)

    def test_undo_batch_delete_zero_restored(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo batch-delete with 0 found shows 'Nothing to restore' (line 285)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_batch_operation(
            operation_type="batch-delete",
            account="iCloud",
            message_ids=[201],
            source_mailbox="INBOX",
        )

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "0"
            args = mock_args(json=False, force=False)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "Nothing to restore" in captured.out

    def test_undo_batch_delete_no_source_mailbox_restores_to_inbox(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo batch-delete without source_mailbox restores to INBOX with note (lines 289, 300)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        test_log.write_text(json.dumps([{
            "timestamp": datetime.now().isoformat(),
            "operation": "batch-delete",
            "account": "iCloud",
            "message_ids": [301],
            "source_mailbox": None,
        }]))

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "1"
            args = mock_args(json=False, force=False)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "INBOX" in captured.out
        assert "Original mailbox unknown" in captured.out

    def test_undo_restores_log_on_exception(self, tmp_path, monkeypatch, mock_args):
        """cmd_undo restores the operation to the log if an exception occurs (lines 307-310)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        undo_module.log_batch_operation(
            operation_type="batch-move",
            account="iCloud",
            message_ids=[401],
            dest_mailbox="Archive",
            sender="s@x.com",
        )

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.side_effect = RuntimeError("AppleScript error")
            args = mock_args(json=False, force=False)
            with pytest.raises(RuntimeError):
                undo_module.cmd_undo(args)

        # The operation should have been put back
        operations = undo_module._load_undo_log()
        assert len(operations) == 1
        assert operations[0]["message_ids"] == [401]

    def test_undo_force_with_no_fresh_uses_all_ops(self, tmp_path, monkeypatch, mock_args, capsys):
        """cmd_undo --force with only stale entries uses all_ops (line 162)."""
        import mxctl.commands.mail.undo as undo_module

        test_log = tmp_path / "mail-undo.json"
        monkeypatch.setattr(undo_module, "UNDO_LOG_FILE", str(test_log))

        stale_ts = (datetime.now() - timedelta(minutes=60)).isoformat()
        test_log.write_text(json.dumps([{
            "timestamp": stale_ts,
            "operation": "batch-move",
            "account": "iCloud",
            "message_ids": [501],
            "dest_mailbox": "Archive",
            "sender": "old@x.com",
        }]))

        mock_run = patch("mxctl.commands.mail.undo.run")
        with mock_run as mocked:
            mocked.return_value = "1"
            args = mock_args(json=False, force=True)
            undo_module.cmd_undo(args)

        captured = capsys.readouterr()
        assert "Undid batch-move" in captured.out


class TestStatsAllAccountsFix:
    """Regression tests ensuring stats --all (without -a) hits all accounts."""

    @patch("mxctl.commands.mail.analytics.run")
    def test_stats_all_no_explicit_account_uses_all_accounts_script(self, mock_run, mock_args, capsys):
        """stats --all without -a must use the all-accounts AppleScript branch."""
        mock_run.return_value = (
            f"200{FIELD_SEPARATOR}15\n"
            f"iCloud{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}100{FIELD_SEPARATOR}10\n"
            f"Gmail{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}100{FIELD_SEPARATOR}5\n"
        )
        # account=None simulates no -a flag
        args = mock_args(account=None, all=True, json=False, mailbox=None)

        cmd_stats(args)

        # The AppleScript used should iterate every account (all-accounts branch)
        script_used = mock_run.call_args[0][0]
        assert "every account" in script_used
        assert "enabled of acct" in script_used

        captured = capsys.readouterr()
        assert "All Accounts" in captured.out
        assert "[iCloud] INBOX" in captured.out
        assert "[Gmail] INBOX" in captured.out

    @patch("mxctl.commands.mail.analytics.run")
    def test_stats_all_with_explicit_account_uses_single_account_script(self, mock_run, mock_args, capsys):
        """stats --all -a ACCOUNT must use the single-account AppleScript branch."""
        mock_run.return_value = (
            f"100{FIELD_SEPARATOR}10\n"
            f"iCloud{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}100{FIELD_SEPARATOR}10\n"
        )
        args = mock_args(account="iCloud", all=True, json=False, mailbox=None)

        cmd_stats(args)

        script_used = mock_run.call_args[0][0]
        # Single-account script targets one account by name, not every account
        assert 'account "iCloud"' in script_used
        assert "every account" not in script_used

        captured = capsys.readouterr()
        assert "Account: iCloud" in captured.out
