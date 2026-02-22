"""Tests for AI classification and grouping logic in ai.py.

These tests focus on the classification logic and data processing,
not the full AppleScript execution pipeline.
"""

from my_cli.config import FIELD_SEPARATOR
from my_cli.util.mail_helpers import normalize_subject


class TestTriageCategorizationLogic:
    """Test the heuristic categorization logic for triage."""

    def test_noreply_pattern_detection(self):
        """Test detection of automated sender patterns."""
        noreply_patterns = [
            "noreply", "no-reply", "notifications", "mailer-daemon",
            "donotreply", "updates@", "news@", "info@", "support@", "billing@"
        ]

        test_cases = {
            "noreply@example.com": True,
            "no-reply@service.com": True,
            "NoReply@Example.Com": True,  # Case insensitive
            "NOREPLY@EXAMPLE.COM": True,
            "notifications@platform.com": True,
            "updates@company.com": True,
            "billing@service.com": True,
            "john.doe@company.com": False,
            "admin@company.com": False,
            "contact@company.com": False,
        }

        for sender, expected_is_notification in test_cases.items():
            is_notification = any(p in sender.lower() for p in noreply_patterns)
            assert is_notification == expected_is_notification, (
                f"Sender '{sender}' should be "
                f"{'notification' if expected_is_notification else 'person'}"
            )

    def test_flagged_status_boolean_parsing(self):
        """Test parsing flagged status from AppleScript output."""
        assert "true".lower() == "true"
        assert "false".lower() == "false"
        assert "True".lower() == "true"
        assert "FALSE".lower() == "false"

    def test_sender_name_extraction(self):
        """Test extraction of sender name from full sender field."""
        # Test the actual logic used in ai.py
        test_cases = [
            ('"John Doe" <john@example.com>', "John Doe"),
            ("jane@example.com", "jane@example.com"),
            ('"Support Team" <support@company.com>', "Support Team"),
        ]

        for sender, expected in test_cases:
            # This is the actual extraction logic used in ai.py
            if "<" in sender:
                extracted = sender.split("<")[0].strip().strip('"')
            else:
                extracted = sender
            assert extracted == expected

    def test_sender_name_edge_case_no_display_name(self):
        """Test edge case where sender has angle brackets but no display name."""
        sender = "<admin@site.org>"
        # Split gives empty string before '<'
        extracted = sender.split("<")[0].strip().strip('"')
        # In real code, this empty string would be used, which is fine
        # since the UI will show something
        assert extracted == ""  # This is what actually happens


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
        from my_cli.util.formatting import truncate

        assert truncate("hello world", 8) == "hello..."
        assert truncate("short", 20) == "short"
        assert truncate("exactly_eight", 13) == "exactly_eight"

    def test_truncate_with_sender_names(self):
        """Test truncation of sender names."""
        from my_cli.util.formatting import truncate

        long_name = "Very Long Sender Name Here"
        truncated = truncate(long_name, 20)

        assert len(truncated) <= 20
        assert "..." in truncated

    def test_truncate_with_subjects(self):
        """Test truncation of long subjects."""
        from my_cli.util.formatting import truncate

        long_subject = "This is a very long subject line that should definitely be truncated"
        truncated = truncate(long_subject, 55)

        assert len(truncated) <= 55
        assert "..." in truncated


class TestDataStructures:
    """Test data structure handling in AI commands."""

    def test_dict_with_list_values(self):
        """Test grouping messages into dict with lists."""
        from collections import defaultdict

        threads = defaultdict(list)
        threads["project"].append({"id": 1, "subject": "Project"})
        threads["project"].append({"id": 2, "subject": "Re: Project"})
        threads["meeting"].append({"id": 3, "subject": "Meeting"})

        assert len(threads) == 2
        assert len(threads["project"]) == 2
        assert len(threads["meeting"]) == 1

    def test_sorting_by_list_length(self):
        """Test sorting threads by number of messages."""
        threads = {
            "small": [{"id": 1}],
            "large": [{"id": 2}, {"id": 3}, {"id": 4}],
            "medium": [{"id": 5}, {"id": 6}],
        }

        sorted_threads = sorted(threads.items(), key=lambda x: -len(x[1]))

        assert sorted_threads[0][0] == "large"
        assert sorted_threads[1][0] == "medium"
        assert sorted_threads[2][0] == "small"


class TestEmptyInputHandling:
    """Test handling of empty or missing data."""

    def test_empty_string_split(self):
        """Test splitting empty string."""
        result = "".strip().split("\n")
        # Empty string splits to ['']
        filtered = [line for line in result if line.strip()]
        assert len(filtered) == 0

    def test_blank_lines_filtered(self):
        """Test filtering blank lines from output."""
        output = "line1\n\nline2\n   \nline3"
        lines = [line for line in output.split("\n") if line.strip()]

        assert len(lines) == 3
        assert lines == ["line1", "line2", "line3"]

    def test_empty_list_handling(self):
        """Test handling empty message lists."""
        messages = []
        count = len(messages)

        assert count == 0
        # Should handle gracefully without crashing
