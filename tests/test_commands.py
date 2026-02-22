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


def test_cmd_inbox_account_filter(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_inbox -a filters to a single account."""
    from my_cli.commands.mail.accounts import cmd_inbox

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}1{FIELD_SEPARATOR}8\n"
        f"MSG{FIELD_SEPARATOR}iCloud{FIELD_SEPARATOR}200{FIELD_SEPARATOR}Filtered Subject{FIELD_SEPARATOR}x@x.com{FIELD_SEPARATOR}Mon\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args(account="iCloud")
    cmd_inbox(args)

    captured = capsys.readouterr()
    assert "iCloud:" in captured.out
    assert "Unread: 1" in captured.out
    # Verify the script sent to run() scopes to a single account
    script_sent = mock_run.call_args[0][0]
    assert 'account "iCloud"' in script_sent
    assert "every account" not in script_sent


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


def test_cmd_triage_account_filter(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_triage -a scopes to a single account."""
    from my_cli.commands.mail.ai import cmd_triage

    mock_run = Mock(return_value=f"iCloud{FIELD_SEPARATOR}123{FIELD_SEPARATOR}Test{FIELD_SEPARATOR}friend@ex.com{FIELD_SEPARATOR}Mon{FIELD_SEPARATOR}false\n")
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(account="iCloud")
    cmd_triage(args)

    captured = capsys.readouterr()
    assert "Triage" in captured.out
    # Verify the script sent to run() scopes to a single account
    script_sent = mock_run.call_args[0][0]
    assert 'account "iCloud"' in script_sent
    assert "every account" not in script_sent


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


# ---------------------------------------------------------------------------
# cmd_open (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_open_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_open opens message in Mail.app."""
    from my_cli.commands.mail.actions import cmd_open

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=12345)
    cmd_open(args)

    captured = capsys.readouterr()
    assert "Opened message 12345 in Mail.app" in captured.out


def test_cmd_open_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_open --json returns JSON."""
    from my_cli.commands.mail.actions import cmd_open

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=12345, json=True)
    cmd_open(args)

    captured = capsys.readouterr()
    assert '"opened": true' in captured.out
    assert '"message_id": 12345' in captured.out
    assert '"subject": "Test Subject"' in captured.out


def test_cmd_open_viewer_guard(monkeypatch, mock_args, capsys):
    """cmd_open AppleScript includes a guard to create a viewer if none exists."""
    from my_cli.commands.mail.actions import cmd_open

    mock_run = Mock(return_value="Test Subject")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=12345)
    cmd_open(args)

    # Verify the AppleScript passed to run() contains the viewer guard
    script = mock_run.call_args[0][0]
    assert "count of message viewers" in script
    assert "make new message viewer" in script


# ---------------------------------------------------------------------------
# cmd_reply (composite.py)
# ---------------------------------------------------------------------------

def test_cmd_reply_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_reply creates a reply draft."""
    from my_cli.commands.mail.composite import cmd_reply

    # run() is called twice: once to read the original, once to create the draft
    mock_run = Mock(side_effect=[
        f"Original Subject{chr(0x1F)}Sender Name <sender@example.com>{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}Original body text",
        "draft created",
    ])
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    args = mock_args(id=123, body="Thanks for your message.", json=False)
    cmd_reply(args)

    captured = capsys.readouterr()
    assert "Reply draft created" in captured.out
    assert "sender@example.com" in captured.out
    assert "Re: Original Subject" in captured.out


