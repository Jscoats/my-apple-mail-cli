"""Deadline scan command: scan unread email subjects for time-sensitive keywords."""

from __future__ import annotations

from datetime import datetime, timedelta

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    FIELD_SEPARATOR,
    resolve_account,
    save_message_aliases,
)
from mxctl.util.applescript import escape, run
from mxctl.util.dates import to_applescript_date
from mxctl.util.formatting import format_output, format_short_date, format_table, truncate
from mxctl.util.mail_helpers import extract_display_name, parse_message_line

# ---------------------------------------------------------------------------
# Keyword tables — order matters within each tier (first match wins)
# ---------------------------------------------------------------------------

_HIGH_KEYWORDS: list[str] = [
    "exam",
    "suspended",
    "overdue",
    "urgent",
    "action required",
    "final notice",
]

_MEDIUM_KEYWORDS: list[str] = [
    "due",
    "deadline",
    "expires",
    "payment",
    "last chance",
]

_LOW_KEYWORDS: list[str] = [
    "reminder",
    "expiring",
    "renew",
    "upcoming",
]

# Ordered list of (keyword, base_priority) for linear scan
_KEYWORD_TABLE: list[tuple[str, str]] = (
    [(kw, "HIGH") for kw in _HIGH_KEYWORDS] + [(kw, "MEDIUM") for kw in _MEDIUM_KEYWORDS] + [(kw, "LOW") for kw in _LOW_KEYWORDS]
)

_PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Column widths: #, ID, Subject, From, Date, Urgency, Keyword
_COL_WIDTHS = [3, 7, 30, 20, 6, 8, 21]

# Cap per-mailbox to keep AppleScript from timing out
_MAILBOX_CAP = 50


# ---------------------------------------------------------------------------
# Keyword matching helpers
# ---------------------------------------------------------------------------


def _match_keyword(subject: str) -> tuple[str, str] | None:
    """Return (keyword, base_priority) for the first match in subject, or None."""
    lower = subject.lower()
    for kw, priority in _KEYWORD_TABLE:
        if kw in lower:
            return kw, priority
    return None


def _boost_priority(priority: str, received_date_str: str, now: datetime) -> str:
    """Boost priority by one level if the message was received within 48 hours."""
    try:
        # Try the AppleScript date formats that format_short_date knows about
        for fmt in [
            "%A, %B %d, %Y at %I:%M:%S %p",
            "%B %d, %Y at %I:%M:%S %p",
            "%a %b %d %Y %H:%M:%S",
            "%a, %d %b %Y %H:%M:%S %z",
        ]:
            try:
                dt = datetime.strptime(received_date_str.strip(), fmt)
                # strptime produces a naive datetime; compare against naive now
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                break
            except ValueError:
                continue
        else:
            return priority  # could not parse — no boost
    except Exception:
        return priority

    if (now - dt) <= timedelta(hours=48):
        if priority == "LOW":
            return "MEDIUM"
        if priority == "MEDIUM":
            return "HIGH"
    return priority


# ---------------------------------------------------------------------------
# AppleScript builder
# ---------------------------------------------------------------------------


def _build_scan_script(
    account: str | None,
    unread_only: bool,
    since_as: str,
    cap: int,
) -> str:
    """Return AppleScript that fetches messages for deadline scanning.

    Output rows: acctName|id|subject|sender|date_received
    """
    read_filter = "read status is false and " if unread_only else ""
    date_filter = f'date received >= date "{since_as}"'
    whose_clause = f"whose {read_filter}{date_filter}"

    msg_row = (
        f'set output to output & acctName & "{FIELD_SEPARATOR}"'
        f' & (id of m) & "{FIELD_SEPARATOR}"'
        f' & (subject of m) & "{FIELD_SEPARATOR}"'
        f' & (sender of m) & "{FIELD_SEPARATOR}"'
        f" & (date received of m) & linefeed"
    )

    if account:
        acct_escaped = escape(account)
        return f"""
        tell application "Mail"
            set output to ""
            set acct to account "{acct_escaped}"
            set acctName to name of acct
            if enabled of acct then
                repeat with mb in (mailboxes of acct)
                    try
                        set msgs to (every message of mb {whose_clause})
                        set msgCount to count of msgs
                        set mbCap to {cap}
                        if msgCount < mbCap then set mbCap to msgCount
                        repeat with i from 1 to mbCap
                            set m to item i of msgs
                            {msg_row}
                        end repeat
                    end try
                end repeat
            end if
            return output
        end tell
        """

    # All enabled accounts
    return f"""
    tell application "Mail"
        set output to ""
        repeat with acct in (every account)
            if enabled of acct then
                set acctName to name of acct
                repeat with mb in (mailboxes of acct)
                    try
                        set msgs to (every message of mb {whose_clause})
                        set msgCount to count of msgs
                        set mbCap to {cap}
                        if msgCount < mbCap then set mbCap to msgCount
                        repeat with i from 1 to mbCap
                            set m to item i of msgs
                            {msg_row}
                        end repeat
                    end try
                end repeat
            end if
        end repeat
        return output
    end tell
    """


