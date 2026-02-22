"""New test coverage for previously-untested modules.

Covers:
- actions.py unsubscribe paths (one-click POST, browser fallback, dry-run, private IP)
- todoist_integration.py HTTP call (success, error, with/without --project flag)
- inbox_tools.py smoke tests (process-inbox, clean-newsletters, weekly-review)
- composite.py _export_bulk (RECORD_SEPARATOR parsing)
"""

import json
import os
import socket
from argparse import Namespace
from io import BytesIO
from unittest.mock import Mock, MagicMock, patch

import pytest

from my_cli.config import FIELD_SEPARATOR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**kwargs):
    defaults = {
        "json": False,
        "account": "iCloud",
        "mailbox": "INBOX",
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


# ===========================================================================
# actions.py — unsubscribe
# ===========================================================================

class TestUnsubscribePrivateIpValidation:
    """Test _is_private_url() rejects private/loopback addresses."""

    def test_private_ip_10_x(self):
        from my_cli.commands.mail.actions import _is_private_url
        with patch("socket.gethostbyname", return_value="10.0.0.1"):
            assert _is_private_url("http://internal.corp/unsub") is True

    def test_private_ip_172_16(self):
        from my_cli.commands.mail.actions import _is_private_url
        with patch("socket.gethostbyname", return_value="172.20.0.1"):
            assert _is_private_url("http://internal.corp/unsub") is True

    def test_private_ip_192_168(self):
        from my_cli.commands.mail.actions import _is_private_url
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            assert _is_private_url("http://router.local/unsub") is True

    def test_loopback_127(self):
        from my_cli.commands.mail.actions import _is_private_url
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            assert _is_private_url("http://localhost/unsub") is True

    def test_public_ip_allowed(self):
        from my_cli.commands.mail.actions import _is_private_url
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            assert _is_private_url("https://example.com/unsub") is False

    def test_dns_failure_blocks(self):
        from my_cli.commands.mail.actions import _is_private_url
        with patch("socket.gethostbyname", side_effect=socket.gaierror("NXDOMAIN")):
            assert _is_private_url("https://nonexistent.invalid/unsub") is True

    def test_missing_hostname_blocks(self):
        from my_cli.commands.mail.actions import _is_private_url
        # URL with no hostname
        assert _is_private_url("file:///etc/hosts") is True


class TestUnsubscribeDryRun:
    """Test unsubscribe --dry-run: shows info without making HTTP requests."""

    @patch("my_cli.commands.mail.actions.run")
    def test_dry_run_shows_links(self, mock_run, capsys):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        header_value = "<https://example.com/unsub>"
        mock_run.return_value = (
            f"Weekly Newsletter"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: {header_value}\n"
        )

        args = _make_args(id=42, dry_run=True, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert "Unsubscribe info" in out
        assert "https://example.com/unsub" in out

    @patch("my_cli.commands.mail.actions.run")
    def test_dry_run_json(self, mock_run, capsys):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        header_value = "<https://example.com/unsub>, <mailto:unsub@example.com>"
        mock_run.return_value = (
            f"My Newsletter"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: {header_value}\n"
        )

        args = _make_args(id=42, dry_run=True, open=False, json=True)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "https_urls" in data
        assert "mailto_urls" in data
        assert data["https_urls"] == ["https://example.com/unsub"]
        assert data["mailto_urls"] == ["mailto:unsub@example.com"]

    @patch("my_cli.commands.mail.actions.run")
    def test_no_unsubscribe_header(self, mock_run, capsys):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        mock_run.return_value = (
            f"Regular Email"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"From: sender@example.com\n"
        )

        args = _make_args(id=42, dry_run=True, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert "No unsubscribe option found" in out


class TestUnsubscribeOneClick:
    """Test the RFC 8058 one-click POST path."""

    @patch("my_cli.commands.mail.actions.run")
    @patch("my_cli.commands.mail.actions._is_private_url", return_value=False)
    @patch("my_cli.commands.mail.actions.urllib.request.urlopen")
    def test_one_click_success(self, mock_urlopen, mock_private, mock_run, capsys):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        # One-click requires List-Unsubscribe-Post header
        mock_run.return_value = (
            f"Promo Newsletter"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: <https://example.com/unsub>\n"
            f"List-Unsubscribe-Post: List-Unsubscribe=One-Click\n"
        )

        # Simulate a successful HTTP 200 response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        args = _make_args(id=42, dry_run=False, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert "one-click" in out
        assert "HTTP 200" in out
        # Confirm a POST was attempted
        assert mock_urlopen.called

    @patch("my_cli.commands.mail.actions.run")
    @patch("my_cli.commands.mail.actions._is_private_url", return_value=True)
    def test_one_click_private_url_dies(self, mock_private, mock_run):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        mock_run.return_value = (
            f"Promo Newsletter"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: <https://192.168.1.1/unsub>\n"
            f"List-Unsubscribe-Post: List-Unsubscribe=One-Click\n"
        )

        args = _make_args(id=42, dry_run=False, open=False)
        with pytest.raises(SystemExit) as exc_info:
            cmd_unsubscribe(args)
        assert exc_info.value.code == 1

    @patch("my_cli.commands.mail.actions.run")
    @patch("my_cli.commands.mail.actions._is_private_url", return_value=False)
    @patch("my_cli.commands.mail.actions.urllib.request.urlopen")
    @patch("my_cli.commands.mail.actions.subprocess.run")
    def test_one_click_fallback_to_browser(self, mock_subprocess, mock_urlopen, mock_private, mock_run, capsys):
        """When one-click POST fails, fall back to opening the browser."""
        from my_cli.commands.mail.actions import cmd_unsubscribe
        import urllib.error

        mock_run.return_value = (
            f"Newsletter"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: <https://example.com/unsub>\n"
            f"List-Unsubscribe-Post: List-Unsubscribe=One-Click\n"
        )

        # Make POST fail
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        args = _make_args(id=42, dry_run=False, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert "browser" in out
        assert mock_subprocess.called


class TestUnsubscribeBrowserFallback:
    """Test the browser fallback (HTTPS only, no one-click)."""

    @patch("my_cli.commands.mail.actions.run")
    @patch("my_cli.commands.mail.actions.subprocess.run")
    def test_opens_browser_when_no_one_click(self, mock_subprocess, mock_run, capsys):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        mock_run.return_value = (
            f"Digest"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: <https://example.com/unsub>\n"
            # No List-Unsubscribe-Post header => no one-click
        )

        args = _make_args(id=42, dry_run=False, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert "browser" in out
        mock_subprocess.assert_called_once()
        cmd_args = mock_subprocess.call_args[0][0]
        assert "open" in cmd_args
        assert "https://example.com/unsub" in cmd_args

    @patch("my_cli.commands.mail.actions.run")
    def test_mailto_only_shows_address(self, mock_run, capsys):
        from my_cli.commands.mail.actions import cmd_unsubscribe

        mock_run.return_value = (
            f"Old Newsletter"
            f"{FIELD_SEPARATOR}HEADER_SPLIT{FIELD_SEPARATOR}"
            f"List-Unsubscribe: <mailto:leave@example.com>\n"
        )

        args = _make_args(id=42, dry_run=False, open=False)
        cmd_unsubscribe(args)

        out = capsys.readouterr().out
        assert "mailto" in out.lower() or "leave@example.com" in out


class TestExtractUrls:
    """Unit tests for _extract_urls."""

    def test_extracts_https(self):
        from my_cli.commands.mail.actions import _extract_urls
        https, mailto = _extract_urls("<https://example.com/unsub>")
        assert https == ["https://example.com/unsub"]
        assert mailto == []

    def test_extracts_mailto(self):
        from my_cli.commands.mail.actions import _extract_urls
        https, mailto = _extract_urls("<mailto:unsub@example.com>")
        assert https == []
        assert mailto == ["mailto:unsub@example.com"]

    def test_extracts_both(self):
        from my_cli.commands.mail.actions import _extract_urls
        https, mailto = _extract_urls(
            "<https://example.com/unsub>, <mailto:unsub@example.com>"
        )
        assert https == ["https://example.com/unsub"]
        assert mailto == ["mailto:unsub@example.com"]

    def test_empty_header(self):
        from my_cli.commands.mail.actions import _extract_urls
        https, mailto = _extract_urls("")
        assert https == []
        assert mailto == []


# ===========================================================================
# todoist_integration.py — HTTP calls
# ===========================================================================

class TestTodoistIntegration:
    """Test cmd_to_todoist with mocked HTTP and AppleScript."""

    def _make_args(self, **kwargs):
        defaults = {
            "json": False,
            "account": "iCloud",
            "mailbox": "INBOX",
            "id": 99,
            "project": None,
            "priority": 1,
            "due": None,
        }
        defaults.update(kwargs)
        return Namespace(**defaults)

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_success_without_project(self, mock_urlopen, mock_config, mock_run, capsys):
        """Task created in Todoist inbox when --project is not provided."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Important Meeting{FIELD_SEPARATOR}"
            f"boss@corp.com{FIELD_SEPARATOR}"
            f"Monday Jan 1 2026"
        )

        response_payload = {
            "id": "task_abc123",
            "content": "Important Meeting",
            "url": "https://todoist.com/tasks/task_abc123",
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_payload).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        args = self._make_args()
        cmd_to_todoist(args)

        out = capsys.readouterr().out
        assert "Important Meeting" in out
        assert "https://todoist.com/tasks/task_abc123" in out
        # Only one urlopen call (no project lookup)
        assert mock_urlopen.call_count == 1

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_success_with_project(self, mock_urlopen, mock_config, mock_run, capsys):
        """When --project is set, resolves project ID first, then creates task."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Follow up{FIELD_SEPARATOR}alice@example.com{FIELD_SEPARATOR}Tuesday"
        )

        projects_list = [
            {"id": "proj_work", "name": "Work"},
            {"id": "proj_personal", "name": "Personal"},
        ]
        task_response = {"id": "task_xyz", "content": "Follow up", "url": "https://todoist.com/t/xyz"}

        # First call: GET /projects; second call: POST /tasks
        resp1 = MagicMock()
        resp1.read.return_value = json.dumps(projects_list).encode("utf-8")
        resp1.__enter__ = lambda s: s
        resp1.__exit__ = MagicMock(return_value=False)

        resp2 = MagicMock()
        resp2.read.return_value = json.dumps(task_response).encode("utf-8")
        resp2.__enter__ = lambda s: s
        resp2.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [resp1, resp2]

        args = self._make_args(project="Work")
        cmd_to_todoist(args)

        out = capsys.readouterr().out
        assert "Follow up" in out
        # Two calls: project lookup + task creation
        assert mock_urlopen.call_count == 2

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_project_not_found_dies(self, mock_urlopen, mock_config, mock_run):
        """When named project doesn't exist, die() is called."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Test Email{FIELD_SEPARATOR}x@y.com{FIELD_SEPARATOR}Wednesday"
        )

        resp = MagicMock()
        resp.read.return_value = json.dumps([]).encode("utf-8")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        args = self._make_args(project="NonExistentProject")
        with pytest.raises(SystemExit) as exc_info:
            cmd_to_todoist(args)
        assert exc_info.value.code == 1

    @patch("my_cli.commands.mail.todoist_integration.get_config")
    def test_missing_api_token_dies(self, mock_config, capsys):
        """Should die() when todoist_api_token not in config."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {}  # No token

        args = self._make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_to_todoist(args)
        assert exc_info.value.code == 1

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_http_error_dies(self, mock_urlopen, mock_config, mock_run):
        """When Todoist API returns HTTP error, die() is called."""
        import urllib.error
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Email{FIELD_SEPARATOR}x@y.com{FIELD_SEPARATOR}Thursday"
        )

        err_response = MagicMock()
        err_response.read.return_value = b"Unauthorized"
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.todoist.com/rest/v2/tasks",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b"Unauthorized"),
        )

        args = self._make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_to_todoist(args)
        assert exc_info.value.code == 1

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_creates_task_json_output(self, mock_urlopen, mock_config, mock_run, capsys):
        """--json flag returns structured task data."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Invoice Due{FIELD_SEPARATOR}billing@shop.com{FIELD_SEPARATOR}Friday"
        )

        response_payload = {"id": "task_111", "content": "Invoice Due"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_payload).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        args = self._make_args(json=True)
        cmd_to_todoist(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["id"] == "task_111"
        assert data["content"] == "Invoice Due"


# ===========================================================================
# inbox_tools.py — smoke tests
# ===========================================================================

class TestProcessInbox:
    """Smoke tests for cmd_process_inbox."""

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_empty_inbox(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        mock_run.return_value = ""
        args = mock_args()
        cmd_process_inbox(args)

        out = capsys.readouterr().out
        assert "No unread messages" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_categorizes_flagged(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        # One flagged message from a real person
        row = (
            f"iCloud{FIELD_SEPARATOR}101{FIELD_SEPARATOR}"
            f"Important Notice{FIELD_SEPARATOR}boss@company.com{FIELD_SEPARATOR}"
            f"Mon Jan 01 2026{FIELD_SEPARATOR}true"
        )
        mock_run.return_value = row + "\n"

        args = mock_args()
        cmd_process_inbox(args)

        out = capsys.readouterr().out
        assert "FLAGGED" in out
        assert "Important Notice" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_categorizes_notifications(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        row = (
            f"iCloud{FIELD_SEPARATOR}202{FIELD_SEPARATOR}"
            f"Your weekly digest{FIELD_SEPARATOR}noreply@service.com{FIELD_SEPARATOR}"
            f"Tue Jan 02 2026{FIELD_SEPARATOR}false"
        )
        mock_run.return_value = row + "\n"

        args = mock_args()
        cmd_process_inbox(args)

        out = capsys.readouterr().out
        assert "NOTIFICATIONS" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_categorizes_people(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        row = (
            f"iCloud{FIELD_SEPARATOR}303{FIELD_SEPARATOR}"
            f"Lunch tomorrow?{FIELD_SEPARATOR}friend@gmail.com{FIELD_SEPARATOR}"
            f"Wed Jan 03 2026{FIELD_SEPARATOR}false"
        )
        mock_run.return_value = row + "\n"

        args = mock_args()
        cmd_process_inbox(args)

        out = capsys.readouterr().out
        assert "PEOPLE" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_json_output(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        row = (
            f"iCloud{FIELD_SEPARATOR}404{FIELD_SEPARATOR}"
            f"Update{FIELD_SEPARATOR}notifications@app.com{FIELD_SEPARATOR}"
            f"Thu Jan 04 2026{FIELD_SEPARATOR}false"
        )
        mock_run.return_value = row + "\n"

        args = mock_args(json=True)
        cmd_process_inbox(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "total" in data
        assert "flagged" in data
        assert "people" in data
        assert "notifications" in data

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_skips_malformed_lines(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_process_inbox

        # Good line + malformed line (not enough fields)
        good = (
            f"iCloud{FIELD_SEPARATOR}505{FIELD_SEPARATOR}"
            f"Hello{FIELD_SEPARATOR}alice@example.com{FIELD_SEPARATOR}"
            f"Fri Jan 05 2026{FIELD_SEPARATOR}false"
        )
        bad = "only-one-field"
        mock_run.return_value = good + "\n" + bad + "\n"

        args = mock_args()
        cmd_process_inbox(args)

        out = capsys.readouterr().out
        # Should still show the good message
        assert "PEOPLE" in out


class TestCleanNewsletters:
    """Smoke tests for cmd_clean_newsletters."""

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_empty_mailbox(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        mock_run.return_value = ""
        args = mock_args()
        cmd_clean_newsletters(args)

        out = capsys.readouterr().out
        assert "No messages found" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_identifies_noreply_sender(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        # Two rows from a noreply sender
        row1 = f"noreply@news.com{FIELD_SEPARATOR}true"
        row2 = f"noreply@news.com{FIELD_SEPARATOR}false"
        mock_run.return_value = row1 + "\n" + row2 + "\n"

        args = mock_args()
        cmd_clean_newsletters(args)

        out = capsys.readouterr().out
        assert "noreply@news.com" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_identifies_bulk_sender(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        # Same sender 4 times (>= 3 is threshold)
        rows = "\n".join(
            f"digest@weekly.com{FIELD_SEPARATOR}true" for _ in range(4)
        )
        mock_run.return_value = rows + "\n"

        args = mock_args()
        cmd_clean_newsletters(args)

        out = capsys.readouterr().out
        assert "digest@weekly.com" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_no_newsletters_found(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        # One unique sender — not a newsletter
        row = f"alice@example.com{FIELD_SEPARATOR}true"
        mock_run.return_value = row + "\n"

        args = mock_args()
        cmd_clean_newsletters(args)

        out = capsys.readouterr().out
        assert "No newsletter senders" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_json_output(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_clean_newsletters

        rows = "\n".join(
            f"updates@service.com{FIELD_SEPARATOR}false" for _ in range(3)
        )
        mock_run.return_value = rows + "\n"

        args = mock_args(json=True)
        cmd_clean_newsletters(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "newsletters" in data
        assert len(data["newsletters"]) >= 1


class TestWeeklyReview:
    """Smoke tests for cmd_weekly_review."""

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_all_empty(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        mock_run.return_value = ""
        args = mock_args(days=7)
        cmd_weekly_review(args)

        out = capsys.readouterr().out
        assert "Weekly Review" in out
        assert "Flagged Messages" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_shows_flagged(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        flagged_row = (
            f"111{FIELD_SEPARATOR}Action Required{FIELD_SEPARATOR}"
            f"boss@work.com{FIELD_SEPARATOR}Mon Jan 01 2026"
        )
        # Three separate run() calls: flagged, attachments, unreplied
        mock_run.side_effect = [
            flagged_row + "\n",  # flagged
            "",                   # attachments
            "",                   # unreplied
        ]

        args = mock_args(days=7)
        cmd_weekly_review(args)

        out = capsys.readouterr().out
        assert "Action Required" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_shows_attachments(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        attach_row = (
            f"222{FIELD_SEPARATOR}Budget Q1{FIELD_SEPARATOR}"
            f"finance@corp.com{FIELD_SEPARATOR}Tue Jan 02 2026{FIELD_SEPARATOR}3"
        )
        mock_run.side_effect = [
            "",                  # flagged
            attach_row + "\n",   # attachments
            "",                  # unreplied
        ]

        args = mock_args(days=7)
        cmd_weekly_review(args)

        out = capsys.readouterr().out
        assert "Budget Q1" in out
        assert "3 attachments" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_unreplied_skips_noreply(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        noreply_row = (
            f"333{FIELD_SEPARATOR}Notification{FIELD_SEPARATOR}"
            f"noreply@service.com{FIELD_SEPARATOR}Wed Jan 03 2026"
        )
        mock_run.side_effect = [
            "",                    # flagged
            "",                    # attachments
            noreply_row + "\n",    # unreplied
        ]

        args = mock_args(days=7)
        cmd_weekly_review(args)

        out = capsys.readouterr().out
        # noreply sender should be filtered out
        assert "Unreplied from People (0)" in out

    @patch("my_cli.commands.mail.inbox_tools.run")
    def test_json_output(self, mock_run, capsys, mock_args):
        from my_cli.commands.mail.inbox_tools import cmd_weekly_review

        mock_run.return_value = ""
        args = mock_args(days=7, json=True)
        cmd_weekly_review(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "days" in data
        assert "flagged_messages" in data
        assert "attachment_messages" in data
        assert "unreplied_messages" in data


# ===========================================================================
# composite.py — _export_bulk with RECORD_SEPARATOR parsing
# ===========================================================================

class TestExportBulk:
    """Test bulk export RECORD_SEPARATOR parsing in _export_bulk."""

    def _run_export_bulk(self, monkeypatch, mock_result: str, dest_dir: str):
        """Helper to invoke _export_bulk with a mocked AppleScript run."""
        from my_cli.commands.mail.composite import _export_bulk

        mock_run = Mock(return_value=mock_result)
        monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

        args = _make_args(after=None)
        _export_bulk(args, "INBOX", "iCloud", dest_dir, after=None)
        return mock_run

    def test_single_message_exported(self, monkeypatch, tmp_path, capsys):
        from my_cli.config import RECORD_SEPARATOR

        msg_data = (
            f"42{FIELD_SEPARATOR}"
            f"Hello World{FIELD_SEPARATOR}"
            f"alice@example.com{FIELD_SEPARATOR}"
            f"Mon Jan 01 2026{FIELD_SEPARATOR}"
            f"This is the body."
        )
        result = msg_data + RECORD_SEPARATOR

        self._run_export_bulk(monkeypatch, result, str(tmp_path))

        out = capsys.readouterr().out
        assert "Exported 1" in out
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".md"
        content = files[0].read_text()
        assert "Hello World" in content
        assert "This is the body." in content

    def test_multiple_messages_exported(self, monkeypatch, tmp_path, capsys):
        from my_cli.config import RECORD_SEPARATOR

        def make_record(msg_id, subject, body):
            return (
                f"{msg_id}{FIELD_SEPARATOR}"
                f"{subject}{FIELD_SEPARATOR}"
                f"sender@example.com{FIELD_SEPARATOR}"
                f"Mon Jan 01 2026{FIELD_SEPARATOR}"
                f"{body}"
            )

        result = (
            make_record(1, "First Message", "Body one") + RECORD_SEPARATOR + "\n"
            + make_record(2, "Second Message", "Body two") + RECORD_SEPARATOR + "\n"
        )

        self._run_export_bulk(monkeypatch, result, str(tmp_path))

        out = capsys.readouterr().out
        assert "Exported 2" in out
        files = sorted(tmp_path.iterdir())
        assert len(files) == 2

    def test_empty_result(self, monkeypatch, tmp_path, capsys):
        self._run_export_bulk(monkeypatch, "", str(tmp_path))

        out = capsys.readouterr().out
        assert "Exported 0" in out

    def test_skips_malformed_entries(self, monkeypatch, tmp_path, capsys):
        from my_cli.config import RECORD_SEPARATOR

        good = (
            f"10{FIELD_SEPARATOR}"
            f"Good Subject{FIELD_SEPARATOR}"
            f"x@y.com{FIELD_SEPARATOR}"
            f"Monday{FIELD_SEPARATOR}"
            f"Content here"
        )
        bad = "only-one-field"
        result = good + RECORD_SEPARATOR + "\n" + bad + RECORD_SEPARATOR + "\n"

        self._run_export_bulk(monkeypatch, result, str(tmp_path))

        out = capsys.readouterr().out
        assert "Exported 1" in out

    def test_body_with_field_separator(self, monkeypatch, tmp_path, capsys):
        """Body content containing FIELD_SEPARATOR should be preserved."""
        from my_cli.config import RECORD_SEPARATOR

        body_with_sep = f"Line 1{FIELD_SEPARATOR}Line 2 (continuation)"
        record = (
            f"77{FIELD_SEPARATOR}"
            f"Complex Body{FIELD_SEPARATOR}"
            f"sender@example.com{FIELD_SEPARATOR}"
            f"Tuesday{FIELD_SEPARATOR}"
            + body_with_sep
        )
        result = record + RECORD_SEPARATOR

        self._run_export_bulk(monkeypatch, result, str(tmp_path))

        files = list(tmp_path.iterdir())
        assert len(files) == 1
        content = files[0].read_text()
        # The body parts joined with FIELD_SEPARATOR should appear
        assert "Line 1" in content

    def test_export_creates_dest_dir(self, monkeypatch, tmp_path, capsys):
        """_export_bulk creates the destination directory if it doesn't exist."""
        from my_cli.config import RECORD_SEPARATOR

        new_dir = str(tmp_path / "new_subdir")
        assert not os.path.exists(new_dir)

        msg_data = (
            f"5{FIELD_SEPARATOR}"
            f"Test{FIELD_SEPARATOR}"
            f"x@y.com{FIELD_SEPARATOR}"
            f"Wednesday{FIELD_SEPARATOR}"
            f"body"
        )
        result = msg_data + RECORD_SEPARATOR

        self._run_export_bulk(monkeypatch, result, new_dir)

        assert os.path.isdir(new_dir)
        out = capsys.readouterr().out
        assert "Exported 1" in out

    def test_json_output(self, monkeypatch, tmp_path, capsys):
        from my_cli.commands.mail.composite import _export_bulk
        from my_cli.config import RECORD_SEPARATOR

        msg_data = (
            f"9{FIELD_SEPARATOR}"
            f"JSON Test{FIELD_SEPARATOR}"
            f"x@y.com{FIELD_SEPARATOR}"
            f"Thursday{FIELD_SEPARATOR}"
            f"body"
        )
        result = msg_data + RECORD_SEPARATOR

        mock_run = Mock(return_value=result)
        monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

        args = _make_args(after=None, json=True)
        _export_bulk(args, "INBOX", "iCloud", str(tmp_path), after=None)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["exported"] == 1
        assert "directory" in data


# ===========================================================================
# parse_message_line — new helper in mail_helpers.py
# ===========================================================================

class TestParseMessageLine:
    """Test the parse_message_line() helper added in the refactor."""

    def test_basic_parse(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = f"42{FIELD_SEPARATOR}Hello{FIELD_SEPARATOR}alice@x.com{FIELD_SEPARATOR}Monday"
        result = parse_message_line(line, ["id", "subject", "sender", "date"], FIELD_SEPARATOR)

        assert result is not None
        assert result["id"] == 42
        assert result["subject"] == "Hello"
        assert result["sender"] == "alice@x.com"
        assert result["date"] == "Monday"

    def test_id_coercion_to_int(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = f"123{FIELD_SEPARATOR}Subject"
        result = parse_message_line(line, ["id", "subject"], FIELD_SEPARATOR)
        assert result["id"] == 123
        assert isinstance(result["id"], int)

    def test_non_numeric_id_kept_as_string(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = f"abc{FIELD_SEPARATOR}Subject"
        result = parse_message_line(line, ["id", "subject"], FIELD_SEPARATOR)
        assert result["id"] == "abc"

    def test_bool_field_coercion_true(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = f"1{FIELD_SEPARATOR}true"
        result = parse_message_line(line, ["id", "flagged"], FIELD_SEPARATOR)
        assert result["flagged"] is True

    def test_bool_field_coercion_false(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = f"2{FIELD_SEPARATOR}false"
        result = parse_message_line(line, ["id", "read"], FIELD_SEPARATOR)
        assert result["read"] is False

    def test_last_field_absorbs_remainder(self):
        from my_cli.util.mail_helpers import parse_message_line

        body = f"part1{FIELD_SEPARATOR}part2{FIELD_SEPARATOR}part3"
        line = f"5{FIELD_SEPARATOR}{body}"
        result = parse_message_line(line, ["id", "body"], FIELD_SEPARATOR)
        assert result["body"] == body

    def test_insufficient_fields_returns_none(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = "only_one_field"
        result = parse_message_line(line, ["id", "subject", "sender"], FIELD_SEPARATOR)
        assert result is None

    def test_exactly_minimum_fields(self):
        from my_cli.util.mail_helpers import parse_message_line

        line = f"7{FIELD_SEPARATOR}Subject Only"
        result = parse_message_line(line, ["id", "subject"], FIELD_SEPARATOR)
        assert result is not None
        assert result["id"] == 7
        assert result["subject"] == "Subject Only"


# ===========================================================================
# Bug fix: to-todoist timeout and token validation
# ===========================================================================

class TestTodoistTimeoutAndTokenValidation:
    """Tests for to-todoist hang fix and token validation."""

    def _make_args(self, **kwargs):
        defaults = {
            "json": False,
            "account": "iCloud",
            "mailbox": "INBOX",
            "id": 42,
            "project": None,
            "priority": 1,
            "due": None,
        }
        defaults.update(kwargs)
        return Namespace(**defaults)

    @patch("my_cli.commands.mail.todoist_integration.get_config")
    def test_empty_string_token_dies(self, mock_config, capsys):
        """Empty-string token (passes 'if not token' check but is invalid) is caught early."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "   "}  # whitespace-only

        args = self._make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_to_todoist(args)
        assert exc_info.value.code == 1
        out = capsys.readouterr()
        assert "invalid" in out.err.lower() or "invalid" in out.out.lower()

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_socket_timeout_on_task_create_dies(self, mock_urlopen, mock_config, mock_run, capsys):
        """socket.timeout during task creation produces a clean error (no hang)."""
        import socket
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Subject{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}Tuesday"
        )
        mock_urlopen.side_effect = socket.timeout("timed out")

        args = self._make_args()
        with pytest.raises(SystemExit) as exc_info:
            cmd_to_todoist(args)
        assert exc_info.value.code == 1
        out = capsys.readouterr()
        assert "timed out" in out.err.lower() or "timeout" in out.err.lower()

    @patch("my_cli.commands.mail.todoist_integration.run")
    @patch("my_cli.commands.mail.todoist_integration.get_config")
    @patch("my_cli.commands.mail.todoist_integration.urllib.request.urlopen")
    def test_urlopen_has_timeout_kwarg(self, mock_urlopen, mock_config, mock_run, capsys):
        """urlopen is called with an explicit timeout= kwarg (prevents silent hang)."""
        from my_cli.commands.mail.todoist_integration import cmd_to_todoist
        from my_cli.config import APPLESCRIPT_TIMEOUT_SHORT

        mock_config.return_value = {"todoist_api_token": "fake-token"}
        mock_run.return_value = (
            f"Subject{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}Tuesday"
        )

        response_payload = {"id": "t1", "content": "Subject"}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(response_payload).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        cmd_to_todoist(self._make_args())

        # Every urlopen call must include a timeout kwarg
        for call in mock_urlopen.call_args_list:
            assert "timeout" in call.kwargs, "urlopen called without timeout kwarg"
            assert call.kwargs["timeout"] == APPLESCRIPT_TIMEOUT_SHORT


# ===========================================================================
# Bug fix: not-junk uses subject+sender search, not stale ID
# ===========================================================================

class TestNotJunkSubjectSenderSearch:
    """Tests for not-junk search-by-subject+sender fix."""

    def test_try_not_junk_uses_subject_sender_when_provided(self):
        """_try_not_junk_in_mailbox builds subject+sender AppleScript when args are given."""
        import subprocess as _subprocess
        from unittest.mock import patch, MagicMock
        from my_cli.commands.mail.actions import _try_not_junk_in_mailbox

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Test Subject\n"

        with patch.object(_subprocess, "run", return_value=mock_result) as mock_sp:
            result = _try_not_junk_in_mailbox(
                "iCloud", "Junk", "INBOX", 99,
                subject="Test Subject", sender="sender@example.com"
            )

        assert result == "Test Subject"
        # The AppleScript passed to osascript should search by subject+sender, not by ID
        script = mock_sp.call_args[0][0][2]  # argv[2] is the -e script
        assert "Test Subject" in script
        assert "sender@example.com" in script
        assert "whose id is" not in script  # must NOT fall back to ID search

    def test_try_not_junk_falls_back_to_id_when_no_subject(self):
        """_try_not_junk_in_mailbox uses ID lookup when subject/sender are empty."""
        import subprocess as _subprocess
        from unittest.mock import patch, MagicMock
        from my_cli.commands.mail.actions import _try_not_junk_in_mailbox

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Some Subject\n"

        with patch.object(_subprocess, "run", return_value=mock_result) as mock_sp:
            result = _try_not_junk_in_mailbox(
                "iCloud", "Junk", "INBOX", 42,
                subject="", sender=""
            )

        assert result == "Some Subject"
        script = mock_sp.call_args[0][0][2]
        assert "whose id is 42" in script

    def test_try_not_junk_returns_none_on_applescript_error(self):
        """Any AppleScript error returns None (no internal error leaks to user)."""
        import subprocess as _subprocess
        from unittest.mock import patch, MagicMock
        from my_cli.commands.mail.actions import _try_not_junk_in_mailbox

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Mail got an error: unexpected internal error"

        with patch.object(_subprocess, "run", return_value=mock_result):
            result = _try_not_junk_in_mailbox(
                "iCloud", "Junk", "INBOX", 42,
                subject="Subject", sender="sender@example.com"
            )

        assert result is None  # error swallowed, not raised

    def test_cmd_not_junk_passes_subject_sender_to_helper(self, monkeypatch, capsys):
        """cmd_not_junk fetches original subject+sender and passes them to _try_not_junk_in_mailbox."""
        import subprocess as _subprocess
        from argparse import Namespace
        from unittest.mock import MagicMock, patch
        from my_cli.commands.mail.actions import cmd_not_junk
        from my_cli.config import FIELD_SEPARATOR

        # Simulate successful fetch of subject+sender from INBOX
        fetch_result = MagicMock()
        fetch_result.returncode = 0
        fetch_result.stdout = f"My Subject{FIELD_SEPARATOR}alice@example.com\n"

        helper_mock = MagicMock(return_value="My Subject")

        with patch.object(_subprocess, "run", return_value=fetch_result):
            monkeypatch.setattr(
                "my_cli.commands.mail.actions._try_not_junk_in_mailbox",
                helper_mock,
            )
            args = Namespace(id=100, account="iCloud", mailbox=None, json=False)
            cmd_not_junk(args)

        # Verify helper was called with subject and sender keyword args
        call_kwargs = helper_mock.call_args
        assert call_kwargs.kwargs.get("subject") == "My Subject" or \
               (len(call_kwargs[1]) > 0 and call_kwargs[1].get("subject") == "My Subject")
        assert "alice@example.com" in str(call_kwargs)
