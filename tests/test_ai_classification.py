"""Tests for AI classification and grouping logic in ai.py.

These tests focus on the classification logic and data processing,
not the full AppleScript execution pipeline.
"""

import argparse
import json
from unittest.mock import Mock

import pytest

from mxctl.config import FIELD_SEPARATOR, NOREPLY_PATTERNS
from mxctl.util.mail_helpers import extract_email, normalize_subject


class TestTriageCategorizationLogic:
    """Test the heuristic categorization logic for triage, using real app code."""

    def test_extract_email_from_display_name_format(self):
        """extract_email pulls the address from 'Name <addr>' format."""
        result = extract_email('"John Doe" <john@example.com>')
        assert result == "john@example.com"

    def test_extract_email_bare_address(self):
        """extract_email returns a bare address unchanged."""
        result = extract_email("jane@example.com")
        assert result == "jane@example.com"

    def test_extract_email_angle_brackets_only(self):
        """extract_email handles '<addr>' with no display name."""
        result = extract_email("<admin@site.org>")
        assert result == "admin@site.org"

    def test_noreply_patterns_match_automated_senders(self):
        """NOREPLY_PATTERNS from config.py correctly identify automated senders."""
        automated_emails = [
            "noreply@example.com",
            "no-reply@service.com",
            "notifications@platform.com",
            "updates@company.com",
            "billing@service.com",
        ]
        for email in automated_emails:
            matched = any(p in email.lower() for p in NOREPLY_PATTERNS)
            assert matched, f"Expected '{email}' to match NOREPLY_PATTERNS but it did not"

    def test_noreply_patterns_do_not_match_personal_senders(self):
        """NOREPLY_PATTERNS should not flag real personal email addresses."""
        personal_emails = [
            "john.doe@company.com",
            "admin@company.com",
            "contact@company.com",
        ]
        for email in personal_emails:
            matched = any(p in email.lower() for p in NOREPLY_PATTERNS)
            assert not matched, f"Expected '{email}' NOT to match NOREPLY_PATTERNS but it did"

    def test_cmd_triage_categorizes_noreply_sender_as_notification(self, monkeypatch, capsys):
        """cmd_triage places a noreply@ sender into NOTIFICATIONS, not PEOPLE."""
        from mxctl.commands.mail.ai import cmd_triage

        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}10{FIELD_SEPARATOR}Your Receipt{FIELD_SEPARATOR}"
                f"noreply@shop.com{FIELD_SEPARATOR}2026-01-01{FIELD_SEPARATOR}false\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_triage(args)

        out = capsys.readouterr().out
        assert "NOTIFICATIONS (1):" in out
        assert "PEOPLE" not in out

    def test_cmd_triage_categorizes_display_name_noreply_as_notification(self, monkeypatch, capsys):
        """cmd_triage uses the extracted email address, not the display name, for classification."""
        from mxctl.commands.mail.ai import cmd_triage

        # Sender has a friendly display name but a no-reply address
        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}11{FIELD_SEPARATOR}Weekly Digest{FIELD_SEPARATOR}"
                f'"Shop Alerts" <notifications@shop.com>{FIELD_SEPARATOR}2026-01-05{FIELD_SEPARATOR}false\n'
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_triage(args)

        out = capsys.readouterr().out
        assert "NOTIFICATIONS (1):" in out
        assert "PEOPLE" not in out


