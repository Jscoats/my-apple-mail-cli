"""Inbox management tools: process-inbox, clean-newsletters, weekly-review."""

from collections import defaultdict
from datetime import datetime, timedelta

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    DEFAULT_MAILBOX,
    FIELD_SEPARATOR,
    MAX_MESSAGES_BATCH,
    NOREPLY_PATTERNS,
    resolve_account,
    save_message_aliases,
    validate_limit,
)
from mxctl.util.applescript import escape, run
from mxctl.util.applescript_templates import mailbox_iterator
from mxctl.util.dates import to_applescript_date
from mxctl.util.formatting import format_output, truncate
from mxctl.util.mail_helpers import extract_display_name, extract_email, parse_message_line

# ---------------------------------------------------------------------------
# Private helpers — AppleScript builders
# ---------------------------------------------------------------------------


def _build_process_inbox_script(account: str | None, limit: int) -> str:
    """Return an AppleScript that scans INBOX(es) for unread messages.

    When *account* is given, only that account's INBOX is scanned.
    Otherwise all enabled accounts are scanned up to *limit* total messages.
    Output rows: acctName|id|subject|sender|date|flagged
    """
    msg_row = (
        f'set output to output & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}"'
        f' & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}"'
        f' & (date received of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & linefeed'
    )
    if account:
        acct_escaped = escape(account)
        return f"""
        tell application "Mail"
            set output to ""
            set totalFound to 0
            set acct to account "{acct_escaped}"
            set acctName to name of acct
            if enabled of acct then
                repeat with mbox in (mailboxes of acct)
                    if name of mbox is "INBOX" then
                        try
                            set unreadMsgs to (every message of mbox whose read status is false)
                            set cap to {limit}
                            if (count of unreadMsgs) < cap then set cap to (count of unreadMsgs)
                            repeat with j from 1 to cap
                                set m to item j of unreadMsgs
                                {msg_row}
                                set totalFound to totalFound + 1
                            end repeat
                        end try
                        exit repeat
                    end if
                end repeat
            end if
            return output
        end tell
        """
    # All enabled accounts — honour the global limit across accounts
    return f"""
        tell application "Mail"
            set output to ""
            set totalFound to 0
            repeat with acct in (every account)
                if totalFound >= {limit} then exit repeat
                if enabled of acct then
                    set acctName to name of acct
                    repeat with mbox in (mailboxes of acct)
                        if totalFound >= {limit} then exit repeat
                        if name of mbox is "INBOX" then
                            try
                                set unreadMsgs to (every message of mbox whose read status is false)
                                set cap to {limit} - totalFound
                                if (count of unreadMsgs) < cap then set cap to (count of unreadMsgs)
                                repeat with j from 1 to cap
                                    set m to item j of unreadMsgs
                                    {msg_row}
                                    set totalFound to totalFound + 1
                                end repeat
                            end try
                            exit repeat
                        end if
                    end repeat
                end if
            end repeat
            return output
        end tell
        """


def _build_newsletters_script(account: str | None, mailbox: str, limit: int) -> str:
    """Return an AppleScript that collects sender/read-status rows from a mailbox.

    When *account* is given, only that account's named mailbox is scanned.
    Otherwise all enabled accounts are scanned up to *limit* total messages.
    Output rows: sender|read_status
    """
    msg_row = f'set output to output & (sender of m) & "{FIELD_SEPARATOR}" & (read status of m) & linefeed'
    if account:
        acct_escaped = escape(account)
        mb_escaped = escape(mailbox)
        return f"""
        tell application "Mail"
            set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
            set allMsgs to (every message of mb)
            set msgCount to count of allMsgs
            set cap to {limit}
            if msgCount < cap then set cap to msgCount
            set output to ""
            repeat with i from 1 to cap
                set m to item i of allMsgs
                {msg_row}
            end repeat
            return output
        end tell
        """
    # All enabled accounts — honour the global limit across accounts
    return f"""
        tell application "Mail"
            set output to ""
            set totalFound to 0
            repeat with acct in (every account)
                if enabled of acct then
                    repeat with mbox in (mailboxes of acct)
                        if name of mbox is "{mailbox}" then
                            try
                                set allMsgs to (every message of mbox)
                                set msgCount to count of allMsgs
                                set cap to {limit}
                                if msgCount < cap then set cap to msgCount
                                repeat with i from 1 to cap
                                    set m to item i of allMsgs
                                    {msg_row}
                                    set totalFound to totalFound + 1
                                    if totalFound >= {limit} then exit repeat
                                end repeat
                            end try
                            exit repeat
                        end if
                    end repeat
                    if totalFound >= {limit} then exit repeat
                end if
            end repeat
            return output
        end tell
        """


