"""Tests for mail_helpers module."""

from mxctl.util.mail_helpers import (
    extract_email,
    normalize_subject,
    parse_email_headers,
)


class TestNormalizeSubject:
    """Test subject normalization."""

    def test_re_prefix(self):
        assert normalize_subject("Re: Hello") == "Hello"

    def test_fwd_prefix(self):
        assert normalize_subject("Fwd: Test") == "Test"

    def test_multiple_prefixes(self):
        assert normalize_subject("Re: Re: Fwd: Test") == "Test"

    def test_international_prefixes(self):
        assert normalize_subject("AW: SV: VS: Subject") == "Subject"

    def test_case_insensitive(self):
        assert normalize_subject("re: RE: fwd: Test") == "Test"

    def test_no_prefix(self):
        assert normalize_subject("Plain Subject") == "Plain Subject"

    def test_fw_prefix(self):
        assert normalize_subject("Fw: Forwarded") == "Forwarded"


class TestExtractEmail:
    """Test email extraction."""

    def test_with_display_name(self):
        assert extract_email('"John Doe" <john@example.com>') == "john@example.com"

    def test_bare_email(self):
        assert extract_email("john@example.com") == "john@example.com"

    def test_angle_brackets_only(self):
        assert extract_email("<admin@site.org>") == "admin@site.org"

    def test_no_email_returns_original(self):
        assert extract_email("Invalid") == "Invalid"


class TestParseEmailHeaders:
    """Test email header parsing."""

    def test_simple_headers(self):
        raw = "From: sender@example.com\nTo: recipient@example.com"
        headers = parse_email_headers(raw)
        assert headers == {
            "From": "sender@example.com",
            "To": "recipient@example.com",
        }

    def test_multiline_headers(self):
        raw = "Subject: This is a long subject\n that continues here"
        headers = parse_email_headers(raw)
        assert headers == {"Subject": "This is a long subject that continues here"}

    def test_duplicate_keys(self):
        raw = "Received: server1\nReceived: server2"
        headers = parse_email_headers(raw)
        assert headers == {"Received": ["server1", "server2"]}

    def test_duplicate_keys_multiline(self):
        raw = "Received: server1\n continuation1\nReceived: server2\n continuation2"
        headers = parse_email_headers(raw)
        assert headers == {"Received": ["server1 continuation1", "server2 continuation2"]}

    def test_tab_continuation(self):
        raw = "Subject: First line\n\tSecond line"
        headers = parse_email_headers(raw)
        assert headers == {"Subject": "First line Second line"}