def test_cmd_reply_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_reply --json returns JSON."""
    from my_cli.commands.mail.composite import cmd_reply

    mock_run = Mock(side_effect=[
        f"Original Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}Body",
        "draft created",
    ])
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    args = mock_args(id=123, body="Reply text.", json=True)
    cmd_reply(args)

    captured = capsys.readouterr()
    assert '"status": "reply_draft_created"' in captured.out
    assert '"to": "sender@example.com"' in captured.out
    assert '"subject": "Re: Original Subject"' in captured.out


# ---------------------------------------------------------------------------
# cmd_forward (composite.py)
# ---------------------------------------------------------------------------

def test_cmd_forward_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_forward creates a forward draft."""
    from my_cli.commands.mail.composite import cmd_forward

    mock_run = Mock(side_effect=[
        f"Original Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}Original body",
        "draft created",
    ])
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    args = mock_args(id=123, to="forward@example.com", json=False)
    cmd_forward(args)

    captured = capsys.readouterr()
    assert "Forward draft created" in captured.out
    assert "forward@example.com" in captured.out
    assert "Fwd: Original Subject" in captured.out


def test_cmd_forward_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_forward --json returns JSON."""
    from my_cli.commands.mail.composite import cmd_forward

    mock_run = Mock(side_effect=[
        f"Original Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}Body",
        "draft created",
    ])
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    args = mock_args(id=123, to="forward@example.com", json=True)
    cmd_forward(args)

    captured = capsys.readouterr()
    assert '"status": "forward_draft_created"' in captured.out
    assert '"to": "forward@example.com"' in captured.out
    assert '"subject": "Fwd: Original Subject"' in captured.out


# ---------------------------------------------------------------------------
# cmd_export (composite.py)
# ---------------------------------------------------------------------------

def test_cmd_export_basic(monkeypatch, mock_args, tmp_path, capsys):
    """Smoke test: cmd_export writes a markdown file."""
    from my_cli.commands.mail.composite import cmd_export

    mock_run = Mock(return_value=(
        f"Test Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}to@example.com, {chr(0x1F)}This is the body."
    ))
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    dest = str(tmp_path)
    args = mock_args(target="123", to=dest, json=False, after=None)
    cmd_export(args)

    captured = capsys.readouterr()
    assert "Exported to:" in captured.out
    # Verify the file was actually created
    md_files = list(tmp_path.glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "# Test Subject" in content
    assert "sender@example.com" in content


def test_cmd_export_json(monkeypatch, mock_args, tmp_path, capsys):
    """Smoke test: cmd_export --json returns JSON."""
    from my_cli.commands.mail.composite import cmd_export

    mock_run = Mock(return_value=(
        f"Test Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}to@example.com, {chr(0x1F)}Body text."
    ))
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    dest = str(tmp_path)
    args = mock_args(target="123", to=dest, json=True, after=None)
    cmd_export(args)

    captured = capsys.readouterr()
    assert '"path":' in captured.out
    assert '"subject": "Test Subject"' in captured.out


# ---------------------------------------------------------------------------
# cmd_thread (composite.py)
# ---------------------------------------------------------------------------

def test_cmd_thread_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_thread shows conversation thread."""
    from my_cli.commands.mail.composite import cmd_thread

    # run() called twice: first for subject, then for thread messages
    mock_run = Mock(side_effect=[
        "Original Subject",
        (
            f"100{chr(0x1F)}Re: Original Subject{chr(0x1F)}person@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}INBOX{chr(0x1F)}iCloud\n"
            f"101{chr(0x1F)}Re: Original Subject{chr(0x1F)}other@example.com{chr(0x1F)}Tue Feb 15 2026{chr(0x1F)}INBOX{chr(0x1F)}iCloud\n"
        ),
    ])
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    args = mock_args(id=123, json=False, limit=100, all_accounts=False)
    cmd_thread(args)

    captured = capsys.readouterr()
    assert "Thread:" in captured.out
    assert "Original Subject" in captured.out
    assert "2 messages" in captured.out
    assert "[100]" in captured.out