# ---------------------------------------------------------------------------
# process-inbox — categorize unread messages and suggest actions
# ---------------------------------------------------------------------------


def get_inbox_categories(account: str | None, limit: int) -> dict:
    """Categorize unread inbox messages into flagged, people, and notifications.

    Returns dict with keys: total, flagged, people, notifications (each a list of message dicts).
    """
    script = _build_process_inbox_script(account, limit)
    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)

    flagged = []
    people = []
    notifications = []

    if result.strip():
        for line in result.strip().split("\n"):
            if not line.strip():
                continue
            msg = parse_message_line(line, ["account", "id", "subject", "sender", "date", "flagged"], FIELD_SEPARATOR)
            if msg is None:
                continue

            if msg["flagged"]:
                flagged.append(msg)
            elif any(p in extract_email(msg["sender"]).lower() for p in NOREPLY_PATTERNS):
                notifications.append(msg)
            else:
                people.append(msg)

    total = len(flagged) + len(people) + len(notifications)
    return {
        "total": total,
        "flagged": flagged,
        "people": people,
        "notifications": notifications,
    }


def cmd_process_inbox(args) -> None:
    """Read-only diagnostic: categorize unread messages and output action plan."""
    # Use only the explicitly-passed -a flag, not the config default.
    # resolve_account() would return the default account (e.g. iCloud) when no
    # flag is given, causing process-inbox to show only one account instead of all.
    account = getattr(args, "account", None)
    limit = validate_limit(getattr(args, "limit", 50))

    json_data = get_inbox_categories(account, limit)
    flagged = json_data["flagged"]
    people = json_data["people"]
    notifications = json_data["notifications"]
    total = json_data["total"]

    if total == 0:
        format_output(args, "No unread messages found.")
        return

    # Assign sequential aliases across all categories
    all_messages = flagged + people + notifications
    save_message_aliases([m["id"] for m in all_messages])
    for i, m in enumerate(all_messages, 1):
        m["alias"] = i

    text = f"Inbox Processing Plan ({total} unread):"

    # Suggest actions for each category
    if flagged:
        text += f"\n\nFLAGGED ({len(flagged)}) — High priority:"
        for m in flagged[:5]:
            sender = extract_display_name(m["sender"])
            text += f"\n  [{m['alias']}] {truncate(sender, 20)}: {truncate(m['subject'], 50)}"
        if len(flagged) > 5:
            text += f"\n  ... and {len(flagged) - 5} more"
        text += "\n\nSuggested commands:"
        text += f'\n  mxctl read <ID> -a "{flagged[0]["account"]}"'
        text += f'\n  mxctl to-todoist <ID> -a "{flagged[0]["account"]}" --priority 4'

    if people:
        text += f"\n\nPEOPLE ({len(people)}) — Requires attention:"
        for m in people[:5]:
            sender = extract_display_name(m["sender"])
            text += f"\n  [{m['alias']}] {truncate(sender, 20)}: {truncate(m['subject'], 50)}"
        if len(people) > 5:
            text += f"\n  ... and {len(people) - 5} more"
        text += "\n\nSuggested commands:"
        text += f'\n  mxctl read <ID> -a "{people[0]["account"]}"'
        text += f'\n  mxctl mark-read <ID> -a "{people[0]["account"]}"'

    if notifications:
        text += f"\n\nNOTIFICATIONS ({len(notifications)}) — Bulk actions:"
        for m in notifications[:5]:
            sender = extract_display_name(m["sender"])
            text += f"\n  [{m['alias']}] {truncate(sender, 20)}: {truncate(m['subject'], 50)}"
        if len(notifications) > 5:
            text += f"\n  ... and {len(notifications) - 5} more"
        text += "\n\nSuggested commands:"
        text += f'\n  mxctl batch-read -a "{notifications[0]["account"]}"'
        text += f'\n  mxctl unsubscribe <ID> -a "{notifications[0]["account"]}"'

    format_output(args, text, json_data=json_data)


