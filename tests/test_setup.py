"""Tests for the mxctl init setup wizard command."""

import json
import os
from argparse import Namespace
from unittest.mock import Mock

from mxctl.config import FIELD_SEPARATOR

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account_line(name, email, enabled=True):
    enabled_str = "true" if enabled else "false"
    return f"{name}{FIELD_SEPARATOR}{email}{FIELD_SEPARATOR}{enabled_str}"


# ---------------------------------------------------------------------------
# test_init_no_accounts
# ---------------------------------------------------------------------------

def test_init_no_accounts(monkeypatch, mock_args, capsys, tmp_path):
    """When run() returns empty, print an error and return early."""
    from mxctl.commands.mail.setup import cmd_init

    # Point config file at a path that genuinely does not exist
    config_dir = str(tmp_path / "cfg")
    config_file = str(tmp_path / "cfg" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    mock_run = Mock(return_value="")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "No mail accounts found" in captured.out


# ---------------------------------------------------------------------------
# test_init_single_account_autoselect
# ---------------------------------------------------------------------------

def test_init_single_account_autoselect(monkeypatch, mock_args, capsys, tmp_path):
    """One enabled account: auto-select it and write config."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # config_file genuinely does not exist (fresh tmp_path) — no patch needed
    # Skip Todoist token
    monkeypatch.setattr("builtins.input", lambda _: "")

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Auto-selected" in captured.out
    assert "iCloud" in captured.out

    assert os.path.isfile(config_file)
    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "iCloud"


# ---------------------------------------------------------------------------
# test_init_multiple_accounts
# ---------------------------------------------------------------------------

def test_init_multiple_accounts(monkeypatch, mock_args, capsys, tmp_path):
    """Multiple accounts: user picks one by number, config is written."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # config_file genuinely does not exist — no patch needed

    # User picks account 2 (Gmail), skips Gmail prompt, skips Todoist token
    inputs = iter(["2", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    assert os.path.isfile(config_file)
    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "Gmail"


# ---------------------------------------------------------------------------
# test_init_existing_config
# ---------------------------------------------------------------------------

def test_init_existing_config(monkeypatch, mock_args, capsys, tmp_path):
    """Existing config: user says 'y' to reconfigure, wizard runs."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    os.makedirs(config_dir, exist_ok=True)

    # Write an existing config so os.path.isfile returns True for real
    existing = {"mail": {"default_account": "OldAccount"}}
    with open(config_file, "w") as f:
        json.dump(existing, f)

    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)
    monkeypatch.setattr("mxctl.commands.mail.setup.get_config", lambda: existing)

    # "y" to reconfigure, skip Gmail prompt ("n"), skip Todoist token
    inputs = iter(["y", "n", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Auto-selected" in captured.out

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "iCloud"


# ---------------------------------------------------------------------------
# test_init_json_output
# ---------------------------------------------------------------------------

def test_init_json_output(monkeypatch, mock_args, capsys, tmp_path):
    """--json flag outputs the written config as JSON."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)
    # config_file genuinely does not exist — no patch needed
    monkeypatch.setattr("builtins.input", lambda _: "")

    args = mock_args(json=True)
    cmd_init(args)

    captured = capsys.readouterr()
    assert '"default_account"' in captured.out
    assert "iCloud" in captured.out


# ---------------------------------------------------------------------------
# test_init_gmail_accounts_saved
# ---------------------------------------------------------------------------

def test_init_gmail_accounts_saved(monkeypatch, mock_args, capsys, tmp_path):
    """Gmail accounts selected during init are saved to config."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("ASU Gmail", "me@asu.edu", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # Pick account 1, mark account 2 as Gmail, skip Todoist
    inputs = iter(["1", "2", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "iCloud"
    assert "ASU Gmail" in cfg["mail"]["gmail_accounts"]


# ---------------------------------------------------------------------------
# test_resolve_mailbox
# ---------------------------------------------------------------------------

def test_resolve_mailbox_gmail_translation(monkeypatch):
    """resolve_mailbox translates friendly names for Gmail accounts."""
    from mxctl.util.mail_helpers import resolve_mailbox

    monkeypatch.setattr(
        "mxctl.util.mail_helpers.get_gmail_accounts",
        lambda: ["ASU Gmail", "Personal Gmail"],
    )

    assert resolve_mailbox("ASU Gmail", "Spam") == "[Gmail]/Spam"
    assert resolve_mailbox("ASU Gmail", "Junk") == "[Gmail]/Spam"
    assert resolve_mailbox("ASU Gmail", "Trash") == "[Gmail]/Trash"
    assert resolve_mailbox("ASU Gmail", "Sent") == "[Gmail]/Sent Mail"
    assert resolve_mailbox("ASU Gmail", "Archive") == "[Gmail]/All Mail"
    assert resolve_mailbox("ASU Gmail", "INBOX") == "INBOX"
    assert resolve_mailbox("ASU Gmail", "[Gmail]/Spam") == "[Gmail]/Spam"


def test_resolve_mailbox_non_gmail_passthrough(monkeypatch):
    """resolve_mailbox does not translate names for non-Gmail accounts."""
    from mxctl.util.mail_helpers import resolve_mailbox

    monkeypatch.setattr(
        "mxctl.util.mail_helpers.get_gmail_accounts",
        lambda: ["ASU Gmail"],
    )

    assert resolve_mailbox("iCloud", "Trash") == "Trash"
    assert resolve_mailbox("iCloud", "Spam") == "Spam"
    assert resolve_mailbox("iCloud", "INBOX") == "INBOX"


# ---------------------------------------------------------------------------
# test_init_creates_config_dir
# ---------------------------------------------------------------------------

def test_init_creates_config_dir(monkeypatch, mock_args, capsys, tmp_path):
    """Config directory is created if it doesn't exist."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "new_config_dir")
    config_file = str(tmp_path / "new_config_dir" / "config.json")

    # Directory does NOT exist yet
    assert not os.path.isdir(config_dir)

    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)
    # config_file genuinely does not exist — no patch needed
    monkeypatch.setattr("builtins.input", lambda _: "")

    args = mock_args()
    cmd_init(args)

    # Directory and config file should now exist
    assert os.path.isdir(config_dir)
    assert os.path.isfile(config_file)


# ---------------------------------------------------------------------------
# _is_interactive()
# ---------------------------------------------------------------------------

def test_is_interactive_ci_env(monkeypatch):
    """CI env var forces _is_interactive() to return False."""
    from mxctl.commands.mail.setup import _is_interactive

    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("MY_CLI_NON_INTERACTIVE", raising=False)
    assert _is_interactive() is False


def test_is_interactive_non_interactive_env(monkeypatch):
    """MY_CLI_NON_INTERACTIVE env var forces _is_interactive() to return False."""
    from mxctl.commands.mail.setup import _is_interactive

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("MY_CLI_NON_INTERACTIVE", "1")
    assert _is_interactive() is False


# ---------------------------------------------------------------------------
# Existing config: user declines reconfigure
# ---------------------------------------------------------------------------

def test_init_existing_config_decline(monkeypatch, mock_args, capsys, tmp_path):
    """Existing config, user says 'n' — keeps config and returns."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    os.makedirs(config_dir, exist_ok=True)

    existing = {"mail": {"default_account": "OldAccount"}}
    with open(config_file, "w") as f:
        json.dump(existing, f)

    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)
    monkeypatch.setattr("mxctl.commands.mail.setup.get_config", lambda: existing)

    # User says 'n' to reconfigure
    monkeypatch.setattr("builtins.input", lambda _: "n")

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Keeping existing configuration" in captured.out


def test_init_existing_config_decline_json(monkeypatch, mock_args, capsys, tmp_path):
    """Existing config, user declines, --json outputs existing config."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    os.makedirs(config_dir, exist_ok=True)

    existing = {"mail": {"default_account": "OldAccount"}}
    with open(config_file, "w") as f:
        json.dump(existing, f)

    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)
    monkeypatch.setattr("mxctl.commands.mail.setup.get_config", lambda: existing)

    monkeypatch.setattr("builtins.input", lambda _: "n")

    args = mock_args(json=True)
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Keeping existing configuration" in captured.out
    # JSON output is present with existing config data
    assert '"default_account"' in captured.out
    assert "OldAccount" in captured.out


def test_init_existing_config_keyboard_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """Existing config, KeyboardInterrupt at reconfigure prompt — cancels."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    os.makedirs(config_dir, exist_ok=True)

    existing = {"mail": {"default_account": "OldAccount"}}
    with open(config_file, "w") as f:
        json.dump(existing, f)

    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)
    monkeypatch.setattr("mxctl.commands.mail.setup.get_config", lambda: existing)

    def raise_interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Setup cancelled" in captured.out


def test_init_existing_config_eof(monkeypatch, mock_args, capsys, tmp_path):
    """Existing config, EOFError at reconfigure prompt — defaults to 'n'."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    os.makedirs(config_dir, exist_ok=True)

    existing = {"mail": {"default_account": "OldAccount"}}
    with open(config_file, "w") as f:
        json.dump(existing, f)

    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)
    monkeypatch.setattr("mxctl.commands.mail.setup.get_config", lambda: existing)

    def raise_eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Keeping existing configuration" in captured.out