class TestNormalizeSubject:
    """Test subject normalization for thread grouping."""

    def test_removes_re_prefix(self):
        """Should remove Re: prefix."""
        assert normalize_subject("Re: Original Subject") == "Original Subject"

    def test_removes_fwd_prefix(self):
        """Should remove Fwd: prefix."""
        assert normalize_subject("Fwd: Original Subject") == "Original Subject"

    def test_removes_multiple_prefixes(self):
        """Should remove multiple nested prefixes."""
        assert normalize_subject("Re: Re: Fwd: Subject") == "Subject"

    def test_case_insensitive_prefix_removal(self):
        """Should handle case variations of prefixes."""
        assert normalize_subject("re: RE: fwd: Subject") == "Subject"
        assert normalize_subject("RE: FWD: SUBJECT") == "SUBJECT"

    def test_international_prefixes(self):
        """Should remove international reply prefixes."""
        assert normalize_subject("AW: Subject") == "Subject"  # German
        assert normalize_subject("SV: Subject") == "Subject"  # Swedish/Norwegian
        assert normalize_subject("VS: Subject") == "Subject"  # Finnish

    def test_no_prefix_unchanged(self):
        """Should leave subjects without prefixes unchanged."""
        assert normalize_subject("Plain Subject") == "Plain Subject"

    def test_fw_prefix(self):
        """Should handle Fw: as alternative to Fwd:."""
        assert normalize_subject("Fw: Forwarded Message") == "Forwarded Message"


class TestThreadGrouping:
    """Test conversation grouping logic."""

    def test_case_insensitive_grouping(self):
        """Thread grouping should be case-insensitive."""
        subjects = [
            "Project Update",
            "project update",
            "PROJECT UPDATE",
            "Re: Project Update",
        ]

        # Normalize all subjects
        normalized = [normalize_subject(s).lower() for s in subjects]

        # All should normalize to the same value
        assert len(set(normalized)) == 1
        assert normalized[0] == "project update"

    def test_groups_replies_together(self):
        """Should group Re: and Fwd: with original."""
        subjects = [
            "Meeting Agenda",
            "Re: Meeting Agenda",
            "Fwd: Meeting Agenda",
            "Re: Re: Meeting Agenda",
        ]

        normalized = [normalize_subject(s) for s in subjects]

        # All should normalize to "Meeting Agenda"
        assert all(n == "Meeting Agenda" for n in normalized)


class TestMessageFieldParsing:
    """Test parsing of message data from AppleScript output."""

    def test_field_separator_split(self):
        """Test splitting by field separator."""
        line = f"account{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Subject{FIELD_SEPARATOR}sender@example.com{FIELD_SEPARATOR}2026-01-01"
        parts = line.split(FIELD_SEPARATOR)

        assert len(parts) == 5
        assert parts[0] == "account"
        assert parts[1] == "123"
        assert parts[2] == "Subject"
        assert parts[3] == "sender@example.com"
        assert parts[4] == "2026-01-01"

    def test_insufficient_fields_detection(self):
        """Should detect when message has too few fields."""
        # Only 3 fields when expecting 5+
        line = f"account{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Subject"
        parts = line.split(FIELD_SEPARATOR)

        assert len(parts) < 5

    def test_message_id_integer_conversion(self):
        """Test converting message ID to int."""
        id_str = "12345"
        message_id = int(id_str) if id_str.isdigit() else id_str

        assert isinstance(message_id, int)
        assert message_id == 12345

    def test_message_id_non_numeric_handling(self):
        """Test handling non-numeric message IDs."""
        id_str = "abc123"
        message_id = int(id_str) if id_str.isdigit() else id_str

        assert isinstance(message_id, str)
        assert message_id == "abc123"


class TestStringTruncation:
    """Test truncation logic for display."""

    def test_truncate_logic(self):
        """Test basic truncation behavior."""
        from mxctl.util.formatting import truncate

        assert truncate("hello world", 8) == "hello..."
        assert truncate("short", 20) == "short"
        assert truncate("exactly_eight", 13) == "exactly_eight"

    def test_truncate_with_sender_names(self):
        """Test truncation of sender names."""
        from mxctl.util.formatting import truncate

        long_name = "Very Long Sender Name Here"
        truncated = truncate(long_name, 20)

        assert len(truncated) <= 20
        assert "..." in truncated

    def test_truncate_with_subjects(self):
        """Test truncation of long subjects."""
        from mxctl.util.formatting import truncate

        long_subject = "This is a very long subject line that should definitely be truncated"
        truncated = truncate(long_subject, 55)

        assert len(truncated) <= 55
        assert "..." in truncated


