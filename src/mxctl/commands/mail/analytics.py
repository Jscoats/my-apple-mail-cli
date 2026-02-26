"""Mail analytics commands: stats, top-senders, digest, show-flagged."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    DEFAULT_DIGEST_LIMIT,
    DEFAULT_MAILBOX,
    DEFAULT_MESSAGE_LIMIT,
    DEFAULT_TOP_SENDERS_LIMIT,
    FIELD_SEPARATOR,
    MAX_MESSAGES_BATCH,
    resolve_account,
    save_message_aliases,
    validate_limit,
)
from mxctl.util.applescript import escape, run
from mxctl.util.dates import to_applescript_date
from mxctl.util.formatting import die, format_output, truncate
from mxctl.util.mail_helpers import extract_email, parse_message_line

# ---------------------------------------------------------------------------
# top-senders
# ---------------------------------------------------------------------------


def get_top_senders(days: int = 30, limit: int = DEFAULT_TOP_SENDERS_LIMIT) -> list[dict]:
    """Fetch and rank most frequent senders over the given number of days."""
    since_dt = datetime.now() - timedelta(days=days)
    since_as = to_applescript_date(since_dt)

    script = f"""
    tell application "Mail"
        set output to ""
        repeat with acct in (every account)
            if enabled of acct then
                repeat with mbox in (mailboxes of acct)
                    if name of mbox is "INBOX" then
                        try
                            set msgs to (every message of mbox whose date received >= date "{since_as}")
                            set msgCount to count of msgs
                            set cap to {MAX_MESSAGES_BATCH}
                            if msgCount < cap then set cap to msgCount
                            repeat with i from 1 to cap
                                set m to item i of msgs
                                set output to output & (sender of m) & linefeed
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

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    if not result.strip():
        return []

    counter = Counter(line.strip() for line in result.strip().split("\n") if line.strip())
    top = counter.most_common(limit)
    return [{"sender": s, "count": c} for s, c in top]


def cmd_top_senders(args) -> None:
    """Show most frequent email senders over a time period."""
    days = getattr(args, "days", 30)
    limit = getattr(args, "limit", DEFAULT_TOP_SENDERS_LIMIT)

    top = get_top_senders(days=days, limit=limit)

    if not top:
        format_output(args, f"No messages found in the last {days} days.", json_data={"days": days, "senders": []})
        return

    text = f"Top {limit} senders (last {days} days):"
    for i, entry in enumerate(top, 1):
        text += f"\n  {i}. {truncate(entry['sender'], 50)} — {entry['count']} messages"
    format_output(args, text, json_data=top)


# ---------------------------------------------------------------------------
# digest — grouped unread summary
# ---------------------------------------------------------------------------