# ---------------------------------------------------------------------------
# No enabled accounts found
# ---------------------------------------------------------------------------

def test_init_no_enabled_accounts(monkeypatch, mock_args, capsys, tmp_path):
    """All accounts disabled — prints error."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    line = _make_account_line("Disabled", "me@example.com", enabled=False)
    mock_run = Mock(return_value=line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "No enabled mail accounts found" in captured.out


# ---------------------------------------------------------------------------
# Blank lines / empty parse lines skipped
# ---------------------------------------------------------------------------

def test_init_blank_lines_skipped(monkeypatch, mock_args, capsys, tmp_path):
    """Blank lines in AppleScript output are skipped during parsing."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    # Put blank line BETWEEN two valid accounts so strip() won't remove it
    acct1 = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    acct2 = _make_account_line("Gmail", "me@gmail.com", enabled=True)
    lines = f"{acct1}\n\n{acct2}\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # Pick account 1, skip gmail, skip todoist
    inputs = iter(["1", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    # Both accounts were parsed (blank line skipped)
    assert "Available mail accounts" in captured.out


# ---------------------------------------------------------------------------
# Multi-account: non-interactive fallback paths
# ---------------------------------------------------------------------------

def test_init_multi_account_invalid_then_valid(monkeypatch, mock_args, capsys, tmp_path):
    """Invalid selection number, then valid — exercises the retry loop."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # Invalid "99" first, then valid "1", then skip gmail, skip todoist
    inputs = iter(["99", "1", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Please enter a number between 1 and 2" in captured.out

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "iCloud"


def test_init_multi_account_keyboard_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """KeyboardInterrupt during account selection — cancels."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    def raise_interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Setup cancelled" in captured.out


def test_init_multi_account_eof_defaults_to_1(monkeypatch, mock_args, capsys, tmp_path):
    """EOFError during account selection — defaults to account 1."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # First input: EOFError -> defaults to "1", then gmail skip, todoist skip
    call_count = 0

    def eof_then_empty(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise EOFError
        return ""

    monkeypatch.setattr("builtins.input", eof_then_empty)

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "iCloud"


# ---------------------------------------------------------------------------
# Gmail step: single account says 'y'
# ---------------------------------------------------------------------------

def test_init_single_account_gmail_yes(monkeypatch, mock_args, capsys, tmp_path):
    """Single account, user says 'y' to Gmail prompt."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("Gmail", "me@gmail.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # Gmail 'y', then todoist skip
    inputs = iter(["y", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["gmail_accounts"] == ["Gmail"]


def test_init_single_account_gmail_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """Single account, KeyboardInterrupt at Gmail prompt — defaults to 'n'."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    call_count = 0

    def interrupt_then_empty(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise KeyboardInterrupt
        return ""

    monkeypatch.setattr("builtins.input", interrupt_then_empty)

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert "gmail_accounts" not in cfg.get("mail", {})


# ---------------------------------------------------------------------------
# Gmail step: multi-account non-interactive fallback
# ---------------------------------------------------------------------------

def test_init_multi_account_gmail_selection(monkeypatch, mock_args, capsys, tmp_path):
    """Multi-account, non-interactive: user enters gmail account numbers."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # Pick account 1, mark account 2 as Gmail, skip todoist
    inputs = iter(["1", "2", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert "Gmail" in cfg["mail"]["gmail_accounts"]


def test_init_multi_account_gmail_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """Multi-account, KeyboardInterrupt/EOFError at gmail prompt — defaults to empty."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    call_count = 0

    def inputs(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "1"  # account selection
        if call_count == 2:
            raise EOFError  # gmail prompt
        return ""  # todoist skip

    monkeypatch.setattr("builtins.input", inputs)

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert "gmail_accounts" not in cfg.get("mail", {})


# ---------------------------------------------------------------------------
# Todoist token: valid format, invalid format, interrupt, eof
# ---------------------------------------------------------------------------

def test_init_todoist_valid_token(monkeypatch, mock_args, capsys, tmp_path):
    """Valid 40-hex-char Todoist token is saved without warning."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    valid_token = "a" * 40
    inputs = iter(["n", valid_token])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["todoist_api_token"] == valid_token

    captured = capsys.readouterr()
    assert "Todoist: connected" in captured.out
    assert "Warning" not in captured.out


def test_init_todoist_invalid_token(monkeypatch, mock_args, capsys, tmp_path):
    """Non-hex token is saved but prints a warning."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    invalid_token = "not-a-valid-token"
    inputs = iter(["n", invalid_token])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "expected format" in captured.out

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["todoist_api_token"] == invalid_token


def test_init_todoist_keyboard_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """KeyboardInterrupt at Todoist prompt — cancels setup entirely."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    call_count = 0

    def inputs(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "n"  # gmail prompt
        raise KeyboardInterrupt  # todoist prompt

    monkeypatch.setattr("builtins.input", inputs)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Setup cancelled" in captured.out
    # Config should NOT have been written
    assert not os.path.isfile(config_file)


def test_init_todoist_eof(monkeypatch, mock_args, capsys, tmp_path):
    """EOFError at Todoist prompt — skips token, saves config."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    call_count = 0

    def inputs(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "n"  # gmail prompt
        raise EOFError  # todoist prompt

    monkeypatch.setattr("builtins.input", inputs)

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert "todoist_api_token" not in cfg


# ---------------------------------------------------------------------------
# JSON output with Todoist token is redacted
# ---------------------------------------------------------------------------

def test_init_json_todoist_redacted(monkeypatch, mock_args, capsys, tmp_path):
    """--json output redacts the Todoist token."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    acct_line = _make_account_line("iCloud", "me@icloud.com", enabled=True)
    mock_run = Mock(return_value=acct_line + "\n")
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    valid_token = "a" * 40
    inputs = iter(["n", valid_token])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args(json=True)
    cmd_init(args)

    captured = capsys.readouterr()
    # JSON output should have redacted token, not the real one
    assert "****" in captured.out
    assert valid_token not in captured.out


# ---------------------------------------------------------------------------
# Summary parts: Gmail count plural
# ---------------------------------------------------------------------------

def test_init_summary_gmail_plural(monkeypatch, mock_args, capsys, tmp_path):
    """Gmail count in summary pluralizes correctly."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail1", "a@gmail.com", enabled=True),
        _make_account_line("Gmail2", "b@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    # Pick account 1, mark both 2 and 3 as Gmail, skip todoist
    inputs = iter(["1", "2,3", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Gmail: 2 accounts" in captured.out


# ---------------------------------------------------------------------------
# register() wires cmd_init to 'init' subcommand
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Interactive paths: _is_interactive() True, mock _radio_select/_checkbox_select
# ---------------------------------------------------------------------------

def test_init_interactive_multi_account_radio(monkeypatch, mock_args, capsys, tmp_path):
    """Interactive mode: _radio_select picks account, _checkbox_select picks Gmail."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    monkeypatch.setattr("mxctl.commands.mail.setup._is_interactive", lambda: True)
    monkeypatch.setattr("mxctl.commands.mail.setup._radio_select", lambda prompt, opts: 0)
    monkeypatch.setattr("mxctl.commands.mail.setup._checkbox_select", lambda prompt, opts: [1])

    # Todoist prompt
    monkeypatch.setattr("builtins.input", lambda _: "")

    args = mock_args()
    cmd_init(args)

    with open(config_file) as f:
        cfg = json.load(f)
    assert cfg["mail"]["default_account"] == "iCloud"
    assert "Gmail" in cfg["mail"]["gmail_accounts"]


def test_init_interactive_radio_keyboard_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """Interactive mode: KeyboardInterrupt in _radio_select cancels."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    monkeypatch.setattr("mxctl.commands.mail.setup._is_interactive", lambda: True)

    def raise_interrupt(prompt, opts):
        raise KeyboardInterrupt

    monkeypatch.setattr("mxctl.commands.mail.setup._radio_select", raise_interrupt)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Setup cancelled" in captured.out


def test_init_interactive_checkbox_keyboard_interrupt(monkeypatch, mock_args, capsys, tmp_path):
    """Interactive mode: KeyboardInterrupt in _checkbox_select cancels."""
    from mxctl.commands.mail.setup import cmd_init

    config_dir = str(tmp_path / "config")
    config_file = str(tmp_path / "config" / "config.json")
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_DIR", config_dir)
    monkeypatch.setattr("mxctl.commands.mail.setup.CONFIG_FILE", config_file)

    lines = "\n".join([
        _make_account_line("iCloud", "me@icloud.com", enabled=True),
        _make_account_line("Gmail", "me@gmail.com", enabled=True),
    ]) + "\n"
    mock_run = Mock(return_value=lines)
    monkeypatch.setattr("mxctl.commands.mail.setup.run", mock_run)

    monkeypatch.setattr("mxctl.commands.mail.setup._is_interactive", lambda: True)
    monkeypatch.setattr("mxctl.commands.mail.setup._radio_select", lambda prompt, opts: 0)

    def raise_interrupt(prompt, opts):
        raise KeyboardInterrupt

    monkeypatch.setattr("mxctl.commands.mail.setup._checkbox_select", raise_interrupt)

    args = mock_args()
    cmd_init(args)

    captured = capsys.readouterr()
    assert "Setup cancelled" in captured.out


# ---------------------------------------------------------------------------
# _radio_select — raw terminal mode
# ---------------------------------------------------------------------------

def _mock_stdin(monkeypatch):
    """Mock sys.stdin.fileno() to return 0 (needed in pytest where stdin is a pseudofile)."""
    mock_stdin = Mock()
    mock_stdin.fileno.return_value = 0
    monkeypatch.setattr("sys.stdin", mock_stdin)


def test_radio_select_enter(monkeypatch):
    """_radio_select: pressing Enter on first option returns 0."""
    from mxctl.commands.mail.setup import _radio_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: b"\r")

    result = _radio_select("Pick one:", ["Alpha", "Beta"])
    assert result == 0


def test_radio_select_arrow_down_then_enter(monkeypatch):
    """_radio_select: arrow down then Enter selects second option."""
    from mxctl.commands.mail.setup import _radio_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    reads = iter([b"\x1b", b"[B", b"\r"])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _radio_select("Pick one:", ["Alpha", "Beta"])
    assert result == 1


def test_radio_select_arrow_up_wraps(monkeypatch):
    """_radio_select: arrow up from 0 wraps to last option."""
    from mxctl.commands.mail.setup import _radio_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    reads = iter([b"\x1b", b"[A", b" "])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _radio_select("Pick:", ["A", "B", "C"])
    assert result == 2  # wrapped from 0 to last (2)


def test_radio_select_space_selects(monkeypatch):
    """_radio_select: space selects current option."""
    from mxctl.commands.mail.setup import _radio_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: b" ")

    result = _radio_select("Pick:", ["Only"])
    assert result == 0


def test_radio_select_ctrl_c_raises(monkeypatch):
    """_radio_select: Ctrl+C raises KeyboardInterrupt."""
    import pytest

    from mxctl.commands.mail.setup import _radio_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: b"\x03")

    with pytest.raises(KeyboardInterrupt):
        _radio_select("Pick:", ["A", "B"])


# ---------------------------------------------------------------------------
# _checkbox_select — raw terminal mode
# ---------------------------------------------------------------------------

def test_checkbox_select_enter_none(monkeypatch):
    """_checkbox_select: Enter with no toggles returns empty list."""
    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: b"\r")

    result = _checkbox_select("Select:", ["A", "B"])
    assert result == []


def test_checkbox_select_toggle_and_enter(monkeypatch):
    """_checkbox_select: space toggles first item, then Enter."""
    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    reads = iter([b" ", b"\r"])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _checkbox_select("Select:", ["A", "B"])
    assert result == [0]


def test_checkbox_select_toggle_on_off(monkeypatch):
    """_checkbox_select: toggle on then off deselects."""
    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    reads = iter([b" ", b" ", b"\r"])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _checkbox_select("Select:", ["A", "B"])
    assert result == []


def test_checkbox_select_arrow_down_and_toggle(monkeypatch):
    """_checkbox_select: arrow down to second item, toggle, enter."""
    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    reads = iter([b"\x1b", b"[B", b" ", b"\n"])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _checkbox_select("Select:", ["A", "B", "C"])
    assert result == [1]


def test_checkbox_select_arrow_up_wraps(monkeypatch):
    """_checkbox_select: arrow up from 0 wraps to last."""
    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    reads = iter([b"\x1b", b"[A", b" ", b"\r"])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _checkbox_select("Select:", ["A", "B", "C"])
    assert result == [2]


def test_checkbox_select_ctrl_c_raises(monkeypatch):
    """_checkbox_select: Ctrl+C raises KeyboardInterrupt."""
    import pytest

    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: b"\x03")

    with pytest.raises(KeyboardInterrupt):
        _checkbox_select("Select:", ["A", "B"])


def test_checkbox_select_multiple_selected(monkeypatch):
    """_checkbox_select: toggle first and third, returns sorted."""
    from mxctl.commands.mail.setup import _checkbox_select

    _mock_stdin(monkeypatch)
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("mxctl.commands.mail.setup.termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("mxctl.commands.mail.setup.tty.setraw", lambda fd: None)

    # Toggle A (space), down, down, toggle C (space), enter
    reads = iter([b" ", b"\x1b", b"[B", b"\x1b", b"[B", b" ", b"\r"])
    monkeypatch.setattr("mxctl.commands.mail.setup.os.read", lambda fd, n: next(reads))

    result = _checkbox_select("Select:", ["A", "B", "C"])
    assert result == [0, 2]


# ---------------------------------------------------------------------------
# register() wires cmd_init to 'init' subcommand
# ---------------------------------------------------------------------------

def test_register(monkeypatch):
    """register() adds 'init' subcommand."""
    import argparse

    from mxctl.commands.mail.setup import register

    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command")
    register(subs)

    args = parser.parse_args(["init", "--json"])
    assert args.json is True
    assert hasattr(args, "func")
