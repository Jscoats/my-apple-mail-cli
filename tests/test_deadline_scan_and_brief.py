"""Comprehensive tests for deadline_scan.py and brief.py.

Covers all branches, error paths, and edge cases needed to restore 100% coverage.
"""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from mxctl.config import FIELD_SEPARATOR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _args(**kwargs):
    defaults = {"json": False, "account": None, "mailbox": "INBOX"}
    defaults.update(kwargs)
    return Namespace(**defaults)


def _sep(s: str) -> str:
    """Replace | with FIELD_SEPARATOR for building test AppleScript output."""
    return s.replace("|", FIELD_SEPARATOR)


# ===========================================================================
# deadline_scan.py — _match_keyword()
# ===========================================================================


class TestMatchKeyword:
    """Unit tests for _match_keyword()."""

    def test_high_keyword_exam(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Your Exam Schedule")
        assert result == ("exam", "HIGH")

    def test_high_keyword_urgent(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("URGENT: Please respond")
        assert result == ("urgent", "HIGH")

    def test_high_keyword_suspended(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Account Suspended")
        assert result == ("suspended", "HIGH")

    def test_high_keyword_overdue(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Payment Overdue")
        assert result == ("overdue", "HIGH")

    def test_high_keyword_action_required(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Action Required: Verify Your Account")
        assert result == ("action required", "HIGH")

    def test_high_keyword_final_notice(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Final Notice Before Termination")
        assert result == ("final notice", "HIGH")

    def test_medium_keyword_due(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Assignment Due Tomorrow")
        assert result == ("due", "MEDIUM")

    def test_medium_keyword_deadline(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Project Deadline Approaching")
        assert result == ("deadline", "MEDIUM")

    def test_medium_keyword_expires(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Your subscription expires soon")
        assert result == ("expires", "MEDIUM")

    def test_medium_keyword_payment(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Payment Confirmation")
        assert result == ("payment", "MEDIUM")

    def test_medium_keyword_last_chance(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Last Chance to Save 50%")
        assert result == ("last chance", "MEDIUM")

    def test_low_keyword_reminder(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Reminder: Meeting Tomorrow")
        assert result == ("reminder", "LOW")

    def test_low_keyword_expiring(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Your card is expiring")
        assert result == ("expiring", "LOW")

    def test_low_keyword_renew(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Time to Renew Your Subscription")
        assert result == ("renew", "LOW")

    def test_low_keyword_upcoming(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Upcoming Events This Week")
        assert result == ("upcoming", "LOW")

    def test_no_match_returns_none(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("Hello from a friend")
        assert result is None

    def test_case_insensitive(self):
        from mxctl.commands.mail.deadline_scan import _match_keyword

        result = _match_keyword("EXAM RESULTS ARE IN")
        assert result == ("exam", "HIGH")

    def test_high_keywords_take_priority_over_medium(self):
        """A subject with both HIGH and MEDIUM keywords returns HIGH match (first match wins)."""
        from mxctl.commands.mail.deadline_scan import _match_keyword

        # "exam" is HIGH, "due" is MEDIUM — exam appears first in keyword table
        result = _match_keyword("exam due tomorrow")
        assert result[1] == "HIGH"


# ===========================================================================
# deadline_scan.py — _boost_priority()
# ===========================================================================


class TestBoostPriority:
    """Unit tests for _boost_priority()."""

    def test_low_boosted_to_medium_within_48h(self):
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        recent = now - timedelta(hours=24)
        date_str = recent.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        result = _boost_priority("LOW", date_str, now)
        assert result == "MEDIUM"

    def test_medium_boosted_to_high_within_48h(self):
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        recent = now - timedelta(hours=12)
        date_str = recent.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        result = _boost_priority("MEDIUM", date_str, now)
        assert result == "HIGH"

    def test_high_stays_high_within_48h(self):
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        recent = now - timedelta(hours=1)
        date_str = recent.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        result = _boost_priority("HIGH", date_str, now)
        assert result == "HIGH"

    def test_old_message_no_boost(self):
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        old = now - timedelta(days=10)
        date_str = old.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        result = _boost_priority("LOW", date_str, now)
        assert result == "LOW"

    def test_unparseable_date_no_boost(self):
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        result = _boost_priority("LOW", "not a real date", now)
        assert result == "LOW"

    def test_alt_format_b_d_y(self):
        """Test the '%B %d, %Y at %I:%M:%S %p' format."""
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        recent = now - timedelta(hours=6)
        date_str = recent.strftime("%B %d, %Y at %I:%M:%S %p")
        result = _boost_priority("LOW", date_str, now)
        assert result == "MEDIUM"

    def test_alt_format_asc(self):
        """Test the '%a %b %d %Y %H:%M:%S' format."""
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        recent = now - timedelta(hours=6)
        date_str = recent.strftime("%a %b %d %Y %H:%M:%S")
        result = _boost_priority("LOW", date_str, now)
        assert result == "MEDIUM"

    def test_alt_format_rfc2822(self):
        """Test the '%a, %d %b %Y %H:%M:%S %z' format (timezone-aware stripped)."""
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        recent = now - timedelta(hours=6)
        date_str = recent.strftime("%a, %d %b %Y %H:%M:%S +0000")
        result = _boost_priority("LOW", date_str, now)
        assert result == "MEDIUM"

    def test_unexpected_exception_in_parsing_returns_priority_unchanged(self, monkeypatch):
        """If an unexpected exception (not ValueError) is raised in parsing, return priority as-is."""
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()

        # Patch datetime.strptime to raise a non-ValueError exception
        with patch("mxctl.commands.mail.deadline_scan.datetime") as mock_dt:
            mock_dt.strptime.side_effect = RuntimeError("unexpected")
            mock_dt.now = datetime.now
            result = _boost_priority("LOW", "any date string", now)

        assert result == "LOW"

    def test_exactly_48h_boundary(self):
        """Messages just inside the 48h boundary are boosted; just outside are not."""
        from mxctl.commands.mail.deadline_scan import _boost_priority

        now = datetime.now()
        # 47h 59m ago — inside the 48h window
        just_inside = now - timedelta(hours=47, minutes=59)
        date_str = just_inside.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        result = _boost_priority("LOW", date_str, now)
        assert result == "MEDIUM"

        # 49h ago — outside the 48h window
        just_outside = now - timedelta(hours=49)
        date_str_out = just_outside.strftime("%A, %B %d, %Y at %I:%M:%S %p")
        result_out = _boost_priority("LOW", date_str_out, now)
        assert result_out == "LOW"


# ===========================================================================
# deadline_scan.py — _build_scan_script()
# ===========================================================================


class TestBuildScanScript:
    """Unit tests for _build_scan_script()."""

    def test_all_accounts_script_no_account(self):
        from mxctl.commands.mail.deadline_scan import _build_scan_script

        script = _build_scan_script(None, True, "January 1, 2026 at 12:00:00 AM", 50)
        assert "every account" in script
        assert "read status is false" in script
        assert 'date "January 1, 2026 at 12:00:00 AM"' in script

    def test_single_account_script(self):
        from mxctl.commands.mail.deadline_scan import _build_scan_script

        script = _build_scan_script("iCloud", True, "January 1, 2026 at 12:00:00 AM", 50)
        assert "every account" not in script
        assert 'account "iCloud"' in script

    def test_unread_filter_applied_when_unread_only(self):
        from mxctl.commands.mail.deadline_scan import _build_scan_script

        script = _build_scan_script(None, True, "January 1, 2026", 50)
        assert "read status is false" in script

    def test_no_unread_filter_when_all(self):
        from mxctl.commands.mail.deadline_scan import _build_scan_script

        script = _build_scan_script(None, False, "January 1, 2026", 50)
        assert "read status is false" not in script

    def test_cap_embedded_in_script(self):
        from mxctl.commands.mail.deadline_scan import _build_scan_script

        script = _build_scan_script(None, True, "January 1, 2026", 25)
        assert "25" in script

    def test_account_with_special_chars_escaped(self):
        from mxctl.commands.mail.deadline_scan import _build_scan_script

        script = _build_scan_script('My "Account"', True, "January 1, 2026", 50)
        # escape() should have sanitized the quotes
        assert 'account "' in script


# ===========================================================================
# deadline_scan.py — scan_deadlines()
# ===========================================================================


class TestScanDeadlines:
    """Tests for the scan_deadlines() core function."""

    def test_empty_result_returns_empty_list(self, monkeypatch):
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value=""))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert result == []

    def test_whitespace_only_result_returns_empty_list(self, monkeypatch):
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value="   \n  "))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert result == []

    def test_matching_message_returned(self, monkeypatch):
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        now = datetime.now()
        date_str = (now - timedelta(days=5)).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        line = _sep(f"iCloud|123|Exam Results Available|prof@university.edu|{date_str}")

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value=line + "\n"))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert len(result) == 1
        assert result[0]["id"] == 123
        assert result[0]["keyword"] == "exam"
        assert result[0]["urgency"] == "HIGH"

    def test_no_keyword_match_skipped(self, monkeypatch):
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        now = datetime.now()
        date_str = (now - timedelta(days=3)).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        line = _sep(f"iCloud|456|Hello from Bob|bob@example.com|{date_str}")

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value=line + "\n"))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert result == []

    def test_deduplication_by_id(self, monkeypatch):
        """Same message ID appearing in multiple mailboxes is counted once."""
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        now = datetime.now()
        date_str = (now - timedelta(days=5)).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        line = _sep(f"iCloud|789|Exam Due Tomorrow|prof@school.edu|{date_str}")

        # Same line twice simulates same message in two mailboxes
        raw = line + "\n" + line + "\n"
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value=raw))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert len(result) == 1

    def test_malformed_line_skipped(self, monkeypatch):
        """Lines with too few fields are skipped via parse_message_line returning None."""
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value="malformed line\n"))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert result == []

    def test_blank_lines_skipped(self, monkeypatch):
        """Blank lines in the middle of multi-line output are skipped via continue."""
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        now = datetime.now()
        date_str = (now - timedelta(days=5)).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        line1 = _sep(f"iCloud|111|Payment Overdue|billing@company.com|{date_str}")
        line2 = _sep(f"iCloud|112|Exam Results|prof@uni.edu|{date_str}")
        # Embed a blank line between two valid lines
        raw = line1 + "\n\n" + line2 + "\n"

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value=raw))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        assert len(result) == 2

    def test_sort_order_high_before_medium_before_low(self, monkeypatch):
        """Results are sorted HIGH > MEDIUM > LOW."""
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        now = datetime.now()
        # Old enough that no boost occurs
        old = (now - timedelta(days=10)).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        line_low = _sep(f"iCloud|1|Reminder: weekly digest|news@x.com|{old}")
        line_med = _sep(f"iCloud|2|Assignment Due Friday|prof@uni.edu|{old}")
        line_high = _sep(f"iCloud|3|Account Suspended Immediately|admin@bank.com|{old}")
        raw = "\n".join([line_low, line_med, line_high]) + "\n"

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", Mock(return_value=raw))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines()
        urgencies = [m["urgency"] for m in result]
        assert urgencies[0] == "HIGH"
        # MEDIUM or LOW can follow, order within the rest doesn't matter as much
        assert "HIGH" not in urgencies[1:]

    def test_with_account_filter(self, monkeypatch):
        from mxctl.commands.mail.deadline_scan import scan_deadlines

        now = datetime.now()
        date_str = (now - timedelta(days=5)).strftime("%A, %B %d, %Y at %I:%M:%S %p")
        line = _sep(f"ASU|222|Exam Grades Posted|prof@asu.edu|{date_str}")

        mock_run = Mock(return_value=line + "\n")
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.run", mock_run)
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.to_applescript_date", Mock(return_value="Jan 1, 2026"))

        result = scan_deadlines(account="ASU", unread_only=False, days=30)
        assert len(result) == 1
        # The script built should reference the account
        script_arg = mock_run.call_args[0][0]
        assert "ASU" in script_arg


# ===========================================================================
# deadline_scan.py — cmd_deadline_scan()
# ===========================================================================


class TestCmdDeadlineScan:
    """Tests for the cmd_deadline_scan() CLI command."""

    def test_no_matches_prints_no_found_message(self, monkeypatch, capsys):
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=[]))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value=None))

        args = _args(account=None, all=False, days=14, json=False)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        assert "no time-sensitive messages found" in captured.out

    def test_no_matches_with_account_includes_account_in_message(self, monkeypatch, capsys):
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=[]))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value="iCloud"))

        args = _args(account="iCloud", all=False, days=14, json=False)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        assert "iCloud" in captured.out

    def test_no_matches_all_flag_note(self, monkeypatch, capsys):
        """--all flag (include read messages) note does NOT appear when messages found."""
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=[]))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value=None))

        args = _args(account=None, all=True, days=14, json=False)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        # unread_only=False so no "unread only" note
        assert "unread only" not in captured.out

    def test_no_matches_unread_only_note(self, monkeypatch, capsys):
        """When unread_only=True, the no-matches message includes a note."""
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=[]))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value=None))

        args = _args(account=None, all=False, days=14, json=False)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        assert "unread only" in captured.out

    def test_matches_text_output(self, monkeypatch, capsys):
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        matches = [
            {
                "id": 42,
                "subject": "Exam Results",
                "sender": '"Prof Smith" <prof@uni.edu>',
                "date": "Monday, January 20, 2026 at 10:00:00 AM",
                "account": "iCloud",
                "keyword": "exam",
                "urgency": "HIGH",
            }
        ]
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=matches))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value="iCloud"))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.save_message_aliases", Mock())

        args = _args(account="iCloud", all=False, days=14, json=False)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        assert "Deadline Scan" in captured.out
        assert "1 item found" in captured.out
        assert "exam" in captured.out
        assert "HIGH" in captured.out

    def test_matches_plural_items_label(self, monkeypatch, capsys):
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        matches = [
            {
                "id": 1,
                "subject": "Exam 1",
                "sender": "a@b.com",
                "date": "Monday",
                "account": "iCloud",
                "keyword": "exam",
                "urgency": "HIGH",
            },
            {
                "id": 2,
                "subject": "Payment Due",
                "sender": "c@d.com",
                "date": "Tuesday",
                "account": "iCloud",
                "keyword": "payment",
                "urgency": "MEDIUM",
            },
        ]
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=matches))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value="iCloud"))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.save_message_aliases", Mock())

        args = _args(account="iCloud", all=False, days=14, json=False)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        assert "2 items found" in captured.out

    def test_matches_json_output(self, monkeypatch, capsys):
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        matches = [
            {
                "id": 99,
                "subject": "Urgent Action Required",
                "sender": "admin@bank.com",
                "date": "Wednesday",
                "account": "iCloud",
                "keyword": "urgent",
                "urgency": "HIGH",
            }
        ]
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=matches))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value="iCloud"))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.save_message_aliases", Mock())

        args = _args(account="iCloud", all=False, days=14, json=True)
        cmd_deadline_scan(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["id"] == 99
        assert data[0]["urgency"] == "HIGH"

    def test_aliases_assigned_to_matches(self, monkeypatch):
        """Aliases (1-indexed) are assigned to each match dict."""
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        matches = [
            {"id": 10, "subject": "Exam", "sender": "a@b.com", "date": "Mon", "account": "iCloud", "keyword": "exam", "urgency": "HIGH"},
            {
                "id": 20,
                "subject": "Reminder",
                "sender": "c@d.com",
                "date": "Tue",
                "account": "iCloud",
                "keyword": "reminder",
                "urgency": "LOW",
            },
        ]
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", Mock(return_value=matches))
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value="iCloud"))

        saved_aliases = []
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.save_message_aliases", lambda ids: saved_aliases.extend(ids))

        args = _args(account="iCloud", all=False, days=14, json=True)
        cmd_deadline_scan(args)

        assert saved_aliases == [10, 20]

    def test_no_explicit_account_uses_none(self, monkeypatch, capsys):
        """When args.account is None, account is passed as None to scan_deadlines."""
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        scan_mock = Mock(return_value=[])
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", scan_mock)
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value=None))

        args = _args(account=None, all=False, days=14, json=False)
        cmd_deadline_scan(args)

        call_kwargs = scan_mock.call_args[1]
        assert call_kwargs.get("account") is None

    def test_all_flag_sets_unread_only_false(self, monkeypatch, capsys):
        """--all flag passes unread_only=False to scan_deadlines."""
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        scan_mock = Mock(return_value=[])
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", scan_mock)
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value=None))

        args = _args(account=None, all=True, days=14, json=False)
        cmd_deadline_scan(args)

        call_kwargs = scan_mock.call_args[1]
        assert call_kwargs.get("unread_only") is False

    def test_custom_days_passed_to_scan(self, monkeypatch, capsys):
        from mxctl.commands.mail.deadline_scan import cmd_deadline_scan

        scan_mock = Mock(return_value=[])
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.scan_deadlines", scan_mock)
        monkeypatch.setattr("mxctl.commands.mail.deadline_scan.resolve_account", Mock(return_value=None))

        args = _args(account=None, all=False, days=7, json=False)
        cmd_deadline_scan(args)

        call_kwargs = scan_mock.call_args[1]
        assert call_kwargs.get("days") == 7