def get_digest() -> dict:
    """Fetch unread messages and group them by sender domain."""
    script = f"""
    tell application "Mail"
        set output to ""
        repeat with acct in (every account)
            if enabled of acct then
                repeat with mbox in (mailboxes of acct)
                    if name of mbox is "INBOX" then
                        try
                            set unreadMsgs to (every message of mbox whose read status is false)
                            set acctName to name of acct
                            set cap to {DEFAULT_DIGEST_LIMIT}
                            if (count of unreadMsgs) < cap then set cap to (count of unreadMsgs)
                            repeat with j from 1 to cap
                                set m to item j of unreadMsgs
                                set output to output & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & linefeed
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

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    if not result.strip():
        return {}

    # Group by sender domain
    groups: dict = defaultdict(list)
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        msg = parse_message_line(line, ["account", "id", "subject", "sender", "date"], FIELD_SEPARATOR)
        if msg is None:
            continue
        email = extract_email(msg["sender"])
        if "@" in email:
            domain = email.split("@")[1].lower()
        else:
            domain = "other"
        groups[domain].append(msg)

    return dict(groups)


def cmd_digest(args) -> None:
    """Show unread messages grouped by sender domain."""
    groups = get_digest()

    if not groups:
        format_output(args, "No unread messages. Inbox zero!")
        return

    # Collect all messages into a flat list for sequential aliases
    all_messages = []
    for _domain, msgs in sorted(groups.items(), key=lambda x: -len(x[1])):
        all_messages.extend(msgs)
    save_message_aliases([m["id"] for m in all_messages])
    for i, m in enumerate(all_messages, 1):
        m["alias"] = i

    total = sum(len(msgs) for msgs in groups.values())
    text = f"Unread Digest ({total} messages, {len(groups)} groups):"
    for domain, msgs in sorted(groups.items(), key=lambda x: -len(x[1])):
        text += f"\n\n  {domain} ({len(msgs)}):"
        for m in msgs[:5]:
            text += f"\n    [{m['alias']}] {truncate(m['subject'], 45)}"
            text += f"\n      From: {truncate(m['sender'], 40)}"
        if len(msgs) > 5:
            text += f"\n    ... and {len(msgs) - 5} more"
    format_output(args, text, json_data=groups)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def get_stats(
    show_all: bool = False,
    account: str | None = None,
    explicit_account: str | None = None,
    mailbox: str = DEFAULT_MAILBOX,
) -> dict:
    """Fetch mailbox or account-wide stats.

    Returns a dict with keys depending on mode:
    - Single mailbox: {"mailbox", "account", "total", "unread"}
    - All mailboxes: {"scope", "total_messages", "total_unread", "mailboxes"}
    """
    if show_all:
        if explicit_account:
            acct_escaped = escape(account)
            script = f"""
            tell application "Mail"
                set acct to account "{acct_escaped}"
                set acctName to name of acct
                set output to ""
                set grandTotal to 0
                set grandUnread to 0
                repeat with mb in (every mailbox of acct)
                    set mbName to name of mb
                    set totalCount to count of messages of mb
                    set unreadCount to unread count of mb
                    set grandTotal to grandTotal + totalCount
                    set grandUnread to grandUnread + unreadCount
                    set output to output & acctName & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & (totalCount as text) & "{FIELD_SEPARATOR}" & (unreadCount as text) & linefeed
                end repeat
                return (grandTotal as text) & "{FIELD_SEPARATOR}" & (grandUnread as text) & linefeed & output
            end tell
            """
        else:
            script = f"""
            tell application "Mail"
                set output to ""
                set grandTotal to 0
                set grandUnread to 0
                repeat with acct in (every account)
                    if enabled of acct then
                        set acctName to name of acct
                        repeat with mb in (every mailbox of acct)
                            set mbName to name of mb
                            set totalCount to count of messages of mb
                            set unreadCount to unread count of mb
                            set grandTotal to grandTotal + totalCount
                            set grandUnread to grandUnread + unreadCount
                            set output to output & acctName & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & (totalCount as text) & "{FIELD_SEPARATOR}" & (unreadCount as text) & linefeed
                        end repeat
                    end if
                end repeat
                return (grandTotal as text) & "{FIELD_SEPARATOR}" & (grandUnread as text) & linefeed & output
            end tell
            """

        result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
        lines = result.strip().split("\n")
        if not lines:  # pragma: no cover — str.split() always returns at least [""]
            return {"scope": account if explicit_account else "all", "total_messages": 0, "total_unread": 0, "mailboxes": []}

        totals_parts = lines[0].split(FIELD_SEPARATOR)
        grand_total = int(totals_parts[0]) if len(totals_parts) >= 1 and totals_parts[0].isdigit() else 0
        grand_unread = int(totals_parts[1]) if len(totals_parts) >= 2 and totals_parts[1].isdigit() else 0

        mailboxes = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(FIELD_SEPARATOR)
            if len(parts) >= 4:
                mailboxes.append(
                    {
                        "account": parts[0],
                        "name": parts[1],
                        "total": int(parts[2]) if parts[2].isdigit() else 0,
                        "unread": int(parts[3]) if parts[3].isdigit() else 0,
                    }
                )

        return {
            "scope": account if explicit_account else "all",
            "total_messages": grand_total,
            "total_unread": grand_unread,
            "mailboxes": mailboxes,
        }
    else:
        acct_escaped = escape(account)
        mb_escaped = escape(mailbox)

        script = f"""
        tell application "Mail"
            set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
            set totalCount to count of messages of mb
            set unreadCount to unread count of mb
            return (totalCount as text) & "{FIELD_SEPARATOR}" & (unreadCount as text)
        end tell
        """

        result = run(script)
        parts = result.split(FIELD_SEPARATOR)
        total = int(parts[0]) if len(parts) >= 1 and parts[0].isdigit() else 0
        unread = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
        return {"mailbox": mailbox, "account": account, "total": total, "unread": unread}


def cmd_stats(args) -> None:
    """Show message count and unread count for a mailbox, or account-wide stats with --all."""
    show_all = getattr(args, "all", False)
    # For --all, we need to know if the user *explicitly* passed -a, not just the resolved default.
    # resolve_account() falls back to the configured default (e.g. iCloud), which would cause
    # --all without -a to incorrectly use the single-account branch.
    explicit_account = getattr(args, "account", None)
    account = resolve_account(explicit_account)

    if show_all:
        data = get_stats(show_all=True, account=account, explicit_account=explicit_account)
        mailboxes = data["mailboxes"]

        if not mailboxes:
            scope = f"account '{account}'" if explicit_account else "any account"
            format_output(args, f"No mailboxes found in {scope}.", json_data={"mailboxes": []})
            return

        scope_label = f"Account: {account}" if explicit_account else "All Accounts"
        text = f"{scope_label}\n"
        text += f"Total: {data['total_messages']} messages, {data['total_unread']} unread\n"
        text += f"\nMailboxes ({len(mailboxes)}):"
        for mb in mailboxes:
            acct_prefix = "" if explicit_account else f"[{mb['account']}] "
            text += f"\n  {acct_prefix}{mb['name']}: {mb['total']} messages, {mb['unread']} unread"

        format_output(args, text, json_data=data)
    else:
        # Single mailbox stats (existing behavior)
        if not account:
            die("Account required. Use -a ACCOUNT.")
        mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX

        data = get_stats(show_all=False, account=account, mailbox=mailbox)
        format_output(
            args,
            f"{mailbox} [{account}]: {data['total']} messages, {data['unread']} unread",
            json_data=data,
        )


# ---------------------------------------------------------------------------
# show-flagged — list all flagged messages
# ---------------------------------------------------------------------------


def get_flagged_messages(account: str | None = None, limit: int = DEFAULT_MESSAGE_LIMIT) -> list[dict]:
    """Fetch all flagged messages, optionally filtered by account."""
    if account:
        acct_escaped = escape(account)
        script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set output to ""
            set totalFound to 0
            repeat with mb in (every mailbox of acct)
                if totalFound >= {limit} then exit repeat
                set mbName to name of mb
                set flaggedMsgs to (every message of mb whose flagged status is true)
                repeat with m in flaggedMsgs
                    if totalFound >= {limit} then exit repeat
                    set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & "{acct_escaped}" & linefeed
                    set totalFound to totalFound + 1
                end repeat
            end repeat
            return output
        end tell
        """
    else:
        script = f"""
        tell application "Mail"
            set output to ""
            set totalFound to 0
            repeat with acct in (every account)
                if totalFound >= {limit} then exit repeat
                set acctName to name of acct
                repeat with mb in (every mailbox of acct)
                    if totalFound >= {limit} then exit repeat
                    set mbName to name of mb
                    set flaggedMsgs to (every message of mb whose flagged status is true)
                    repeat with m in flaggedMsgs
                        if totalFound >= {limit} then exit repeat
                        set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & acctName & linefeed
                        set totalFound to totalFound + 1
                    end repeat
                end repeat
            end repeat
            return output
        end tell
        """

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    if not result.strip():
        return []

    messages = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        msg = parse_message_line(line, ["id", "subject", "sender", "date", "mailbox", "account"], FIELD_SEPARATOR)
        if msg is not None:
            messages.append(msg)
    return messages