# ---------------------------------------------------------------------------
# Core scan function (exported for use by `brief` and other callers)
# ---------------------------------------------------------------------------


def scan_deadlines(
    account: str | None = None,
    unread_only: bool = True,
    days: int = 14,
) -> list[dict]:
    """Scan mailboxes for messages with deadline/time-sensitive subjects.

    Args:
        account:    Limit scan to a specific account name. None = all accounts.
        unread_only: When True (default), only unread messages are scanned.
        days:       Look-back window in days (default: 14).

    Returns:
        List of match dicts sorted by urgency (HIGH → MEDIUM → LOW), each with:
            id, subject, sender, date, account, keyword, urgency
    """
    since_dt = datetime.now() - timedelta(days=days)
    since_as = to_applescript_date(since_dt)

    script = _build_scan_script(account, unread_only, since_as, _MAILBOX_CAP)
    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)

    if not result.strip():
        return []

    _fields = ["account", "id", "subject", "sender", "date"]
    now = datetime.now()
    seen_ids: set[int] = set()
    matches: list[dict] = []

    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        msg = parse_message_line(line, _fields, FIELD_SEPARATOR)
        if msg is None:
            continue

        msg_id = msg["id"]
        # De-duplicate — same message can appear in multiple mailboxes
        if msg_id in seen_ids:
            continue
        seen_ids.add(msg_id)

        hit = _match_keyword(msg["subject"])
        if hit is None:
            continue

        keyword, base_priority = hit
        urgency = _boost_priority(base_priority, str(msg["date"]), now)

        matches.append(
            {
                "id": msg_id,
                "subject": msg["subject"],
                "sender": msg["sender"],
                "date": msg["date"],
                "account": msg["account"],
                "keyword": keyword,
                "urgency": urgency,
            }
        )

    # Sort: HIGH first, then MEDIUM, then LOW
    matches.sort(key=lambda m: _PRIORITY_ORDER.get(m["urgency"], 99))
    return matches


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def cmd_deadline_scan(args) -> None:
    """Scan unread messages across all accounts for deadline/time-sensitive subjects."""
    account = resolve_account(getattr(args, "account", None))
    # Use only the explicitly-passed -a flag (like process-inbox does) so that
    # the default "all accounts" path isn't accidentally overridden by config.
    explicit_account = getattr(args, "account", None)
    if not explicit_account:
        account = None
    unread_only = not getattr(args, "all", False)
    days = getattr(args, "days", 14)

    matches = scan_deadlines(account=account, unread_only=unread_only, days=days)

    if not matches:
        scope = f" in {account}" if account else " across all accounts"
        filter_note = " (unread only)" if unread_only else ""
        format_output(args, f"Deadline Scan — no time-sensitive messages found{scope}{filter_note}.")
        return

    save_message_aliases([m["id"] for m in matches])
    for i, m in enumerate(matches, 1):
        m["alias"] = i

    use_json = getattr(args, "json", False)
    if use_json:
        format_output(args, "", json_data=matches)
        return

    header = f"Deadline Scan — {len(matches)} item{'s' if len(matches) != 1 else ''} found\n"
    headers = ["#", "ID", "Subject", "From", "Date", "Urgency", "Keyword"]
    rows = [
        [
            str(m["alias"]),
            str(m["id"]),
            m["subject"],
            truncate(extract_display_name(m["sender"]) or m["sender"], 20),
            format_short_date(str(m["date"])),
            m["urgency"],
            m["keyword"],
        ]
        for m in matches
    ]
    table = format_table(headers, rows, _COL_WIDTHS)
    format_output(args, header + table, json_data=matches)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register the deadline-scan subcommand."""
    p = subparsers.add_parser(
        "deadline-scan",
        help="Scan unread email subjects for deadline/time-sensitive keywords",
    )
    p.add_argument("-a", "--account", help="Limit to specific account (default: all)")
    p.add_argument("--all", action="store_true", help="Include read messages (default: unread only)")
    p.add_argument("--days", type=int, default=14, help="Look-back window in days (default: 14)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_deadline_scan)
