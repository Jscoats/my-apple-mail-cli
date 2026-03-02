"""Daily email brief: action-required, flagged, people, and notification count."""

from __future__ import annotations

from datetime import datetime

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    FIELD_SEPARATOR,
    NOREPLY_PATTERNS,
    save_message_aliases,
)
from mxctl.util.applescript import run
from mxctl.util.applescript_templates import inbox_iterator_all_accounts
from mxctl.util.formatting import format_output, format_short_date, format_table, truncate
from mxctl.util.mail_helpers import extract_display_name, extract_email, parse_message_line

# ---------------------------------------------------------------------------
# Deadline keywords (case-insensitive subject scan)
# ---------------------------------------------------------------------------

_ACTION_KEYWORDS = [
    "exam",
    "suspended",
    "overdue",
    "urgent",
    "action required",
    "final notice",
    "due",
    "deadline",
    "expires",
    "payment",
    "last chance",
    "reminder",
]

# ---------------------------------------------------------------------------
# Brief table layout
# ---------------------------------------------------------------------------

_BRIEF_HEADERS = ["#", "ID", "Subject", "From", "Date", "Preview"]
_BRIEF_COL_WIDTHS = [3, 7, 28, 20, 8, 30]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def _fetch_unread(account: str | None = None) -> list[dict]:
    """Fetch all unread INBOX messages with preview across all (or one) accounts."""
    inner_ops = (
        f'set msgPreview to ""\n'
        f"            try\n"
        f"                set msgPreview to content of m\n"
        f"                if length of msgPreview > 80 then\n"
        f"                    set msgPreview to text 1 thru 80 of msgPreview\n"
        f"                end if\n"
        f"            on error\n"
        f'                set msgPreview to ""\n'
        f"            end try\n"
        f'            set output to output & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & "{FIELD_SEPARATOR}" & msgPreview & linefeed'
    )

    script = inbox_iterator_all_accounts(inner_ops, cap=50, account=account)
    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)

    if not result.strip():
        return []

    fields = ["account", "id", "subject", "sender", "date", "flagged", "preview"]
    messages = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        # If preview is empty the trailing separator may be stripped — pad it back.
        if line.count(FIELD_SEPARATOR) == len(fields) - 2:
            line = line + FIELD_SEPARATOR
        msg = parse_message_line(line, fields, FIELD_SEPARATOR)
        if msg is not None:
            messages.append(msg)

    return messages


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _is_action_required(subject: str) -> bool:
    """Return True if the subject contains any deadline/action keyword."""
    lower = subject.lower()
    return any(kw in lower for kw in _ACTION_KEYWORDS)


def _is_notification(sender: str) -> bool:
    """Return True if the sender looks like an automated / noreply address."""
    email = extract_email(sender).lower()
    return any(p in email for p in NOREPLY_PATTERNS)


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------


def classify_messages(messages: list[dict]) -> dict[str, list[dict]]:
    """Classify unread messages into action_required, flagged, people, notifications.

    Priority (a message appears in only one section):
        1. ACTION REQUIRED (deadline keyword in subject)
        2. FLAGGED
        3. PEOPLE (real human sender)
        4. NOTIFICATIONS (automated / noreply)
    """
    action_required: list[dict] = []
    flagged: list[dict] = []
    people: list[dict] = []
    notifications: list[dict] = []

    seen: set = set()

    for msg in messages:
        msg_id = msg["id"]
        if msg_id in seen:
            continue
        seen.add(msg_id)

        if _is_action_required(msg.get("subject", "")):
            action_required.append(msg)
        elif msg.get("flagged"):
            flagged.append(msg)
        elif _is_notification(msg.get("sender", "")):
            notifications.append(msg)
        else:
            people.append(msg)

    return {
        "action_required": action_required,
        "flagged": flagged,
        "people": people,
        "notifications": notifications,
    }


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------


def _build_rows(messages: list[dict], start_alias: int) -> list[list[str]]:
    rows = []
    for i, msg in enumerate(messages, start_alias):
        sender = extract_display_name(msg.get("sender", ""))
        rows.append(
            [
                str(i),
                str(msg["id"]),
                truncate(msg.get("subject", ""), 28),
                truncate(sender, 20),
                format_short_date(msg.get("date", "")),
                truncate(msg.get("preview", "").replace("\n", " ").strip(), 30),
            ]
        )
    return rows


def _section_text(title: str, messages: list[dict], start_alias: int) -> str:
    rows = _build_rows(messages, start_alias)
    table = format_table(_BRIEF_HEADERS, rows, _BRIEF_COL_WIDTHS)
    return f"{title} ({len(messages)}):\n{table}"


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def cmd_brief(args) -> None:
    """Show a daily email brief: action-required, flagged, people, notification count."""
    account = getattr(args, "account", None)
    verbose = getattr(args, "verbose", False)

    messages = _fetch_unread(account=account)
    classified = classify_messages(messages)

    action_required = classified["action_required"]
    flagged = classified["flagged"]
    people = classified["people"]
    notifications = classified["notifications"]

    # JSON output
    if getattr(args, "json", False):
        format_output(
            args,
            "",
            json_data={
                "action_required": action_required,
                "flagged": flagged,
                "people": people,
                "notifications": notifications,
            },
        )
        return

    # Save aliases for all shown messages so `mxctl read N` works
    shown = action_required + flagged + people
    if verbose:
        shown = shown + notifications
    save_message_aliases([m["id"] for m in shown])
    for i, m in enumerate(shown, 1):
        m["alias"] = i

    # Header
    today = datetime.now().strftime("%a, %b %d").replace(" 0", " ")
    lines = [f"Daily Brief — {today}"]

    alias_counter = 1

    if action_required:
        lines.append("")
        lines.append(_section_text("ACTION REQUIRED", action_required, alias_counter))
        alias_counter += len(action_required)

    if flagged:
        lines.append("")
        lines.append(_section_text("FLAGGED", flagged, alias_counter))
        alias_counter += len(flagged)

    if people:
        lines.append("")
        lines.append(_section_text("PEOPLE", people, alias_counter))
        alias_counter += len(people)

    # Notifications section
    if notifications:
        if verbose:
            lines.append("")
            lines.append(_section_text("NOTIFICATIONS", notifications, alias_counter))
        else:
            lines.append("")
            lines.append(f"NOTIFICATIONS ({len(notifications)} unread — not shown)")
    else:
        lines.append("")
        lines.append("NOTIFICATIONS (0 unread)")

    if not action_required and not flagged and not people and not notifications:
        format_output(args, "Daily Brief — Inbox zero!")
        return

    format_output(args, "\n".join(lines))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register the brief subcommand."""
    p = subparsers.add_parser("brief", help="Daily email brief: actions, flagged, people, notification count")
    p.add_argument("-a", "--account", help="Limit to a specific account")
    p.add_argument("--verbose", action="store_true", help="Also show notifications table")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_brief)