# ---------------------------------------------------------------------------
# clean-newsletters — identify bulk senders + suggest cleanup
# ---------------------------------------------------------------------------


def get_newsletter_senders(account: str | None, mailbox: str, limit: int) -> dict:
    """Identify likely newsletter senders from a mailbox.

    Returns dict with keys:
      - newsletters (list[dict]): identified newsletter senders
      - has_messages (bool): False if the mailbox had no messages at all
    """
    script = _build_newsletters_script(account, mailbox, limit)
    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)

    if not result.strip():
        return {"newsletters": [], "has_messages": False}

    # Group by sender email
    sender_stats: dict = defaultdict(lambda: {"total": 0, "unread": 0})
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 2:
            sender_raw = parts[0]
            is_read = parts[1].lower() == "true"
            email = extract_email(sender_raw)
            sender_stats[email]["total"] += 1
            if not is_read:
                sender_stats[email]["unread"] += 1

    # Identify likely newsletters
    newsletters = []
    for email, stats in sender_stats.items():
        is_likely_newsletter = stats["total"] >= 3 or any(pattern in email.lower() for pattern in NOREPLY_PATTERNS)
        if is_likely_newsletter:
            newsletters.append(
                {
                    "sender": email,
                    "total_messages": stats["total"],
                    "unread_messages": stats["unread"],
                }
            )

    # Sort by message count descending
    newsletters.sort(key=lambda x: x["total_messages"], reverse=True)
    return {"newsletters": newsletters, "has_messages": True}


def cmd_clean_newsletters(args) -> None:
    """Identify likely newsletter senders and suggest batch-move commands."""
    account = resolve_account(getattr(args, "account", None))
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    limit = max(1, min(getattr(args, "limit", 200), MAX_MESSAGES_BATCH))

    data = get_newsletter_senders(account, mailbox, limit)
    newsletters = data["newsletters"]

    if not data.get("has_messages", True):
        scope = f"in {mailbox} [{account}]" if account else "in INBOX across all accounts"
        format_output(args, f"No messages found {scope}.", json_data={"newsletters": []})
        return

    if not newsletters:
        format_output(args, "No newsletter senders identified.", json_data={"newsletters": []})
        return

    # Build output
    scope = f" in {mailbox} [{account}]" if account else " across all accounts"
    text = f"Identified {len(newsletters)} newsletter senders{scope} (from {limit} recent messages):"

    for nl in newsletters:
        text += f"\n\n  {nl['sender']}"
        text += f"\n    Total: {nl['total_messages']} messages ({nl['unread_messages']} unread)"

        # Suggest cleanup command
        acct_flag = f'-a "{account}"' if account else ""
        cleanup_cmd = f'mxctl batch-move --from-sender "{nl["sender"]}" --to-mailbox "Newsletters" {acct_flag}'
        text += f"\n    Cleanup: {cleanup_cmd}"

    format_output(args, text, json_data=data)


# ---------------------------------------------------------------------------
# weekly-review — flagged + unreplied + attachment report
# ---------------------------------------------------------------------------