class TestCmdSummary:
    """Edge-case tests for cmd_summary that differ from the basic smoke tests in test_commands.py."""

    def test_summary_sender_display_name_extracted(self, monkeypatch, capsys):
        """cmd_summary strips angle-bracket email addresses, showing only the display name."""
        from mxctl.commands.mail.ai import cmd_summary

        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}200{FIELD_SEPARATOR}Hello{FIELD_SEPARATOR}"
                f'"Alice Smith" <alice@example.com>{FIELD_SEPARATOR}2026-02-01\n'
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=20, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_summary(args)

        out = capsys.readouterr().out
        # Display name should appear, raw angle-bracket form should not
        assert "Alice Smith" in out
        assert "<alice@example.com>" not in out

    def test_summary_skips_malformed_lines(self, monkeypatch, capsys):
        """cmd_summary silently skips lines that have fewer than 5 fields."""
        from mxctl.commands.mail.ai import cmd_summary

        # One valid line, one malformed (only 2 fields)
        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}99{FIELD_SEPARATOR}Good Subject{FIELD_SEPARATOR}a@b.com{FIELD_SEPARATOR}2026-01-10\n"
                f"bad-line-no-separators\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=20, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_summary(args)

        out = capsys.readouterr().out
        # Only the valid message should be counted
        assert "1 unread:" in out
        assert "[1]" in out

    def test_summary_json_contains_all_fields(self, monkeypatch, capsys):
        """cmd_summary JSON output includes account, id, subject, sender, and date fields."""
        from mxctl.commands.mail.ai import cmd_summary

        mock_run = Mock(
            return_value=(
                f"Work{FIELD_SEPARATOR}555{FIELD_SEPARATOR}Quarterly Report{FIELD_SEPARATOR}boss@work.com{FIELD_SEPARATOR}2026-03-15\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=20, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=True)
        cmd_summary(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 1
        msg = data[0]
        assert msg["account"] == "Work"
        assert msg["id"] == 555
        assert msg["subject"] == "Quarterly Report"
        assert msg["sender"] == "boss@work.com"
        assert msg["date"] == "2026-03-15"


class TestCmdTriage:
    """Edge-case tests for cmd_triage that differ from the basic smoke tests in test_commands.py."""

    def test_triage_all_flagged_shows_no_people_or_notifications(self, monkeypatch, capsys):
        """When every message is flagged, PEOPLE and NOTIFICATIONS sections are absent."""
        from mxctl.commands.mail.ai import cmd_triage

        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}1{FIELD_SEPARATOR}Urgent A{FIELD_SEPARATOR}a@a.com{FIELD_SEPARATOR}2026-01-01{FIELD_SEPARATOR}true\n"
                f"iCloud{FIELD_SEPARATOR}2{FIELD_SEPARATOR}Urgent B{FIELD_SEPARATOR}b@b.com{FIELD_SEPARATOR}2026-01-02{FIELD_SEPARATOR}true\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_triage(args)

        out = capsys.readouterr().out
        assert "FLAGGED (2):" in out
        assert "PEOPLE" not in out
        assert "NOTIFICATIONS" not in out

    def test_triage_skips_lines_with_fewer_than_six_fields(self, monkeypatch, capsys):
        """cmd_triage ignores lines that are missing the flagged field (< 6 fields)."""
        from mxctl.commands.mail.ai import cmd_triage

        # One valid line (6 fields) and one truncated line (5 fields — no flagged status)
        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}10{FIELD_SEPARATOR}Valid{FIELD_SEPARATOR}p@p.com{FIELD_SEPARATOR}2026-01-01{FIELD_SEPARATOR}false\n"
                f"iCloud{FIELD_SEPARATOR}11{FIELD_SEPARATOR}Truncated{FIELD_SEPARATOR}q@q.com{FIELD_SEPARATOR}2026-01-02\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_triage(args)

        out = capsys.readouterr().out
        # Only the 1 valid message should be counted
        assert "Triage (1 unread):" in out

    def test_triage_json_structure_has_correct_keys(self, monkeypatch, capsys):
        """cmd_triage JSON output is an object with exactly flagged, people, and notifications keys."""
        from mxctl.commands.mail.ai import cmd_triage

        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}5{FIELD_SEPARATOR}Note{FIELD_SEPARATOR}friend@ex.com{FIELD_SEPARATOR}2026-01-01{FIELD_SEPARATOR}false\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=True)
        cmd_triage(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert set(data.keys()) == {"flagged", "people", "notifications"}
        assert isinstance(data["flagged"], list)
        assert isinstance(data["people"], list)
        assert isinstance(data["notifications"], list)

    def test_triage_json_message_has_flagged_field(self, monkeypatch, capsys):
        """Each message dict in triage JSON output includes a boolean 'flagged' field."""
        from mxctl.commands.mail.ai import cmd_triage

        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}7{FIELD_SEPARATOR}Important{FIELD_SEPARATOR}boss@co.com{FIELD_SEPARATOR}2026-02-10{FIELD_SEPARATOR}true\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=True)
        cmd_triage(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data["flagged"]) == 1
        msg = data["flagged"][0]
        assert msg["flagged"] is True
        assert msg["id"] == 7
        assert msg["subject"] == "Important"


