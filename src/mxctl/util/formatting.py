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


def format_short_date(date_str: str) -> str:
    """Convert an AppleScript date string to a short 'Mon DD' format.

    Examples:
        "Tuesday, January 14, 2026 at 2:30:00 PM" -> "Jan 14"
        "January 14, 2026 at 2:30:00 PM"          -> "Jan 14"
        "Mon Feb 14 2026 10:00:00"                 -> "Feb 14"
    Returns the original string (truncated to 8 chars) if parsing fails.
    """
    from datetime import datetime

    for fmt in [
        "%A, %B %d, %Y at %I:%M:%S %p",
        "%B %d, %Y at %I:%M:%S %p",
        "%a %b %d %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",
    ]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%b %d")
        except ValueError:
            continue
    # Fallback: return first 8 chars of original
    return date_str[:8]


def format_table(headers: list[str], rows: list[list[str]], col_widths: list[int]) -> str:
    """Build a Unicode box-drawing bordered table with row separators between every data row.

    Args:
        headers: Column header labels.
        rows:     Data rows; each inner list must have the same length as headers.
        col_widths: Maximum display width for each column (content is truncated to fit).

    Returns:
        A multi-line string containing the full bordered table.

    Box-drawing characters used:
        Top border:    ┌─┬┐
        Header sep:    ├─┼┤
        Row sep:       ├─┼┤
        Bottom border: └─┴┘
        Sides:         │
    """
    n = len(headers)
    # Clamp widths to at least the header length so headers always fit.
    widths = [max(col_widths[i], len(headers[i])) for i in range(n)]

    def _cell(text: str, width: int) -> str:
        text = truncate(str(text), width)
        return text.ljust(width)

    def _top_border() -> str:
        parts = ["─" * (w + 2) for w in widths]
        return "┌" + "┬".join(parts) + "┐"

    def _mid_sep() -> str:
        parts = ["─" * (w + 2) for w in widths]
        return "├" + "┼".join(parts) + "┤"

    def _bot_border() -> str:
        parts = ["─" * (w + 2) for w in widths]
        return "└" + "┴".join(parts) + "┘"

    def _row_line(cells: list[str]) -> str:
        parts = [f" {_cell(cells[i], widths[i])} " for i in range(n)]
        return "│" + "│".join(parts) + "│"

    lines = [_top_border(), _row_line(headers), _mid_sep()]
    for idx, row in enumerate(rows):
        lines.append(_row_line(row))
        if idx < len(rows) - 1:
            lines.append(_mid_sep())
    lines.append(_bot_border())
    return "\n".join(lines)


def _convert_dates_with_keys(obj: object, key: str | None = None) -> object:
    """Recursively convert AppleScript dates to ISO 8601, using key context."""
    if isinstance(obj, dict):
        return {k: _convert_dates_with_keys(v, k) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_dates_with_keys(item, key) for item in obj]
    elif isinstance(obj, str) and key and "date" in key.lower():
        # Apply date conversion only for keys containing "date"
        # Import here to avoid circular dependency
        from mxctl.util.dates import parse_applescript_date

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
