"""Smoke tests for top 10 mail command functions."""

from unittest.mock import Mock


from my_cli.config import FIELD_SEPARATOR


# ---------------------------------------------------------------------------
# cmd_inbox (accounts.py)
# ---------------------------------------------------------------------------

def test_cmd_inbox_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_inbox displays unread counts across accounts."""
    from my_cli.commands.mail.accounts import cmd_inbox

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}2{FIELD_SEPARATOR}10\n"
        f"MSG{FIELD_SEPARATOR}iCloud{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}sender@example.com{FIELD_SEPARATOR}Mon Feb 14 2026 10:00:00\n"
        f"Example Account{FIELD_SEPARATOR}0{FIELD_SEPARATOR}5\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args()
    cmd_inbox(args)

    captured = capsys.readouterr()
    assert "Inbox Summary" in captured.out
    assert "iCloud:" in captured.out
    assert "Unread: 2" in captured.out
    assert "[123] Test Subject" in captured.out


def test_cmd_inbox_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_inbox --json returns JSON array."""
    from my_cli.commands.mail.accounts import cmd_inbox

    mock_run = Mock(return_value=f"iCloud{FIELD_SEPARATOR}1{FIELD_SEPARATOR}5\n")
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args(json=True)
    cmd_inbox(args)

    captured = capsys.readouterr()
    assert '"account": "iCloud"' in captured.out
    assert '"unread": 1' in captured.out


def test_cmd_inbox_empty(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_inbox handles empty result."""
    from my_cli.commands.mail.accounts import cmd_inbox

    mock_run = Mock(return_value="")
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args()
    cmd_inbox(args)

    captured = capsys.readouterr()
    assert "No mail accounts found" in captured.out


# ---------------------------------------------------------------------------
# cmd_list (messages.py)
# ---------------------------------------------------------------------------

def test_cmd_list_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_list displays messages."""
    from my_cli.commands.mail.messages import cmd_list

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}sender@example.com{FIELD_SEPARATOR}"
        f"Mon Feb 14 2026{FIELD_SEPARATOR}true{FIELD_SEPARATOR}false\n"
        f"124{FIELD_SEPARATOR}Another{FIELD_SEPARATOR}other@example.com{FIELD_SEPARATOR}"
        f"Tue Feb 15 2026{FIELD_SEPARATOR}false{FIELD_SEPARATOR}true\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.messages.run", mock_run)

    args = mock_args()
    cmd_list(args)

    captured = capsys.readouterr()
    assert "Messages in INBOX" in captured.out
    assert "[123] Test Subject" in captured.out
    assert "[124] Another" in captured.out
    assert "UNREAD" in captured.out
    assert "FLAGGED" in captured.out


def test_cmd_list_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_list --json returns JSON array."""
    from my_cli.commands.mail.messages import cmd_list

    mock_run = Mock(return_value=f"123{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}true{FIELD_SEPARATOR}false\n")
    monkeypatch.setattr("my_cli.commands.mail.messages.run", mock_run)

    args = mock_args(json=True)
    cmd_list(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"subject": "Test"' in captured.out
    assert '"read": true' in captured.out


# ---------------------------------------------------------------------------
# cmd_read (messages.py)
# ---------------------------------------------------------------------------

def test_cmd_read_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_read displays full message details."""
    from my_cli.commands.mail.messages import cmd_read

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}msg-id-123{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}"
        f"Mon Feb 14 2026{FIELD_SEPARATOR}true{FIELD_SEPARATOR}false{FIELD_SEPARATOR}false{FIELD_SEPARATOR}"
        f"false{FIELD_SEPARATOR}false{FIELD_SEPARATOR}false{FIELD_SEPARATOR}"
        f"to@ex.com,{FIELD_SEPARATOR}cc@ex.com,{FIELD_SEPARATOR}reply@ex.com{FIELD_SEPARATOR}"
        f"This is the message body.{FIELD_SEPARATOR}2"
    ))
    monkeypatch.setattr("my_cli.commands.mail.messages.run", mock_run)

    args = mock_args(id=123)
    cmd_read(args)

    captured = capsys.readouterr()
    assert "Message Details:" in captured.out
    assert "Subject: Test Subject" in captured.out
    assert "From: sender@ex.com" in captured.out
    assert "This is the message body." in captured.out
    assert "Attachments: 2" in captured.out


