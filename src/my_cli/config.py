"""Configuration management for the `my` CLI.

Three-tier account resolution (most specific wins):
1. Explicit --account flag
2. Default in ~/.config/my/config.json -> {"mail": {"default_account": "iCloud"}}
3. Last-used account saved in ~/.config/my/state.json -> {"mail": {"last_account": "iCloud"}}

Migration note: Backward compatibility is maintained. Config lookups check the new
namespaced format first (e.g., config["mail"]["default_account"]), then fall back
to the legacy flat format (config["default_account"]) if the namespace key is missing.
This allows existing configs to continue working without modification.
"""

from __future__ import annotations

import json
import os
import fcntl
import time
from contextlib import contextmanager

from my_cli.util.formatting import die

CONFIG_DIR = os.path.expanduser("~/.config/my")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")
TEMPLATES_FILE = os.path.join(CONFIG_DIR, "mail-templates.json")
UNDO_LOG_FILE = os.path.join(CONFIG_DIR, "mail-undo.json")

DEFAULT_MESSAGE_LIMIT = 25
MAX_MESSAGE_LIMIT = 100
DEFAULT_BODY_LENGTH = 10000
DEFAULT_MAILBOX = "INBOX"

# Caps for various operations
MAX_MESSAGES_BATCH = 500
DEFAULT_DIGEST_LIMIT = 50
DEFAULT_TOP_SENDERS_LIMIT = 10
MAX_EXPORT_BULK_LIMIT = 100

# AppleScript timeout values (seconds)
APPLESCRIPT_TIMEOUT_SHORT = 15
APPLESCRIPT_TIMEOUT_DEFAULT = 30
APPLESCRIPT_TIMEOUT_LONG = 60
APPLESCRIPT_TIMEOUT_BATCH = 120

# Data separators for AppleScript field/record parsing
FIELD_SEPARATOR = "\x1F"
RECORD_SEPARATOR = "\x1eEND\x1e"

# Common patterns for identifying no-reply / automated senders
NOREPLY_PATTERNS = [
    "noreply", "no-reply", "notifications", "mailer-daemon", "donotreply",
    "updates@", "news@", "info@", "support@", "billing@",
]


def _ensure_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


@contextmanager
def file_lock(path: str):
    """Context manager for file-based locking with retry."""
    lock_path = path + ".lock"
    max_retries = 10
    retry_delay = 0.05  # 50ms

    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    for attempt in range(max_retries):
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield lock_file
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    try:
                        os.unlink(lock_path)
                    except OSError:
                        pass
            break
        except BlockingIOError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                die(f"Could not acquire file lock for {path} after {max_retries} attempts. Another process may be holding it.")


def _load_json(path: str) -> dict:
    if os.path.isfile(path):
        try:
            with file_lock(path):
                with open(path) as f:
                    content = f.read().strip()
                    if not content:  # Handle empty/truncated files
                        return {}
                    return json.loads(content)
        except json.JSONDecodeError:
            import sys
            print(f"Warning: {path} contains invalid JSON. Using defaults.", file=sys.stderr)
            return {}
        except IOError:
            return {}
    return {}


_SENSITIVE_FILES = {CONFIG_FILE, STATE_FILE, UNDO_LOG_FILE, TEMPLATES_FILE}


def _save_json(path: str, data: dict) -> None:
    _ensure_dir()
    with file_lock(path):
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        if path in _SENSITIVE_FILES:
            os.chmod(path, 0o600)


_config_warned: bool = False


def get_config() -> dict:
    global _config_warned
    if not _config_warned and not os.path.isfile(CONFIG_FILE):
        import sys
        print(
            "No config found. Run `my mail init` to set up your default account.",
            file=sys.stderr,
        )
        _config_warned = True
    return _load_json(CONFIG_FILE)


def get_state() -> dict:
    return _load_json(STATE_FILE)


def save_last_account(account: str) -> None:
    state = get_state()
    if "mail" not in state:
        state["mail"] = {}
    state["mail"]["last_account"] = account
    _save_json(STATE_FILE, state)


def resolve_account(explicit: str | None) -> str | None:
    """Resolve account using three-tier strategy. Returns None if nothing set."""
    if explicit:
        save_last_account(explicit)
        return explicit

    cfg = get_config()
    # Check namespaced key first, fall back to legacy flat key
    default_account = cfg.get("mail", {}).get("default_account") or cfg.get("default_account")
    if default_account:
        return default_account

    state = get_state()
    # Check namespaced key first, fall back to legacy flat key
    return state.get("mail", {}).get("last_account") or state.get("last_account")


def validate_limit(limit: int) -> int:
    """Clamp limit to [1, MAX_MESSAGE_LIMIT]."""
    return max(1, min(limit, MAX_MESSAGE_LIMIT))


def get_gmail_accounts() -> list[str]:
    """Return list of account names configured as Gmail accounts."""
    cfg = get_config()
    return cfg.get("mail", {}).get("gmail_accounts", [])
