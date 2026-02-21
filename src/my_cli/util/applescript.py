"""AppleScript execution helpers."""

from __future__ import annotations

import os
import subprocess
import sys

APPLESCRIPT_TIMEOUT = 30


def escape(s: str) -> str:
    """Escape a string for safe use in AppleScript."""
    if s is None:
        return ""
    s = str(s).replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\0", "")
    return s


def sanitize_path(path: str) -> str:
    """Expand and resolve a file path."""
    return os.path.abspath(os.path.expanduser(path))


def run(script: str, timeout: int = APPLESCRIPT_TIMEOUT) -> str:
    """Execute AppleScript and return stdout. Exits on error."""
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
            msg = "Mail.app is not running. Please open Mail and try again."
        elif "can't get account" in err_lower:
            msg = f"Account not found. Run `my mail accounts` to see available accounts.\n{err}"
        elif "can't get mailbox" in err_lower:
            msg = f"Mailbox not found. Run `my mail mailboxes` to see available mailboxes.\n{err}"
        elif "can't get message" in err_lower:
            msg = f"Message not found — it may have been moved or deleted.\n{err}"
        else:
            msg = f"AppleScript error: {err}"
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)

    return result.stdout.strip()