def test_cmd_thread_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_thread --json returns JSON array."""
    from my_cli.commands.mail.composite import cmd_thread

    mock_run = Mock(side_effect=[
        "Original Subject",
        f"100{chr(0x1F)}Re: Original Subject{chr(0x1F)}person@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}INBOX{chr(0x1F)}iCloud\n",
    ])
    monkeypatch.setattr("my_cli.commands.mail.composite.run", mock_run)

    args = mock_args(id=123, json=True, limit=100, all_accounts=False)
    cmd_thread(args)

    captured = capsys.readouterr()
    assert '"id": 100' in captured.out
    assert '"subject": "Re: Original Subject"' in captured.out
    assert '"account": "iCloud"' in captured.out


# ---------------------------------------------------------------------------
# cmd_top_senders (analytics.py)
# ---------------------------------------------------------------------------

def test_cmd_top_senders_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_top_senders shows most frequent senders."""
    from my_cli.commands.mail.analytics import cmd_top_senders

    mock_run = Mock(return_value=(
        "alice@example.com\n"
        "bob@example.com\n"
        "alice@example.com\n"
        "alice@example.com\n"
        "bob@example.com\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.analytics.run", mock_run)

    args = mock_args(days=30, limit=10, json=False)
    cmd_top_senders(args)

    captured = capsys.readouterr()
    assert "Top 10 senders" in captured.out
    assert "alice@example.com" in captured.out
    assert "bob@example.com" in captured.out


def test_cmd_top_senders_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_top_senders --json returns JSON array."""
    from my_cli.commands.mail.analytics import cmd_top_senders

    mock_run = Mock(return_value=(
        "alice@example.com\n"
        "alice@example.com\n"
        "bob@example.com\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.analytics.run", mock_run)

    args = mock_args(days=30, limit=10, json=True)
    cmd_top_senders(args)

    captured = capsys.readouterr()
    assert '"sender":' in captured.out
    assert '"count":' in captured.out
    assert "alice@example.com" in captured.out


# ---------------------------------------------------------------------------
# cmd_digest (analytics.py)
# ---------------------------------------------------------------------------

def test_cmd_digest_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_digest shows unread grouped by sender domain."""
    from my_cli.commands.mail.analytics import cmd_digest

    mock_run = Mock(return_value=(
        f"iCloud{chr(0x1F)}123{chr(0x1F)}Newsletter Update{chr(0x1F)}news@example.com{chr(0x1F)}Mon Feb 14 2026\n"
        f"iCloud{chr(0x1F)}124{chr(0x1F)}Hello there{chr(0x1F)}friend@personal.org{chr(0x1F)}Tue Feb 15 2026\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.analytics.run", mock_run)

    args = mock_args(json=False)
    cmd_digest(args)

    captured = capsys.readouterr()
    assert "Unread Digest" in captured.out
    assert "example.com" in captured.out
    assert "[123]" in captured.out


def test_cmd_digest_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_digest --json returns JSON dict."""
    from my_cli.commands.mail.analytics import cmd_digest

    mock_run = Mock(return_value=(
        f"iCloud{chr(0x1F)}123{chr(0x1F)}Test Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.analytics.run", mock_run)

    args = mock_args(json=True)
    cmd_digest(args)

    captured = capsys.readouterr()
    assert '"example.com"' in captured.out
    assert '"id": 123' in captured.out


# ---------------------------------------------------------------------------
# cmd_headers (system.py)
# ---------------------------------------------------------------------------

def test_cmd_headers_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_headers shows email header summary."""
    from my_cli.commands.mail.system import cmd_headers

    raw_headers = (
        "From: Sender Name <sender@example.com>\n"
        "To: recipient@example.com\n"
        "Subject: Test Subject\n"
        "Date: Mon, 14 Feb 2026 10:00:00 +0000\n"
        "Message-Id: <abc123@example.com>\n"
        "Authentication-Results: mx.example.com; spf=pass dkim=pass dmarc=pass\n"
        "Received: from mail.example.com by mx.example.com\n"
        "Received: from smtp.example.com by mail.example.com\n"
    )
    mock_run = Mock(return_value=raw_headers)
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args(id=123, json=False, raw=False)
    cmd_headers(args)

    captured = capsys.readouterr()
    assert "From: Sender Name <sender@example.com>" in captured.out
    assert "Subject: Test Subject" in captured.out
    assert "SPF=pass" in captured.out
    assert "DKIM=pass" in captured.out
    assert "Hops: 2" in captured.out


def test_cmd_headers_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_headers --json returns JSON dict of headers."""
    from my_cli.commands.mail.system import cmd_headers

    raw_headers = (
        "From: sender@example.com\n"
        "To: recipient@example.com\n"
        "Subject: Test Subject\n"
        "Date: Mon, 14 Feb 2026 10:00:00 +0000\n"
        "Message-Id: <abc123@example.com>\n"
    )
    mock_run = Mock(return_value=raw_headers)
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args(id=123, json=True, raw=False)
    cmd_headers(args)

    captured = capsys.readouterr()
    assert '"From"' in captured.out
    assert '"Subject"' in captured.out
    assert "Test Subject" in captured.out


# ---------------------------------------------------------------------------
# cmd_rules (system.py)
# ---------------------------------------------------------------------------

def test_cmd_rules_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_rules lists mail rules."""
    from my_cli.commands.mail.system import cmd_rules

    mock_run = Mock(return_value=(
        f"Move Newsletters{chr(0x1F)}true\n"
        f"Archive Old Mail{chr(0x1F)}false\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args(json=False, action=None, rule_name=None)
    cmd_rules(args)

    captured = capsys.readouterr()
    assert "Mail Rules:" in captured.out
    assert "[ON] Move Newsletters" in captured.out
    assert "[OFF] Archive Old Mail" in captured.out


def test_cmd_rules_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_rules --json returns JSON array."""
    from my_cli.commands.mail.system import cmd_rules

    mock_run = Mock(return_value=(
        f"Move Newsletters{chr(0x1F)}true\n"
        f"Archive Old Mail{chr(0x1F)}false\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args(json=True, action=None, rule_name=None)
    cmd_rules(args)

    captured = capsys.readouterr()
    assert '"name": "Move Newsletters"' in captured.out
    assert '"enabled": true' in captured.out
    assert '"enabled": false' in captured.out


# ---------------------------------------------------------------------------
# cmd_attachments (attachments.py)
# ---------------------------------------------------------------------------

def test_cmd_attachments_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_attachments lists message attachments."""
    from my_cli.commands.mail.attachments import cmd_attachments

    mock_run = Mock(return_value=(
        "Test Subject\n"
        "report.pdf\n"
        "invoice.xlsx\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.attachments.run", mock_run)

    args = mock_args(id=123, json=False)
    cmd_attachments(args)

    captured = capsys.readouterr()
    assert "Attachments in" in captured.out
    assert "report.pdf" in captured.out
    assert "invoice.xlsx" in captured.out


def test_cmd_attachments_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_attachments --json returns JSON."""
    from my_cli.commands.mail.attachments import cmd_attachments

    mock_run = Mock(return_value=(
        "Test Subject\n"
        "document.pdf\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.attachments.run", mock_run)

    args = mock_args(id=123, json=True)
    cmd_attachments(args)

    captured = capsys.readouterr()
    assert '"subject": "Test Subject"' in captured.out
    assert '"attachments":' in captured.out
    assert "document.pdf" in captured.out


# ---------------------------------------------------------------------------
# cmd_context (ai.py)
# ---------------------------------------------------------------------------

def test_cmd_context_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_context shows message with thread history."""
    from my_cli.commands.mail.ai import cmd_context

    # run() called twice: once for main message, once for thread
    mock_run = Mock(side_effect=[
        f"Context Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}to@example.com, {chr(0x1F)}Main message body.",
        "",  # empty thread
    ])
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(id=123, json=False, limit=50, all_accounts=False)
    cmd_context(args)

    captured = capsys.readouterr()
    assert "=== Message ===" in captured.out
    assert "Context Subject" in captured.out
    assert "sender@example.com" in captured.out
    assert "Main message body." in captured.out


def test_cmd_context_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_context --json returns JSON with message and thread."""
    from my_cli.commands.mail.ai import cmd_context

    from my_cli.config import RECORD_SEPARATOR
    thread_entry = (
        f"200{chr(0x1F)}Re: Context Subject{chr(0x1F)}other@example.com"
        f"{chr(0x1F)}Tue Feb 15 2026{chr(0x1F)}Previous reply body."
    )
    mock_run = Mock(side_effect=[
        f"Context Subject{chr(0x1F)}sender@example.com{chr(0x1F)}Mon Feb 14 2026{chr(0x1F)}to@example.com, {chr(0x1F)}Main body.",
        thread_entry + RECORD_SEPARATOR,
    ])
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(id=123, json=True, limit=50, all_accounts=False)
    cmd_context(args)

    captured = capsys.readouterr()
    assert '"message":' in captured.out
    assert '"thread":' in captured.out
    assert '"subject": "Context Subject"' in captured.out


# ---------------------------------------------------------------------------
# cmd_find_related (ai.py)
# ---------------------------------------------------------------------------

def test_cmd_find_related_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_find_related searches and groups by conversation."""
    from unittest.mock import Mock
    from my_cli.commands.mail.ai import cmd_find_related

    search_result = (
        f"1{FIELD_SEPARATOR}Project Update{FIELD_SEPARATOR}alice@test.com{FIELD_SEPARATOR}Mon Feb 10 2026{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}Work\n"
        f"2{FIELD_SEPARATOR}Re: Project Update{FIELD_SEPARATOR}bob@test.com{FIELD_SEPARATOR}Tue Feb 11 2026{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}Work"
    )
    mock_run = Mock(return_value=search_result)
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(query="Project Update", json=False)
    cmd_find_related(args)

    captured = capsys.readouterr()
    assert "Related messages" in captured.out
    assert "Project Update" in captured.out


def test_cmd_find_related_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_find_related JSON output groups by thread."""
    from unittest.mock import Mock
    from my_cli.commands.mail.ai import cmd_find_related

    search_result = (
        f"1{FIELD_SEPARATOR}Meeting Notes{FIELD_SEPARATOR}alice@test.com{FIELD_SEPARATOR}Mon Feb 10 2026{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}Work"
    )
    mock_run = Mock(return_value=search_result)
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(query="Meeting Notes", json=True)
    cmd_find_related(args)

    captured = capsys.readouterr()
    assert "meeting notes" in captured.out  # normalized subject key


def test_cmd_find_related_empty(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_find_related handles no results."""
    from unittest.mock import Mock
    from my_cli.commands.mail.ai import cmd_find_related

    mock_run = Mock(return_value="")
    monkeypatch.setattr("my_cli.commands.mail.ai.run", mock_run)

    args = mock_args(query="nonexistent", json=False)
    cmd_find_related(args)

    captured = capsys.readouterr()
    assert "No messages found" in captured.out


# ---------------------------------------------------------------------------
# cmd_accounts (accounts.py)
# ---------------------------------------------------------------------------

def test_cmd_accounts_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_accounts lists configured mail accounts."""
    from my_cli.commands.mail.accounts import cmd_accounts

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}John Doe{FIELD_SEPARATOR}john@icloud.com{FIELD_SEPARATOR}true\n"
        f"Work Gmail{FIELD_SEPARATOR}John Doe{FIELD_SEPARATOR}john@work.com{FIELD_SEPARATOR}false\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args()
    cmd_accounts(args)

    captured = capsys.readouterr()
    assert "Mail Accounts:" in captured.out
    assert "iCloud" in captured.out
    assert "john@icloud.com" in captured.out
    assert "enabled" in captured.out
    assert "disabled" in captured.out


def test_cmd_accounts_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_accounts --json returns JSON array of accounts."""
    from my_cli.commands.mail.accounts import cmd_accounts

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}John Doe{FIELD_SEPARATOR}john@icloud.com{FIELD_SEPARATOR}true\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args(json=True)
    cmd_accounts(args)

    captured = capsys.readouterr()
    assert '"name": "iCloud"' in captured.out
    assert '"email": "john@icloud.com"' in captured.out
    assert '"enabled": true' in captured.out


def test_cmd_accounts_empty(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_accounts handles no accounts found."""
    from my_cli.commands.mail.accounts import cmd_accounts

    mock_run = Mock(return_value="")
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args()
    cmd_accounts(args)

    captured = capsys.readouterr()
    assert "No mail accounts found" in captured.out


def test_cmd_accounts_applescript_content(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_accounts sends AppleScript that reads account properties."""
    from my_cli.commands.mail.accounts import cmd_accounts

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}John Doe{FIELD_SEPARATOR}john@icloud.com{FIELD_SEPARATOR}true\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args()
    cmd_accounts(args)

    script_sent = mock_run.call_args[0][0]
    assert "every account" in script_sent
    assert "user name of acct" in script_sent
    assert "enabled of acct" in script_sent


# ---------------------------------------------------------------------------
# cmd_mailboxes (accounts.py)
# ---------------------------------------------------------------------------

def test_cmd_mailboxes_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mailboxes lists all mailboxes across all accounts."""
    from my_cli.commands.mail.accounts import cmd_mailboxes

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}3\n"
        f"iCloud{FIELD_SEPARATOR}Sent{FIELD_SEPARATOR}0\n"
        f"Work{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}1\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)
    # Patch resolve_account to return None so the all-accounts code path is taken
    monkeypatch.setattr("my_cli.commands.mail.accounts.resolve_account", lambda x: None)

    args = mock_args(account=None)
    cmd_mailboxes(args)

    captured = capsys.readouterr()
    assert "All Mailboxes:" in captured.out
    assert "INBOX" in captured.out
    assert "(3 unread)" in captured.out
    assert "[iCloud]" in captured.out


def test_cmd_mailboxes_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mailboxes --json returns JSON array of mailboxes."""
    from my_cli.commands.mail.accounts import cmd_mailboxes

    mock_run = Mock(return_value=(
        f"iCloud{FIELD_SEPARATOR}INBOX{FIELD_SEPARATOR}5\n"
        f"iCloud{FIELD_SEPARATOR}Sent{FIELD_SEPARATOR}0\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)
    # Patch resolve_account to return None so the all-accounts code path is taken
    monkeypatch.setattr("my_cli.commands.mail.accounts.resolve_account", lambda x: None)

    args = mock_args(account=None, json=True)
    cmd_mailboxes(args)

    captured = capsys.readouterr()
    assert '"account": "iCloud"' in captured.out
    assert '"name": "INBOX"' in captured.out
    assert '"unread": 5' in captured.out


def test_cmd_mailboxes_account_filter(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mailboxes -a scopes to a single account."""
    from my_cli.commands.mail.accounts import cmd_mailboxes

    mock_run = Mock(return_value=(
        f"INBOX{FIELD_SEPARATOR}2\n"
        f"Sent Messages{FIELD_SEPARATOR}0\n"
        f"Junk{FIELD_SEPARATOR}0\n"
    ))
    monkeypatch.setattr("my_cli.commands.mail.accounts.run", mock_run)

    args = mock_args(account="iCloud")
    cmd_mailboxes(args)

    captured = capsys.readouterr()
    assert "Mailboxes in iCloud:" in captured.out
    assert "INBOX" in captured.out
    assert "(2 unread)" in captured.out
    # Verify the script scopes to a single account
    script_sent = mock_run.call_args[0][0]
    assert 'account "iCloud"' in script_sent
    assert "every account" not in script_sent


# ---------------------------------------------------------------------------
# cmd_mark_unread (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_mark_unread_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mark_unread marks a message as unread."""
    from my_cli.commands.mail.actions import cmd_mark_unread

    mock_run = Mock(return_value="Important Message")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=456)
    cmd_mark_unread(args)

    captured = capsys.readouterr()
    assert "marked as unread" in captured.out
    assert "Important Message" in captured.out


def test_cmd_mark_unread_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mark_unread --json returns JSON with status=unread."""
    from my_cli.commands.mail.actions import cmd_mark_unread

    mock_run = Mock(return_value="Important Message")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=456, json=True)
    cmd_mark_unread(args)

    captured = capsys.readouterr()
    assert '"id": 456' in captured.out
    assert '"status": "unread"' in captured.out
    assert '"subject": "Important Message"' in captured.out


def test_cmd_mark_unread_applescript_sets_read_false(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_mark_unread AppleScript sets read status to false."""
    from my_cli.commands.mail.actions import cmd_mark_unread

    mock_run = Mock(return_value="Important Message")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=456)
    cmd_mark_unread(args)

    script_sent = mock_run.call_args[0][0]
    assert "read status" in script_sent
    assert "false" in script_sent


# ---------------------------------------------------------------------------
# cmd_unflag (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_unflag_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_unflag removes flag from a message."""
    from my_cli.commands.mail.actions import cmd_unflag

    mock_run = Mock(return_value="Flagged Item")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=789)
    cmd_unflag(args)

    captured = capsys.readouterr()
    assert "unflagged" in captured.out
    assert "Flagged Item" in captured.out


def test_cmd_unflag_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_unflag --json returns JSON with status=unflagged."""
    from my_cli.commands.mail.actions import cmd_unflag

    mock_run = Mock(return_value="Flagged Item")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=789, json=True)
    cmd_unflag(args)

    captured = capsys.readouterr()
    assert '"id": 789' in captured.out
    assert '"status": "unflagged"' in captured.out
    assert '"subject": "Flagged Item"' in captured.out


def test_cmd_unflag_applescript_sets_flagged_false(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_unflag AppleScript sets flagged status to false."""
    from my_cli.commands.mail.actions import cmd_unflag

    mock_run = Mock(return_value="Flagged Item")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=789)
    cmd_unflag(args)

    script_sent = mock_run.call_args[0][0]
    assert "flagged status" in script_sent
    assert "false" in script_sent


# ---------------------------------------------------------------------------
# cmd_move (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_move_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_move moves a message between mailboxes."""
    from my_cli.commands.mail.actions import cmd_move

    mock_run = Mock(return_value="Project Proposal")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=321, account="iCloud", from_mailbox="INBOX", to_mailbox="Archive")
    cmd_move(args)

    captured = capsys.readouterr()
    assert "Project Proposal" in captured.out
    assert "moved from" in captured.out
    assert "INBOX" in captured.out
    assert "Archive" in captured.out


def test_cmd_move_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_move --json returns JSON with source and destination."""
    from my_cli.commands.mail.actions import cmd_move

    mock_run = Mock(return_value="Project Proposal")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=321, account="iCloud", from_mailbox="INBOX", to_mailbox="Archive", json=True)
    cmd_move(args)

    captured = capsys.readouterr()
    assert '"id": 321' in captured.out
    assert '"subject": "Project Proposal"' in captured.out
    assert '"from": "INBOX"' in captured.out
    assert '"to": "Archive"' in captured.out


def test_cmd_move_applescript_uses_mailboxes(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_move AppleScript references source and destination mailboxes."""
    from my_cli.commands.mail.actions import cmd_move

    mock_run = Mock(return_value="Project Proposal")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=321, account="iCloud", from_mailbox="INBOX", to_mailbox="Archive")
    cmd_move(args)

    script_sent = mock_run.call_args[0][0]
    assert "INBOX" in script_sent
    assert "Archive" in script_sent
    assert "move theMsg to destMb" in script_sent


# ---------------------------------------------------------------------------
# cmd_junk (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_junk_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_junk marks a message as junk."""
    from my_cli.commands.mail.actions import cmd_junk

    mock_run = Mock(return_value="Suspicious Newsletter")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=555)
    cmd_junk(args)

    captured = capsys.readouterr()
    assert "marked as junk" in captured.out
    assert "Suspicious Newsletter" in captured.out