def get_weekly_review(account: str | None, days: int) -> dict:
    """Generate weekly review data: flagged, attachment, and unreplied messages.

    Returns dict with day/account context plus three message lists.
    """
    # Calculate date threshold
    since_dt = datetime.now() - timedelta(days=days)
    since_as = to_applescript_date(since_dt)

    # Pass the already-escaped account name to mailbox_iterator (or None for all accounts).
    acct_escaped = escape(account) if account else None

    # Category 1: Flagged messages (all mailboxes, not date-filtered)
    flagged_inner = (
        f"set flaggedMsgs to (every message of mb whose flagged status is true)\n"
        f"                repeat with m in flaggedMsgs\n"
        f'                    set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & linefeed\n'
        f"                end repeat"
    )
    flagged_script = mailbox_iterator(flagged_inner, account=acct_escaped)

    # Category 2: Messages with attachments from last N days
    attachments_inner = (
        f'set msgs to (every message of mb whose date received >= date "{since_as}")\n'
        f"                set msgCount to count of msgs\n"
        f"                set cap to {MAX_MESSAGES_BATCH}\n"
        f"                if msgCount < cap then set cap to msgCount\n"
        f"                repeat with i from 1 to cap\n"
        f"                    set m to item i of msgs\n"
        f"                    if (count of mail attachments of m) > 0 then\n"
        f'                        set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (count of mail attachments of m) & linefeed\n'
        f"                    end if\n"
        f"                end repeat"
    )
    attachments_script = mailbox_iterator(attachments_inner, account=acct_escaped)

    # Category 3: Unreplied messages from people (last N days, not yet replied to)
    unreplied_inner = (
        f'set msgs to (every message of mb whose date received >= date "{since_as}" and was replied to is false)\n'
        f"                set msgCount to count of msgs\n"
        f"                set cap to {MAX_MESSAGES_BATCH}\n"
        f"                if msgCount < cap then set cap to msgCount\n"
        f"                repeat with i from 1 to cap\n"
        f"                    set m to item i of msgs\n"
        f'                    set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & linefeed\n'
        f"                end repeat"
    )
    unreplied_script = mailbox_iterator(unreplied_inner, account=acct_escaped)

    # Execute all three queries
    flagged_result = run(flagged_script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    attachments_result = run(attachments_script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    unreplied_result = run(unreplied_script, timeout=APPLESCRIPT_TIMEOUT_LONG)

    # Parse flagged messages
    flagged_messages = []
    if flagged_result.strip():
        for line in flagged_result.strip().split("\n"):
            if not line.strip():
                continue
            msg = parse_message_line(line, ["id", "subject", "sender", "date"], FIELD_SEPARATOR)
            if msg is not None:
                flagged_messages.append(msg)

    # Parse messages with attachments
    attachment_messages = []
    if attachments_result.strip():
        for line in attachments_result.strip().split("\n"):
            if not line.strip():
                continue
            msg = parse_message_line(line, ["id", "subject", "sender", "date", "attachment_count"], FIELD_SEPARATOR)
            if msg is not None:
                msg["attachment_count"] = int(msg["attachment_count"]) if str(msg["attachment_count"]).isdigit() else 0
                attachment_messages.append(msg)

    # Parse unreplied messages (filter out noreply senders)
    unreplied_messages = []
    if unreplied_result.strip():
        for line in unreplied_result.strip().split("\n"):
            if not line.strip():
                continue
            msg = parse_message_line(line, ["id", "subject", "sender", "date"], FIELD_SEPARATOR)
            if msg is None:
                continue
            sender_email = extract_email(msg["sender"])
            if not any(pattern in sender_email.lower() for pattern in NOREPLY_PATTERNS):
                unreplied_messages.append(msg)

    return {
        "days": days,
        "account": account,
        "flagged_count": len(flagged_messages),
        "attachment_count": len(attachment_messages),
        "unreplied_count": len(unreplied_messages),
        "flagged_messages": flagged_messages,
        "attachment_messages": attachment_messages,
        "unreplied_messages": unreplied_messages,
    }


def cmd_weekly_review(args) -> None:
    """Generate weekly review: flagged, messages with attachments, unreplied from people."""
    account = resolve_account(getattr(args, "account", None))
    days = getattr(args, "days", 7)

    json_data = get_weekly_review(account, days)
    flagged_messages = json_data["flagged_messages"]
    attachment_messages = json_data["attachment_messages"]
    unreplied_messages = json_data["unreplied_messages"]

    # Assign sequential aliases across all sections
    all_messages = flagged_messages + attachment_messages + unreplied_messages
    save_message_aliases([m["id"] for m in all_messages])
    for i, m in enumerate(all_messages, 1):
        m["alias"] = i

    # Build report
    scope = f" for account '{account}'" if account else " across all accounts"
    text = f"Weekly Review{scope} (last {days} days):"

    # Section 1: Flagged messages
    text += f"\n\nFlagged Messages ({len(flagged_messages)}):"
    if flagged_messages:
        for msg in flagged_messages[:10]:  # Show up to 10
            text += f"\n  [{msg['alias']}] {truncate(msg['subject'], 60)}"
            text += f"\n      From: {truncate(msg['sender'], 50)}"
        if len(flagged_messages) > 10:
            text += f"\n  ... and {len(flagged_messages) - 10} more"
    else:
        text += "\n  None"

    # Section 2: Messages with attachments
    text += f"\n\nMessages with Attachments ({len(attachment_messages)}):"
    if attachment_messages:
        for msg in attachment_messages[:10]:
            text += f"\n  [{msg['alias']}] {truncate(msg['subject'], 60)} ({msg['attachment_count']} attachments)"
            text += f"\n      From: {truncate(msg['sender'], 50)}"
        if len(attachment_messages) > 10:
            text += f"\n  ... and {len(attachment_messages) - 10} more"
    else:
        text += "\n  None"

    # Section 3: Unreplied from people
    text += f"\n\nUnreplied from People ({len(unreplied_messages)}):"
    if unreplied_messages:
        for msg in unreplied_messages[:10]:
            text += f"\n  [{msg['alias']}] {truncate(msg['subject'], 60)}"
            text += f"\n      From: {truncate(msg['sender'], 50)}"
        if len(unreplied_messages) > 10:
            text += f"\n  ... and {len(unreplied_messages) - 10} more"
    else:
        text += "\n  None"

    # Add suggested actions
    text += "\n\nSuggested Actions:"
    if flagged_messages:
        text += "\n  • Review flagged messages and unflag when done: mxctl unflag <id>"
    if unreplied_messages:
        text += "\n  • Reply to pending messages from real people"
    if attachment_messages:
        text += "\n  • Review and save important attachments: mxctl save-attachment <id> <filename> <path>"
    if not flagged_messages and not unreplied_messages and not attachment_messages:
        text += "\n  • Great job! Your inbox is clean."

    format_output(args, text, json_data=json_data)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    # process-inbox
    p = subparsers.add_parser("process-inbox", help="Categorize unread messages and suggest actions")
    p.add_argument("-a", "--account", help="Limit to specific account (default: all)")
    p.add_argument("--limit", type=int, default=50, help="Max messages to scan (default: 50)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_process_inbox)

    # clean-newsletters
    p = subparsers.add_parser("clean-newsletters", help="Identify bulk senders and suggest cleanup")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--limit", type=int, default=200, help="Number of recent messages to analyze (default: 200)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_clean_newsletters)

    # weekly-review
    p = subparsers.add_parser("weekly-review", help="Flagged + unreplied + attachment report")
    p.add_argument("-a", "--account", help="Filter by account name (default: all accounts)")
    p.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_weekly_review)