def cmd_show_flagged(args) -> None:
    """List all flagged messages."""
    account = resolve_account(getattr(args, "account", None))
    limit = validate_limit(getattr(args, "limit", DEFAULT_MESSAGE_LIMIT))

    messages = get_flagged_messages(account=account, limit=limit)

    if not messages:
        scope = f" in account '{account}'" if account else " across all accounts"
        format_output(args, f"No flagged messages found{scope}.", json_data={"flagged_messages": []})
        return

    save_message_aliases([m["id"] for m in messages])
    for i, m in enumerate(messages, 1):
        m["alias"] = i

    scope = f" in account '{account}'" if account else " across all accounts"
    text = f"Flagged messages{scope} (showing up to {limit}):"
    for m in messages:
        text += f"\n- [{m['alias']}] {truncate(m['subject'], 60)}"
        text += f"\n  From: {m['sender']}"
        text += f"\n  Date: {m['date']}"
        text += f"\n  Location: {m['mailbox']} [{m['account']}]"
    format_output(args, text, json_data=messages)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register analytics mail subcommands."""
    p = subparsers.add_parser("top-senders", help="Most frequent senders")
    p.add_argument("--days", type=int, default=30, help="Look back N days (default: 30)")
    p.add_argument("--limit", type=int, default=10, help="Number of senders to show")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_top_senders)

    p = subparsers.add_parser("digest", help="Grouped unread summary")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_digest)

    p = subparsers.add_parser("stats", help="Message count and unread count for a mailbox")
    p.add_argument("mailbox", nargs="?", default=None, help="Mailbox name (default: INBOX)")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--all", action="store_true", help="Show account-wide stats across all mailboxes")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_stats)

    p = subparsers.add_parser("show-flagged", help="List all flagged messages")
    p.add_argument("-a", "--account", help="Filter by account name")
    p.add_argument("--limit", type=int, default=DEFAULT_MESSAGE_LIMIT, help="Maximum messages to show")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_show_flagged)