def test_cmd_junk_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_junk --json returns JSON with status=junk."""
    from my_cli.commands.mail.actions import cmd_junk

    mock_run = Mock(return_value="Suspicious Newsletter")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=555, json=True)
    cmd_junk(args)

    captured = capsys.readouterr()
    assert '"id": 555' in captured.out
    assert '"status": "junk"' in captured.out
    assert '"subject": "Suspicious Newsletter"' in captured.out


def test_cmd_junk_applescript_sets_junk_true(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_junk AppleScript sets junk mail status to true."""
    from my_cli.commands.mail.actions import cmd_junk

    mock_run = Mock(return_value="Suspicious Newsletter")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=555)
    cmd_junk(args)

    script_sent = mock_run.call_args[0][0]
    assert "junk mail status" in script_sent
    assert "true" in script_sent


# ---------------------------------------------------------------------------
# cmd_not_junk (actions.py)
# ---------------------------------------------------------------------------

def test_cmd_not_junk_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_not_junk marks a message as not junk and moves to INBOX."""
    from my_cli.commands.mail.actions import cmd_not_junk

    mock_run = Mock(return_value="Legitimate Newsletter")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=666, account="iCloud", mailbox=None)
    cmd_not_junk(args)

    captured = capsys.readouterr()
    assert "marked as not junk" in captured.out
    assert "moved to INBOX" in captured.out
    assert "Legitimate Newsletter" in captured.out


def test_cmd_not_junk_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_not_junk --json returns JSON with status=not_junk."""
    from my_cli.commands.mail.actions import cmd_not_junk

    mock_run = Mock(return_value="Legitimate Newsletter")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=666, account="iCloud", mailbox=None, json=True)
    cmd_not_junk(args)

    captured = capsys.readouterr()
    assert '"id": 666' in captured.out
    assert '"status": "not_junk"' in captured.out
    assert '"moved_to": "INBOX"' in captured.out