def test_cmd_read_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_read --json returns JSON object."""
    from my_cli.commands.mail.messages import cmd_read

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}msg-id{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}"
        f"Mon{FIELD_SEPARATOR}true{FIELD_SEPARATOR}false{FIELD_SEPARATOR}false{FIELD_SEPARATOR}"
        f"false{FIELD_SEPARATOR}false{FIELD_SEPARATOR}false{FIELD_SEPARATOR}"
        f"to@ex.com,{FIELD_SEPARATOR}{FIELD_SEPARATOR}{FIELD_SEPARATOR}"
        f"Body text{FIELD_SEPARATOR}0"
    ))
    monkeypatch.setattr("my_cli.commands.mail.messages.run", mock_run)

    args = mock_args(id=123, json=True)
    cmd_read(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"subject": "Test"' in captured.out
    assert '"body": "Body text"' in captured.out


# ---------------------------------------------------------------------------
# cmd_search (messages.py)
# ---------------------------------------------------------------------------

def test_cmd_search_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_search finds messages."""
    from my_cli.commands.mail.messages import cmd_search

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}"
        f"Mon Feb 14{FIELD_SEPARATOR}true{FIELD_SEPARATOR}false{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.messages.run", mock_run)

    args = mock_args(query="test")
    cmd_search(args)

    captured = capsys.readouterr()
    assert "Search results for 'test'" in captured.out
    assert "[123] Test Subject" in captured.out
    assert "Location: INBOX [iCloud]" in captured.out


def test_cmd_search_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_search --json returns JSON array."""
    from my_cli.commands.mail.messages import cmd_search

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}"
        f"Mon{FIELD_SEPARATOR}true{FIELD_SEPARATOR}false{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.messages.run", mock_run)

    args = mock_args(query="test", json=True)
    cmd_search(args)

    captured = capsys.readouterr()
    assert '"mailbox": "INBOX"' in captured.out
    assert '"account": "iCloud"' in captured.out


# ---------------------------------------------------------------------------
# cmd_mark_read (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_mark_read_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mark_read marks message as read."""
    from my_cli.commands.mail.actions import cmd_mark_read

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=123)
    cmd_mark_read(args)

    captured = capsys.readouterr()
    assert "marked as read" in captured.out
    assert "Test Subject" in captured.out


def test_cmd_mark_read_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mark_read --json returns JSON."""
    from my_cli.commands.mail.actions import cmd_mark_read

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=123, json=True)
    cmd_mark_read(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"status": "read"' in captured.out


# ---------------------------------------------------------------------------
# cmd_flag (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_flag_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_flag flags a message."""
    from my_cli.commands.mail.actions import cmd_flag

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=123)
    cmd_flag(args)

    captured = capsys.readouterr()
    assert "flagged" in captured.out
    assert "Test Subject" in captured.out


def test_cmd_flag_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_flag --json returns JSON."""
    from my_cli.commands.mail.actions import cmd_flag

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=123, json=True)
    cmd_flag(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"status": "flagged"' in captured.out


# ---------------------------------------------------------------------------
# cmd_delete (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_delete_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_delete moves message to Trash."""
    from my_cli.commands.mail.actions import cmd_delete

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=123)
    cmd_delete(args)

    captured = capsys.readouterr()
    assert "moved to Trash" in captured.out
    assert "Test Subject" in captured.out