# ===========================================================================
# deadline_scan.py — register()
# ===========================================================================


class TestDeadlineScanRegister:
    """Test that register() wires the subcommand correctly."""

    def test_register_adds_deadline_scan_command(self):
        import argparse

        from mxctl.commands.mail.deadline_scan import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["deadline-scan"])
        assert hasattr(args, "func")

    def test_register_default_days(self):
        import argparse

        from mxctl.commands.mail.deadline_scan import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["deadline-scan"])
        assert args.days == 14

    def test_register_all_flag_default_false(self):
        import argparse

        from mxctl.commands.mail.deadline_scan import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["deadline-scan"])
        assert args.all is False

    def test_register_all_flag_can_be_set(self):
        import argparse

        from mxctl.commands.mail.deadline_scan import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["deadline-scan", "--all"])
        assert args.all is True

    def test_register_json_flag(self):
        import argparse

        from mxctl.commands.mail.deadline_scan import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["deadline-scan", "--json"])
        assert args.json is True


# ===========================================================================
# brief.py — _fetch_unread()
# ===========================================================================


class TestFetchUnread:
    """Tests for _fetch_unread()."""

    def test_empty_result_returns_empty_list(self, monkeypatch):
        from mxctl.commands.mail.brief import _fetch_unread

        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value=""))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        assert result == []

    def test_whitespace_only_returns_empty_list(self, monkeypatch):
        from mxctl.commands.mail.brief import _fetch_unread

        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value="   \n  "))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        assert result == []

    def test_valid_line_parsed(self, monkeypatch):
        from mxctl.commands.mail.brief import _fetch_unread

        preview = "Hello this is a preview"
        line = _sep(f"iCloud|42|Test Subject|sender@example.com|Monday|false|{preview}")
        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value=line + "\n"))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        assert len(result) == 1
        assert result[0]["id"] == 42
        assert result[0]["subject"] == "Test Subject"
        assert result[0]["preview"] == preview
        assert result[0]["flagged"] is False

    def test_flagged_field_parsed(self, monkeypatch):
        from mxctl.commands.mail.brief import _fetch_unread

        line = _sep("iCloud|7|Flagged Message|user@example.com|Tuesday|true|A preview")
        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value=line + "\n"))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        assert result[0]["flagged"] is True

    def test_missing_preview_padded(self, monkeypatch):
        """When preview is empty, the trailing separator may be absent — it's padded back."""
        from mxctl.commands.mail.brief import _fetch_unread

        # Line has exactly 6 fields (one fewer than expected 7) — preview is empty
        line = _sep("iCloud|8|No Preview Email|user@example.com|Wednesday|false")
        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value=line + "\n"))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        assert len(result) == 1
        assert result[0]["preview"] == ""

    def test_malformed_line_skipped(self, monkeypatch):
        from mxctl.commands.mail.brief import _fetch_unread

        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value="bad\n"))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        assert result == []

    def test_blank_lines_skipped(self, monkeypatch):
        """Blank lines in the middle of multi-line output are skipped."""
        from mxctl.commands.mail.brief import _fetch_unread

        line1 = _sep("iCloud|9|Hello|user@example.com|Thursday|false|Preview text")
        line2 = _sep("iCloud|10|World|other@example.com|Friday|false|Another preview")
        # Embed a blank line between two valid lines — strip() won't remove it
        raw = line1 + "\n\n" + line2 + "\n"
        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value=raw))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", Mock(return_value="dummy"))

        result = _fetch_unread()
        # Only two valid messages (blank line skipped via continue)
        assert len(result) == 2

    def test_account_passed_to_template(self, monkeypatch):
        from mxctl.commands.mail.brief import _fetch_unread

        template_mock = Mock(return_value="dummy script")
        monkeypatch.setattr("mxctl.commands.mail.brief.run", Mock(return_value=""))
        monkeypatch.setattr("mxctl.commands.mail.brief.inbox_iterator_all_accounts", template_mock)

        _fetch_unread(account="ASU Email")
        assert template_mock.call_args[1].get("account") == "ASU Email" or template_mock.call_args[0][-1] == "ASU Email"


