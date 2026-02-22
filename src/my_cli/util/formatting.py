"""Output formatting helpers."""

from __future__ import annotations

import json
import sys
from typing import NoReturn


def truncate(s: str, max_length: int) -> str:
    """Truncate a string with ellipsis."""
    if not s or len(s) <= max_length:
        return s or ""
    return s[: max_length - 3] + "..."


def _convert_dates_with_keys(obj: object, key: str | None = None) -> object:
    """Recursively convert AppleScript dates to ISO 8601, using key context."""
    if isinstance(obj, dict):
        return {k: _convert_dates_with_keys(v, k) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_dates_with_keys(item, key) for item in obj]
    elif isinstance(obj, str) and key and "date" in key.lower():
        # Apply date conversion only for keys containing "date"
        # Import here to avoid circular dependency
        from my_cli.util.dates import parse_applescript_date

        return parse_applescript_date(obj)
    else:
        return obj


def output(text: str, *, json_data: object = None, use_json: bool = False) -> None:
    """Print text output, or JSON if --json was passed."""
    if use_json and json_data is not None:
        # Convert AppleScript dates to ISO 8601 before serializing
        converted_data = _convert_dates_with_keys(json_data)
        print(json.dumps(converted_data, indent=2, default=str))
    else:
        print(text)


def format_output(args: object, text: str, *, json_data: object = None) -> None:
    """Extract use_json from args and call output(). DRY wrapper for commands."""
    use_json = getattr(args, "json", False)
    output(text, json_data=json_data, use_json=use_json)


def die(msg: str, code: int = 1) -> NoReturn:
    """Print error and exit."""
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)