def test_cmd_delete_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_delete --json returns JSON."""
    from my_cli.commands.mail.actions import cmd_delete

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=123, json=True)
    cmd_delete(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"status": "deleted"' in captured.out


# ---------------------------------------------------------------------------
# cmd_summary (ai.py)
# ---------------------------------------------------------------------------

def test_cmd_summary_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_summary lists unread messages concisely."""
    from my_cli.commands.mail.ai import cmd_summary

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Test Subject{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}Mon Feb 14 2026\n"
        f"iCloud{FIELD_SEPARATOR}124{FIELD_SEPARATOR}Another{FIELD_SEPARATOR}other@ex.com{FIELD_SEPARATOR}Tue Feb 15 2026\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args()
    cmd_summary(args)

    captured = capsys.readouterr()
    assert "2 unread:" in captured.out
    assert "[123]" in captured.out
    assert "Test Subject" in captured.out


def test_cmd_summary_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_summary --json returns JSON array."""
    from my_cli.commands.mail.ai import cmd_summary

    mock_run = Mock(return_value=f"iCloud{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}Mon\n")
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(json=True)
    cmd_summary(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"subject": "Test"' in captured.out


def test_cmd_summary_empty(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_summary handles no unread."""
    from my_cli.commands.mail.ai import cmd_summary

    mock_run = Mock(return_value="")
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args()
    cmd_summary(args)

    captured = capsys.readouterr()
    assert "No unread messages" in captured.out


# ---------------------------------------------------------------------------
# cmd_triage (ai.py)
# ---------------------------------------------------------------------------

def test_cmd_triage_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_triage groups unread by category."""
    from my_cli.commands.mail.ai import cmd_triage

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Flagged Message{FIELD_SEPARATOR}person@ex.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}true\n"
        f"iCloud{FIELD_SEPARATOR}124{FIELD_SEPARATOR}Personal{FIELD_SEPARATOR}friend@ex.com{FIELD_SEPARATOR}Tue{FIELD_SEPARATOR}false\n"
        f"iCloud{FIELD_SEPARATOR}125{FIELD_SEPARATOR}Notification{FIELD_SEPARATOR}noreply@ex.com{FIELD_SEPARATOR}Wed{FIELD_SEPARATOR}false\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args()
    cmd_triage(args)

    captured = capsys.readouterr()
    assert "Triage (3 unread):" in captured.out
    assert "FLAGGED (1):" in captured.out
    assert "PEOPLE (1):" in captured.out
    assert "NOTIFICATIONS (1):" in captured.out


def test_cmd_triage_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_triage --json returns categorized JSON."""
    from my_cli.commands.mail.ai import cmd_triage

    mock_run = Mock(return_value=f"iCloud{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}false\n")
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(json=True)
    cmd_triage(args)

    captured = capsys.readouterr()
    assert '"flagged":' in captured.out
    assert '"people":' in captured.out
    assert '"notifications":' in captured.out


# ---------------------------------------------------------------------------
# cmd_show_flagged (analytics.py)
# ---------------------------------------------------------------------------

def test_cmd_show_flagged_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_show_flagged lists flagged messages."""
    from my_cli.commands.mail.analytics import cmd_show_flagged

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}Flagged Subject{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}"
        f"Mon Feb 14{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.analytics.run", mock_run)

    args = mock_args()
    cmd_show_flagged(args)

    captured = capsys.readouterr()
    assert "Flagged messages" in captured.out
    assert "[123] Flagged Subject" in captured.out
    assert "Location: INBOX [iCloud]" in captured.out


def test_cmd_show_flagged_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_show_flagged --json returns JSON array."""
    from my_cli.commands.mail.analytics import cmd_show_flagged

    mock_run = Mock(return_value=(
        f"123{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}sender@ex.com{FIELD_SEPARATOR}"
        f"Mon{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}iCloud\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.analytics.run", mock_run)

    args = mock_args(json=True)
    cmd_show_flagged(args)

    captured = capsys.readouterr()
    assert '"id": 123' in captured.out
    assert '"mailbox": "INBOX"' in captured.out