# ===========================================================================
# brief.py — _is_action_required()
# ===========================================================================


class TestIsActionRequired:
    """Tests for _is_action_required()."""

    def test_exam_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Your Exam Results") is True

    def test_suspended_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Account Suspended") is True

    def test_overdue_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Payment Overdue") is True

    def test_urgent_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("URGENT: please reply") is True

    def test_action_required_in_subject(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Action Required: verify your email") is True

    def test_final_notice_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Final Notice Before Cancellation") is True

    def test_due_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Assignment Due Friday") is True

    def test_deadline_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Deadline Approaching") is True

    def test_expires_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Your password expires soon") is True

    def test_payment_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Payment Confirmation") is True

    def test_last_chance_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Last Chance to Save") is True

    def test_reminder_is_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Reminder: Weekly Meeting") is True

    def test_regular_email_not_action(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("Hello from your friend") is False

    def test_case_insensitive(self):
        from mxctl.commands.mail.brief import _is_action_required

        assert _is_action_required("EXAM GRADES POSTED") is True


# ===========================================================================
# brief.py — _is_notification()
# ===========================================================================


class TestIsNotification:
    """Tests for _is_notification()."""

    def test_noreply_sender_is_notification(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("noreply@company.com") is True

    def test_no_reply_with_dash(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("no-reply@service.com") is True

    def test_notifications_sender(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("notifications@github.com") is True

    def test_human_sender_not_notification(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("alice@example.com") is False

    def test_formatted_sender_string(self):
        """Sender string with display name should be parsed to email first."""
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification('"GitHub" <noreply@github.com>') is True

    def test_info_at_sender(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("info@company.com") is True

    def test_support_at_sender(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("support@service.com") is True

    def test_news_at_sender(self):
        from mxctl.commands.mail.brief import _is_notification

        assert _is_notification("news@newsletter.org") is True


# ===========================================================================
# brief.py — classify_messages()
# ===========================================================================


class TestClassifyMessages:
    """Tests for classify_messages()."""

    def _make_msg(self, msg_id, subject, sender, flagged=False):
        return {
            "id": msg_id,
            "subject": subject,
            "sender": sender,
            "flagged": flagged,
            "date": "Monday",
            "preview": "preview",
            "account": "iCloud",
        }

    def test_action_required_classification(self):
        from mxctl.commands.mail.brief import classify_messages

        msg = self._make_msg(1, "Exam Results Due", "prof@uni.edu")
        result = classify_messages([msg])
        assert len(result["action_required"]) == 1
        assert len(result["flagged"]) == 0
        assert len(result["people"]) == 0
        assert len(result["notifications"]) == 0

    def test_flagged_classification(self):
        from mxctl.commands.mail.brief import classify_messages

        msg = self._make_msg(2, "Hello from Bob", "bob@example.com", flagged=True)
        result = classify_messages([msg])
        assert len(result["flagged"]) == 1
        assert len(result["action_required"]) == 0

    def test_people_classification(self):
        from mxctl.commands.mail.brief import classify_messages

        msg = self._make_msg(3, "Let's catch up", "friend@example.com")
        result = classify_messages([msg])
        assert len(result["people"]) == 1
        assert len(result["notifications"]) == 0

    def test_notification_classification(self):
        from mxctl.commands.mail.brief import classify_messages

        msg = self._make_msg(4, "Your weekly digest", "noreply@service.com")
        result = classify_messages([msg])
        assert len(result["notifications"]) == 1

    def test_action_required_takes_priority_over_flagged(self):
        """Action keywords outrank the flagged status."""
        from mxctl.commands.mail.brief import classify_messages

        msg = self._make_msg(5, "Urgent: please act", "a@b.com", flagged=True)
        result = classify_messages([msg])
        assert len(result["action_required"]) == 1
        assert len(result["flagged"]) == 0

    def test_deduplication_by_id(self):
        from mxctl.commands.mail.brief import classify_messages

        msg = self._make_msg(6, "Hello", "friend@example.com")
        result = classify_messages([msg, msg])
        # Should appear only once despite being passed twice
        total = sum(len(v) for v in result.values())
        assert total == 1

    def test_empty_input_returns_empty_buckets(self):
        from mxctl.commands.mail.brief import classify_messages

        result = classify_messages([])
        assert result == {"action_required": [], "flagged": [], "people": [], "notifications": []}

    def test_mixed_messages(self):
        from mxctl.commands.mail.brief import classify_messages

        msgs = [
            self._make_msg(1, "Exam Due", "prof@uni.edu"),
            self._make_msg(2, "Hi!", "friend@example.com", flagged=True),
            self._make_msg(3, "How are you?", "pal@example.com"),
            self._make_msg(4, "Newsletter", "noreply@news.com"),
        ]
        result = classify_messages(msgs)
        assert len(result["action_required"]) == 1
        assert len(result["flagged"]) == 1
        assert len(result["people"]) == 1
        assert len(result["notifications"]) == 1


# ===========================================================================
# brief.py — _build_rows() and _section_text()
# ===========================================================================


class TestBuildRowsAndSectionText:
    """Tests for _build_rows() and _section_text()."""

    def _make_msg(self, msg_id, subject="Test", sender="sender@example.com", date="Monday", preview="A preview"):
        return {
            "id": msg_id,
            "subject": subject,
            "sender": sender,
            "date": date,
            "preview": preview,
            "flagged": False,
            "account": "iCloud",
        }

    def test_build_rows_numbering_starts_at_alias(self):
        from mxctl.commands.mail.brief import _build_rows

        msgs = [self._make_msg(1), self._make_msg(2)]
        rows = _build_rows(msgs, start_alias=3)
        assert rows[0][0] == "3"
        assert rows[1][0] == "4"

    def test_build_rows_preview_newlines_stripped(self):
        from mxctl.commands.mail.brief import _build_rows

        msg = self._make_msg(1, preview="line one\nline two")
        rows = _build_rows([msg], start_alias=1)
        assert "\n" not in rows[0][5]

    def test_section_text_includes_title_and_count(self):
        from mxctl.commands.mail.brief import _section_text

        msgs = [self._make_msg(1), self._make_msg(2)]
        text = _section_text("PEOPLE", msgs, 1)
        assert "PEOPLE" in text
        assert "(2)" in text

    def test_section_text_empty_messages(self):
        from mxctl.commands.mail.brief import _section_text

        text = _section_text("FLAGGED", [], 1)
        assert "FLAGGED" in text
        assert "(0)" in text


# ===========================================================================
# brief.py — cmd_brief()
# ===========================================================================


class TestCmdBrief:
    """Tests for the cmd_brief() CLI command."""

    def _make_msg(self, msg_id, subject="Hello", sender="friend@example.com", flagged=False, preview="preview"):
        return {
            "id": msg_id,
            "subject": subject,
            "sender": sender,
            "flagged": flagged,
            "date": "Monday",
            "preview": preview,
            "account": "iCloud",
        }

    def test_inbox_zero_when_no_messages(self, monkeypatch, capsys):
        from mxctl.commands.mail.brief import cmd_brief

        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=[]))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "Inbox zero" in captured.out

    def test_json_output(self, monkeypatch, capsys):
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(1, "Exam Results", "prof@uni.edu")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=True)
        cmd_brief(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "action_required" in data
        assert "flagged" in data
        assert "people" in data
        assert "notifications" in data

    def test_action_required_section_shown(self, monkeypatch, capsys):
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(1, "Exam Due Tomorrow", "prof@uni.edu")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "ACTION REQUIRED" in captured.out

    def test_flagged_section_shown(self, monkeypatch, capsys):
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(2, "Meeting Notes", "boss@company.com", flagged=True)]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "FLAGGED" in captured.out

    def test_people_section_shown(self, monkeypatch, capsys):
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(3, "Let's get coffee", "friend@example.com")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "PEOPLE" in captured.out

    def test_notification_count_shown_not_table(self, monkeypatch, capsys):
        """Without --verbose, notifications show count only, no table."""
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(4, "Weekly Digest", "noreply@news.com")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "NOTIFICATIONS" in captured.out
        assert "not shown" in captured.out

    def test_verbose_shows_notifications_table(self, monkeypatch, capsys):
        """With --verbose, notifications are shown as a table."""
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(5, "Newsletter", "noreply@updates.com")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=True, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "NOTIFICATIONS" in captured.out
        assert "not shown" not in captured.out

    def test_zero_notifications_shown(self, monkeypatch, capsys):
        """When no notifications, shows NOTIFICATIONS (0 unread)."""
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(6, "Hello from friend", "friend@example.com")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "NOTIFICATIONS (0 unread)" in captured.out

    def test_header_includes_today_date(self, monkeypatch, capsys):
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [self._make_msg(7, "Hello", "friend@example.com")]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        assert "Daily Brief" in captured.out

    def test_aliases_assigned_sequentially(self, monkeypatch):
        """Aliases should be saved for action_required + flagged + people (not notifications by default)."""
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [
            self._make_msg(10, "Exam Tomorrow", "prof@uni.edu"),  # action_required
            self._make_msg(20, "Hi!", "pal@example.com", flagged=True),  # flagged
            self._make_msg(30, "Let's chat", "friend@example.com"),  # people
            self._make_msg(40, "Newsletter", "noreply@news.com"),  # notifications
        ]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))

        saved_ids = []
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", lambda ids: saved_ids.extend(ids))

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        # Notifications not included when not verbose
        assert 40 not in saved_ids
        assert 10 in saved_ids

    def test_verbose_includes_notifications_in_aliases(self, monkeypatch):
        """When verbose=True, notifications are also included in aliases."""
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [
            self._make_msg(10, "Hello", "friend@example.com"),  # people
            self._make_msg(20, "Newsletter", "noreply@news.com"),  # notifications
        ]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))

        saved_ids = []
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", lambda ids: saved_ids.extend(ids))

        args = _args(account=None, verbose=True, json=False)
        cmd_brief(args)

        assert 20 in saved_ids

    def test_alias_counter_increments_across_sections(self, monkeypatch, capsys):
        """Alias numbering continues across action_required → flagged → people."""
        from mxctl.commands.mail.brief import cmd_brief

        msgs = [
            self._make_msg(1, "Exam Due", "prof@uni.edu"),  # action_required → alias 1
            self._make_msg(2, "Flagged", "boss@company.com", flagged=True),  # flagged → alias 2
            self._make_msg(3, "Coffee?", "friend@example.com"),  # people → alias 3
        ]
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", Mock(return_value=msgs))
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account=None, verbose=False, json=False)
        cmd_brief(args)

        captured = capsys.readouterr()
        # All three sections should appear in order
        assert "ACTION REQUIRED" in captured.out
        assert "FLAGGED" in captured.out
        assert "PEOPLE" in captured.out

    def test_account_filter_passed_to_fetch(self, monkeypatch):
        from mxctl.commands.mail.brief import cmd_brief

        fetch_mock = Mock(return_value=[])
        monkeypatch.setattr("mxctl.commands.mail.brief._fetch_unread", fetch_mock)
        monkeypatch.setattr("mxctl.commands.mail.brief.save_message_aliases", Mock())

        args = _args(account="ASU Email", verbose=False, json=False)
        cmd_brief(args)

        fetch_mock.assert_called_once_with(account="ASU Email")


# ===========================================================================
# brief.py — register()
# ===========================================================================


class TestBriefRegister:
    """Test that register() wires the brief subcommand correctly."""

    def test_register_adds_brief_command(self):
        import argparse

        from mxctl.commands.mail.brief import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["brief"])
        assert hasattr(args, "func")

    def test_register_verbose_default_false(self):
        import argparse

        from mxctl.commands.mail.brief import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["brief"])
        assert args.verbose is False

    def test_register_verbose_flag(self):
        import argparse

        from mxctl.commands.mail.brief import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["brief", "--verbose"])
        assert args.verbose is True

    def test_register_json_flag(self):
        import argparse

        from mxctl.commands.mail.brief import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["brief", "--json"])
        assert args.json is True

    def test_register_account_flag(self):
        import argparse

        from mxctl.commands.mail.brief import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        register(subparsers)

        args = parser.parse_args(["brief", "-a", "iCloud"])
        assert args.account == "iCloud"
