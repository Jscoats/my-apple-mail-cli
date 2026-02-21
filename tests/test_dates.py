"""Tests for dates module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from my_cli.util.dates import (
    days_ago,
    parse_applescript_date,
    parse_date,
    to_applescript_date,
    today,
)


class TestParseDate:
    """Test date parsing."""

    def test_valid_date(self):
        result = parse_date("2026-02-14")
        assert result == datetime(2026, 2, 14)

    def test_invalid_date_dies(self):
        with pytest.raises(SystemExit):
            parse_date("not-a-date")


class TestToApplescriptDate:
    """Test datetime to AppleScript date conversion."""

    def test_conversion(self):
        dt = datetime(2026, 2, 14)
        assert to_applescript_date(dt) == "February 14, 2026"

    def test_single_digit_day(self):
        dt = datetime(2026, 1, 5)
        assert to_applescript_date(dt) == "January 05, 2026"


class TestDaysAgo:
    """Test days_ago helper."""

    @patch("my_cli.util.dates.datetime")
    def test_days_ago(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 2, 14)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = days_ago(7)
        assert result == "2026-02-07"

    @patch("my_cli.util.dates.datetime")
    def test_zero_days_ago(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 2, 14)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = days_ago(0)
        assert result == "2026-02-14"


class TestToday:
    """Test today helper."""

    @patch("my_cli.util.dates.datetime")
    def test_today(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 2, 14)
        result = today()
        assert result == "2026-02-14"


class TestParseApplescriptDate:
    """Test AppleScript date to ISO 8601 conversion."""

    def test_with_weekday(self):
        result = parse_applescript_date("Tuesday, January 14, 2026 at 2:30:00 PM")
        assert result == "2026-01-14T14:30:00"

    def test_without_weekday(self):
        result = parse_applescript_date("January 14, 2026 at 2:30:00 PM")
        assert result == "2026-01-14T14:30:00"

    def test_morning_time(self):
        result = parse_applescript_date("January 14, 2026 at 9:15:30 AM")
        assert result == "2026-01-14T09:15:30"

    def test_midnight(self):
        result = parse_applescript_date("January 14, 2026 at 12:00:00 AM")
        assert result == "2026-01-14T00:00:00"

    def test_noon(self):
        result = parse_applescript_date("January 14, 2026 at 12:00:00 PM")
        assert result == "2026-01-14T12:00:00"

    def test_invalid_returns_original(self):
        result = parse_applescript_date("invalid date string")
        assert result == "invalid date string"