# ===========================================================================
# cmd_summary — empty inbox path (line 38 — blank line skip in summary)
# ===========================================================================


class TestCmdSummaryBlankLineSkip:
    """Test that cmd_summary skips blank lines in output (line 38)."""

    def test_summary_blank_line_in_output(self, monkeypatch, capsys):
        """cmd_summary skips blank lines between valid messages."""
        from mxctl.commands.mail.ai import cmd_summary

        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}100{FIELD_SEPARATOR}First{FIELD_SEPARATOR}a@b.com{FIELD_SEPARATOR}2026-01-01\n"
                f"\n"
                f"   \n"
                f"iCloud{FIELD_SEPARATOR}101{FIELD_SEPARATOR}Second{FIELD_SEPARATOR}c@d.com{FIELD_SEPARATOR}2026-01-02\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=20, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_summary(args)

        out = capsys.readouterr().out
        assert "2 unread:" in out
        assert "[1]" in out
        assert "[2]" in out


# ===========================================================================
# cmd_triage — empty inbox and account filter (lines 67-68, 77)
# ===========================================================================


class TestCmdTriageEdgeCases:
    """Additional coverage for cmd_triage edge cases."""

    def test_triage_empty_inbox(self, monkeypatch, capsys):
        """cmd_triage with empty result shows inbox zero message (lines 67-68)."""
        from mxctl.commands.mail.ai import cmd_triage

        mock_run = Mock(return_value="")
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_triage(args)

        out = capsys.readouterr().out
        assert "Inbox zero" in out or "No unread" in out

    def test_triage_blank_line_skip(self, monkeypatch, capsys):
        """cmd_triage skips blank lines in output (line 77)."""
        from mxctl.commands.mail.ai import cmd_triage

        # Put blank lines BETWEEN two valid lines so strip() doesn't remove them
        mock_run = Mock(
            return_value=(
                f"iCloud{FIELD_SEPARATOR}10{FIELD_SEPARATOR}Valid A{FIELD_SEPARATOR}p@p.com{FIELD_SEPARATOR}2026-01-01{FIELD_SEPARATOR}false\n"
                f"\n"
                f"  \n"
                f"iCloud{FIELD_SEPARATOR}11{FIELD_SEPARATOR}Valid B{FIELD_SEPARATOR}q@q.com{FIELD_SEPARATOR}2026-01-02{FIELD_SEPARATOR}false\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)
        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            lambda inner_ops, cap=30, account=None: 'tell application "Mail"\nend tell',
        )

        args = argparse.Namespace(account=None, json=False)
        cmd_triage(args)

        out = capsys.readouterr().out
        assert "Triage (2 unread):" in out

    def test_triage_with_account_filter(self, monkeypatch, capsys):
        """cmd_triage with -a flag passes account to inbox_iterator_all_accounts."""
        from mxctl.commands.mail.ai import cmd_triage

        mock_run = Mock(
            return_value=(
                f"Work{FIELD_SEPARATOR}20{FIELD_SEPARATOR}Task{FIELD_SEPARATOR}boss@work.com{FIELD_SEPARATOR}2026-01-01{FIELD_SEPARATOR}false\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        captured_account = []

        def mock_template(inner_ops, cap=30, account=None):
            captured_account.append(account)
            return 'tell application "Mail"\nend tell'

        monkeypatch.setattr(
            "mxctl.commands.mail.ai.inbox_iterator_all_accounts",
            mock_template,
        )

        args = argparse.Namespace(account="Work", json=False)
        cmd_triage(args)

        assert captured_account[0] == "Work"


# ===========================================================================
# cmd_context — edge cases (lines 127, 158, 168-169)
# ===========================================================================


class TestCmdContextEdgeCases:
    """Coverage for cmd_context missing lines."""

    def test_context_no_account_dies(self, monkeypatch):
        """cmd_context without account dies (line 127)."""
        from mxctl.commands.mail.ai import cmd_context

        monkeypatch.setattr("mxctl.commands.mail.ai.resolve_account", lambda _: None)

        args = argparse.Namespace(account=None, mailbox=None, id=100, limit=50, all_accounts=False, json=False)
        with pytest.raises(SystemExit):
            cmd_context(args)

    def test_context_insufficient_parts_dies(self, monkeypatch):
        """cmd_context with bad initial message fetch dies (line 158)."""
        from mxctl.commands.mail.ai import cmd_context

        mock_run = Mock(return_value="only-partial-data")
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(account="iCloud", mailbox="INBOX", id=100, limit=50, all_accounts=False, json=False)
        with pytest.raises(SystemExit):
            cmd_context(args)

    def test_context_all_accounts_flag(self, monkeypatch, capsys):
        """cmd_context --all-accounts uses 'every account' loop (lines 168-169)."""
        from mxctl.commands.mail.ai import cmd_context

        # First call returns main message; second call returns thread
        mock_run = Mock(
            side_effect=[
                f"Subject{FIELD_SEPARATOR}sender@x.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}to@x.com{FIELD_SEPARATOR}Message body",
                "",  # No thread messages
            ]
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(account="iCloud", mailbox="INBOX", id=100, limit=50, all_accounts=True, json=False)
        cmd_context(args)

        # Second script should use "every account"
        second_script = mock_run.call_args_list[1][0][0]
        assert "every account" in second_script

    def test_context_with_thread_entries(self, monkeypatch, capsys):
        """cmd_context shows thread history when present."""
        from mxctl.commands.mail.ai import cmd_context
        from mxctl.config import RECORD_SEPARATOR

        mock_run = Mock(
            side_effect=[
                f"Meeting Notes{FIELD_SEPARATOR}alice@x.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}bob@x.com{FIELD_SEPARATOR}Main body",
                (
                    f"200{FIELD_SEPARATOR}Re: Meeting Notes{FIELD_SEPARATOR}bob@x.com{FIELD_SEPARATOR}Tue{FIELD_SEPARATOR}Reply body"
                    + RECORD_SEPARATOR
                ),
            ]
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(account="iCloud", mailbox="INBOX", id=100, limit=50, all_accounts=False, json=False)
        cmd_context(args)

        captured = capsys.readouterr()
        assert "Thread History" in captured.out
        assert "Reply body" in captured.out

    def test_context_json_output(self, monkeypatch, capsys):
        """cmd_context --json returns structured data."""
        from mxctl.commands.mail.ai import cmd_context

        mock_run = Mock(
            side_effect=[
                f"Subject{FIELD_SEPARATOR}s@x.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}t@x.com{FIELD_SEPARATOR}Body here",
                "",
            ]
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(account="iCloud", mailbox="INBOX", id=100, limit=50, all_accounts=False, json=True)
        cmd_context(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "message" in data
        assert "thread" in data
        assert data["message"]["subject"] == "Subject"


# ===========================================================================
# cmd_find_related — edge cases (lines 247-266, 301, 304, 324)
# ===========================================================================


class TestCmdFindRelatedEdgeCases:
    """Coverage for cmd_find_related missing lines."""

    def test_find_related_by_message_id(self, monkeypatch, capsys):
        """cmd_find_related with numeric query looks up message first (lines 247-266)."""
        from mxctl.commands.mail.ai import cmd_find_related

        # First call: lookup message by ID; second call: search
        mock_run = Mock(
            side_effect=[
                f"Re: Project Update{FIELD_SEPARATOR}alice@x.com",  # lookup returns subject + sender
                (
                    f"50{FIELD_SEPARATOR}Project Update{FIELD_SEPARATOR}alice@x.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
                    f"51{FIELD_SEPARATOR}Re: Project Update{FIELD_SEPARATOR}bob@x.com{FIELD_SEPARATOR}Tue{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
                ),
            ]
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(query="12345", json=False)
        cmd_find_related(args)

        captured = capsys.readouterr()
        assert "conversations" in captured.out.lower()

    def test_find_related_by_message_id_not_found(self, monkeypatch, capsys):
        """cmd_find_related with numeric query where message is not found (lines 262-264)."""
        from mxctl.commands.mail.ai import cmd_find_related

        mock_run = Mock(return_value="")
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(query="99999", json=False)
        cmd_find_related(args)

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_find_related_no_results(self, monkeypatch, capsys):
        """cmd_find_related with no search results shows message."""
        from mxctl.commands.mail.ai import cmd_find_related

        mock_run = Mock(return_value="")
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(query="nonexistent topic", json=False)
        cmd_find_related(args)

        captured = capsys.readouterr()
        assert "No messages found" in captured.out

    def test_find_related_blank_line_skip(self, monkeypatch, capsys):
        """cmd_find_related skips blank lines (line 301)."""
        from mxctl.commands.mail.ai import cmd_find_related

        # Put blank lines BETWEEN two valid lines
        mock_run = Mock(
            return_value=(
                f"60{FIELD_SEPARATOR}Topic{FIELD_SEPARATOR}a@b.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
                f"\n"
                f"  \n"
                f"61{FIELD_SEPARATOR}Topic{FIELD_SEPARATOR}c@d.com{FIELD_SEPARATOR}Tue{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(query="Topic", json=False)
        cmd_find_related(args)

        captured = capsys.readouterr()
        assert "1 conversations" in captured.out

    def test_find_related_malformed_line_skip(self, monkeypatch, capsys):
        """cmd_find_related skips malformed lines (line 304)."""
        from mxctl.commands.mail.ai import cmd_find_related

        mock_run = Mock(
            return_value=(
                f"70{FIELD_SEPARATOR}Good{FIELD_SEPARATOR}a@b.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
                f"bad-line-no-separators\n"
            )
        )
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(query="Good", json=False)
        cmd_find_related(args)

        captured = capsys.readouterr()
        assert "1 conversations" in captured.out

    def test_find_related_more_than_5_in_thread(self, monkeypatch, capsys):
        """cmd_find_related shows '... and N more' for threads >5 messages (line 324)."""
        from mxctl.commands.mail.ai import cmd_find_related

        lines = ""
        for i in range(8):
            lines += (
                f"{i}{FIELD_SEPARATOR}Same Topic{FIELD_SEPARATOR}s{i}@x.com{FIELD_SEPARATOR}"
                f"Day {i}{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
            )
        mock_run = Mock(return_value=lines)
        monkeypatch.setattr("mxctl.commands.mail.ai.run", mock_run)

        args = argparse.Namespace(query="Same Topic", json=False)
        cmd_find_related(args)

        captured = capsys.readouterr()
        assert "and 3 more" in captured.out