def test_cmd_not_junk_applescript_moves_to_inbox(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_not_junk AppleScript clears junk status and moves to INBOX."""
    from my_cli.commands.mail.actions import cmd_not_junk

    mock_run = Mock(return_value="Legitimate Newsletter")
    monkeypatch.setattr("my_cli.commands.mail.actions.run", mock_run)

    args = mock_args(id=666, account="iCloud", mailbox=None)
    cmd_not_junk(args)

    script_sent = mock_run.call_args[0][0]
    assert "junk mail status" in script_sent
    assert "false" in script_sent
    assert "move theMsg to inboxMb" in script_sent


# ---------------------------------------------------------------------------
# cmd_check (system.py)
# ---------------------------------------------------------------------------

def test_cmd_check_basic(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_check triggers a mail fetch and reports success."""
    from my_cli.commands.mail.system import cmd_check

    mock_run = Mock(return_value="ok")
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args()
    cmd_check(args)

    captured = capsys.readouterr()
    assert "Mail check triggered." in captured.out


def test_cmd_check_json(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_check --json returns JSON with status=checked."""
    from my_cli.commands.mail.system import cmd_check

    mock_run = Mock(return_value="ok")
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args(json=True)
    cmd_check(args)

    captured = capsys.readouterr()
    assert '"status": "checked"' in captured.out


def test_cmd_check_applescript_calls_check_for_new_mail(monkeypatch, mock_args, capsys):
    """Smoke test: cmd_check AppleScript invokes 'check for new mail'."""
    from my_cli.commands.mail.system import cmd_check

    mock_run = Mock(return_value="ok")
    monkeypatch.setattr("my_cli.commands.mail.system.run", mock_run)

    args = mock_args()
    cmd_check(args)

    script_sent = mock_run.call_args[0][0]
    assert "check for new mail" in script_sent
