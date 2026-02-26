"""AppleScript execution helpers."""

from __future__ import annotations

import os
import re
import subprocess
import sys

from mxctl.config import APPLESCRIPT_TIMEOUT_DEFAULT, STATE_FILE

_automation_warned: bool = False


def _warn_automation_once() -> None:
    """Print a one-time heads-up about macOS Automation permission if needed."""
    global _automation_warned
    if _automation_warned:
        return

    # Check if we've already shown the prompt in a previous session
    from mxctl.config import _save_json, get_state

    state = get_state()
    if state.get("automation_prompted"):
        _automation_warned = True
        return

    # Check terminal app name for a friendlier message
    terminal_app = os.environ.get("TERM_PROGRAM", "your terminal app")
    if terminal_app == "iTerm.app":
        terminal_app = "iTerm"
    elif terminal_app == "Apple_Terminal":
        terminal_app = "Terminal"

    print(
        "Note: macOS will ask for Automation permission to control Mail.app. If prompted, click Allow.",
        file=sys.stderr,
    )
    print(
        f"  If you see 'not authorized': System Settings → Privacy & Security → Automation → {terminal_app} → enable Mail.",
        file=sys.stderr,
    )

    # Mark as warned for this session and persist to state
    _automation_warned = True
    state["automation_prompted"] = True
    _save_json(STATE_FILE, state)


def validate_msg_id(value) -> int:
    """Validate that value is a positive integer suitable for use as a message ID.

    Supports short session aliases: if value matches a saved alias (e.g. "1"),
    resolves to the real message ID from the most recent listing command.

    Raises SystemExit via die() if the value is not a positive integer.
    Returns the integer value on success.
    """
    from mxctl.config import resolve_alias
    from mxctl.util.formatting import die

    # Reject floats explicitly — int(1.5) == 1 without error, which is misleading
    if isinstance(value, float):
        die(f"Invalid message ID '{value}': must be a positive integer.")

    # Try alias resolution first
    resolved = resolve_alias(value)
    if resolved is not None:
        return resolved

    # Fall through to real ID validation
    try:
        int_val = int(value)
    except (TypeError, ValueError):
        die(f"Invalid message ID '{value}': must be a positive integer.")
    if int_val <= 0:
        die(f"Invalid message ID '{value}': must be a positive integer.")
    return int_val


def escape(s: str | None) -> str:
    """Escape a string for safe use in AppleScript."""
    if s is None:
        return ""
    s = str(s).replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = re.sub(r"[\x00-\x1f]", "", s)
    return s


def sanitize_path(path: str) -> str:
    """Expand and resolve a file path."""
    return os.path.abspath(os.path.expanduser(path))


def run(script: str, timeout: int = APPLESCRIPT_TIMEOUT_DEFAULT) -> str:
    """Execute AppleScript and return stdout. Exits on error."""
    _warn_automation_once()
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        print("Error: osascript not found. This tool requires macOS.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(
            "Error: Mail operation timed out. Try reducing --limit or narrowing the date range.",
            file=sys.stderr,
        )
        sys.exit(1)

    if result.returncode != 0:
        err = result.stderr.strip()
        err_lower = err.lower().replace("\u2018", "'").replace("\u2019", "'")
        if "not authorized" in err_lower:
            msg = "Mail access denied. Grant access in System Settings > Privacy & Security > Automation."
        elif "application isn't running" in err_lower:
            msg = "Mail.app failed to launch. Try opening Mail.app manually and try again."
        elif "can't get account" in err_lower:
            msg = "Account not found. Run `mxctl accounts` to see available accounts."
        elif "can't get mailbox" in err_lower:
            msg = "Mailbox not found. Run `mxctl mailboxes` to see available mailboxes."
        elif "can't get message" in err_lower:
            msg = "Message not found — it may have been moved or deleted."
        else:
            msg = f"AppleScript error: {err}"
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)

    return result.stdout.strip()
