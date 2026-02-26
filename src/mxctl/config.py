"""Configuration management for mxctl.

Three-tier account resolution (most specific wins):
1. Explicit --account flag
2. Default in ~/.config/mxctl/config.json -> {"mail": {"default_account": "iCloud"}}
3. Last-used account saved in ~/.config/mxctl/state.json -> {"mail": {"last_account": "iCloud"}}

Migration note: Backward compatibility is maintained. Config lookups check the new
namespaced format first (e.g., config["mail"]["default_account"]), then fall back
to the legacy flat format (config["default_account"]) if the namespace key is missing.
This allows existing configs to continue working without modification.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import time
from contextlib import contextmanager

from mxctl.util.formatting import die

CONFIG_DIR = os.path.expanduser("~/.config/mxctl")
_LEGACY_CONFIG_DIR = os.path.expanduser("~/.config/my")
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
FIELD_SEPARATOR = "\x1f"
RECORD_SEPARATOR = "\x1eEND\x1e"

# Common patterns for identifying no-reply / automated senders
NOREPLY_PATTERNS = [
    "noreply",
    "no-reply",
    "notifications",
    "mailer-daemon",
    "donotreply",
    "updates@",
    "news@",
    "info@",
    "support@",
    "billing@",
]

_migrated: bool = False


def _migrate_legacy_config() -> None:
    """One-time migration from ~/.config/my/ to ~/.config/mxctl/."""
    global _migrated
    if _migrated:
        return
    _migrated = True

    if os.path.isdir(CONFIG_DIR):
        return  # Already migrated or fresh install
    if not os.path.isdir(_LEGACY_CONFIG_DIR):
        return  # No legacy config to migrate

    import sys

    shutil.copytree(_LEGACY_CONFIG_DIR, CONFIG_DIR)
    print(
        f"Migrated config from {_LEGACY_CONFIG_DIR} to {CONFIG_DIR}",
        file=sys.stderr,
    )


def _ensure_dir() -> None:
    _migrate_legacy_config()
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
    _migrate_legacy_config()
    if os.path.isfile(path):
        try:
            with file_lock(path), open(path) as f:
                content = f.read().strip()
                if not content:  # Handle empty/truncated files
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            import sys

            print(f"Warning: {path} contains invalid JSON. Using defaults.", file=sys.stderr)
            return {}
        except OSError:
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


def get_config(required: bool = False, warn: bool = True) -> dict:
    global _config_warned
    if not os.path.isfile(CONFIG_FILE):
        _migrate_legacy_config()
    if not os.path.isfile(CONFIG_FILE):
        if required:
            die("No config found. Run `mxctl init` to set up your default account.")
        if warn and not _config_warned:
            import sys

            print(
                "No config found. Run `mxctl init` to set up your default account.",
                file=sys.stderr,
            )
            _config_warned = True
    return _load_json(CONFIG_FILE)


def get_state() -> dict:
    return _load_json(STATE_FILE)


def save_message_aliases(aliases: list[int]) -> None:
    """Save ordered list of message IDs as session aliases to state."""
    state = get_state()
    state.setdefault("mail", {})["aliases"] = {str(i + 1): mid for i, mid in enumerate(aliases)}
    _save_json(STATE_FILE, state)


def resolve_alias(value) -> int | None:
    """If value matches a saved alias number, resolve to real message ID."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    state = get_state()
    aliases = state.get("mail", {}).get("aliases", {})
    real_id = aliases.get(str(n))
    if real_id is not None:
        return int(real_id)
    return None


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

    cfg = get_config(required=False, warn=False)
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
    cfg = get_config(required=False, warn=False)
    return cfg.get("mail", {}).get("gmail_accounts", [])
