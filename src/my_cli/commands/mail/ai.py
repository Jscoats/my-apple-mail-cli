"""AI-optimized mail commands designed for Claude Code: summary, triage, context, find-related."""

from collections import defaultdict

from my_cli.config import (
    DEFAULT_DIGEST_LIMIT,
    DEFAULT_MAILBOX,
    APPLESCRIPT_TIMEOUT_LONG,
    FIELD_SEPARATOR,
    MAX_MESSAGES_BATCH,
    NOREPLY_PATTERNS,
    RECORD_SEPARATOR,
    resolve_account,
)
from my_cli.util.applescript import escape, run, validate_msg_id
from my_cli.util.applescript_templates import inbox_iterator_all_accounts
from my_cli.util.formatting import die, format_output, truncate
from my_cli.util.mail_helpers import extract_email, normalize_subject


# ---------------------------------------------------------------------------
# summary — ultra-concise one-liner per unread
# ---------------------------------------------------------------------------

def cmd_summary(args) -> None:
    """Generate an ultra-concise one-liner per unread message."""
    inner_ops = f'set output to output & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & linefeed'
    script = inbox_iterator_all_accounts(inner_ops, cap=20)

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    if not result.strip():
        format_output(args, "No unread messages.")
        return

    messages = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 5:
            messages.append({
                "account": parts[0],
                "id": int(parts[1]) if parts[1].isdigit() else parts[1],
                "subject": parts[2],
                "sender": parts[3],
                "date": parts[4],
            })

    # Ultra-concise format for AI consumption
    text = f"{len(messages)} unread:"
    for m in messages:
        # Extract just the name from sender
        sender = m["sender"]
        if "<" in sender:
            sender = sender.split("<")[0].strip().strip('"')
        text += f"\n  [{m['id']}] {truncate(sender, 20)}: {truncate(m['subject'], 55)}"
    format_output(args, text, json_data=messages)


# ---------------------------------------------------------------------------
# triage — unread grouped by urgency/category
# ---------------------------------------------------------------------------

def cmd_triage(args) -> None:
    """Group unread messages by urgency and category."""
    account = resolve_account(getattr(args, "account", None))
    inner_ops = f'set output to output & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & linefeed'
    script = inbox_iterator_all_accounts(inner_ops, cap=30, account=account)

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    if not result.strip():
        format_output(args, "No unread messages. Inbox zero!")
        return

    flagged = []
    people = []
    notifications = []

    # Simple heuristic categorization
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) < 6:
            continue
        msg = {
            "account": parts[0],
            "id": int(parts[1]) if parts[1].isdigit() else parts[1],
            "subject": parts[2],
            "sender": parts[3],
            "date": parts[4],
            "flagged": parts[5].lower() == "true",
        }

        if msg["flagged"]:
            flagged.append(msg)
        elif any(p in extract_email(msg["sender"]).lower() for p in NOREPLY_PATTERNS):
            notifications.append(msg)
        else:
            people.append(msg)

    total = len(flagged) + len(people) + len(notifications)
    text = f"Triage ({total} unread):"

    if flagged:
        text += f"\n\nFLAGGED ({len(flagged)}):"
        for m in flagged:
            sender = m["sender"].split("<")[0].strip().strip('"') if "<" in m["sender"] else m["sender"]
            text += f"\n  [{m['id']}] {truncate(sender, 20)}: {truncate(m['subject'], 50)}"

    if people:
        text += f"\n\nPEOPLE ({len(people)}):"
        for m in people:
            sender = m["sender"].split("<")[0].strip().strip('"') if "<" in m["sender"] else m["sender"]
            text += f"\n  [{m['id']}] {truncate(sender, 20)}: {truncate(m['subject'], 50)}"

    if notifications:
        text += f"\n\nNOTIFICATIONS ({len(notifications)}):"
        for m in notifications:
            sender = m["sender"].split("<")[0].strip().strip('"') if "<" in m["sender"] else m["sender"]
            text += f"\n  [{m['id']}] {truncate(sender, 20)}: {truncate(m['subject'], 50)}"

    format_output(args, text, json_data={"flagged": flagged, "people": people, "notifications": notifications})


# ---------------------------------------------------------------------------
# context — message + full thread history
# ---------------------------------------------------------------------------

def cmd_context(args) -> None:
    """Show a message with full thread history."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    message_id = validate_msg_id(args.id)
    limit = max(1, min(getattr(args, "limit", 50), MAX_MESSAGES_BATCH))
    all_accounts = getattr(args, "all_accounts", False)

    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    # Get the full message + thread subject
    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        set msgSubject to subject of theMsg
        set msgSender to sender of theMsg
        set msgDate to date received of theMsg
        set msgContent to content of theMsg

        set toList to ""
        repeat with r in (to recipients of theMsg)
            set toList to toList & (address of r) & ", "
        end repeat

        return msgSubject & "{FIELD_SEPARATOR}" & msgSender & "{FIELD_SEPARATOR}" & msgDate & "{FIELD_SEPARATOR}" & toList & "{FIELD_SEPARATOR}" & msgContent
    end tell
    """

    result = run(script)
    parts = result.split(FIELD_SEPARATOR)
    if len(parts) < 5:
        die("Failed to read message.")

    subject, sender, date, to_list, content = parts[0], parts[1], parts[2], parts[3], FIELD_SEPARATOR.join(parts[4:])

    # Find thread
    thread_subject = normalize_subject(subject)
    thread_escaped = escape(thread_subject)

    # Search for thread messages (current account or all accounts based on flag)
    if all_accounts:
        acct_loop = 'repeat with acct in (every account)\nset acctName to name of acct'
        acct_loop_end = 'end repeat'
    else:
        acct_loop = f'set acct to account "{acct_escaped}"\nset acctName to name of acct'
        acct_loop_end = ''

    thread_script = f"""
    tell application "Mail"
        set output to ""
        set totalFound to 0
        {acct_loop}
            repeat with mbox in (mailboxes of acct)
                if totalFound >= {limit} then exit repeat
                try
                    set msgs to (every message of mbox whose subject contains "{thread_escaped}")
                    repeat with m in msgs
                        if totalFound >= {limit} then exit repeat
                        if (id of m) is not {message_id} then
                            set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (content of m) & "{RECORD_SEPARATOR}"
                            set totalFound to totalFound + 1
                        end if
                    end repeat
                end try
            end repeat
        {acct_loop_end}
        return output
    end tell
    """

    thread_result = run(thread_script, timeout=APPLESCRIPT_TIMEOUT_LONG)

    # Build thread data
    thread_entries = []
    if thread_result.strip():
        for entry in thread_result.split(RECORD_SEPARATOR):
            entry = entry.strip()
            if not entry:
                continue
            p = entry.split(FIELD_SEPARATOR)
            if len(p) >= 5:
                thread_entries.append({
                    "id": int(p[0]) if p[0].isdigit() else p[0],
                    "subject": p[1],
                    "from": p[2],
                    "date": p[3],
                    "body": FIELD_SEPARATOR.join(p[4:]),
                })

    data = {
        "message": {
            "id": message_id,
            "subject": subject,
            "from": sender,
            "to": to_list.rstrip(", "),
            "date": date,
            "body": content,
        },
        "thread": thread_entries,
    }

    text = f"=== Message ===\nFrom: {sender}\nTo: {to_list.rstrip(', ')}\nDate: {date}\nSubject: {subject}\n\n{content}"
    if thread_entries:
        text += "\n\n=== Thread History ==="
        for t in thread_entries:
            text += f"\n\n--- [{t['id']}] {t['subject']} ---\nFrom: {t['from']}  Date: {t['date']}\n{t['body']}"

    format_output(args, text, json_data=data)


# ---------------------------------------------------------------------------
# find-related — search + group by conversation
# ---------------------------------------------------------------------------

def cmd_find_related(args) -> None:
    """Search for messages and group results by conversation."""
    query = args.query

    # If query is a numeric message ID, look up the message first
    if query.isdigit():
        message_id = int(query)
        lookup_script = f"""
        tell application "Mail"
            repeat with acct in (every account)
                repeat with mbox in (mailboxes of acct)
                    try
                        set theMsg to first message of mbox whose id is {message_id}
                        return (subject of theMsg) & "{FIELD_SEPARATOR}" & (sender of theMsg)
                    end try
                end repeat
            end repeat
            return ""
        end tell
        """
        lookup_result = run(lookup_script, timeout=APPLESCRIPT_TIMEOUT_LONG)
        if not lookup_result.strip():
            format_output(args, f"Message {message_id} not found.")
            return
        parts = lookup_result.strip().split(FIELD_SEPARATOR)
        query = normalize_subject(parts[0])

    query_escaped = escape(query)

    script = f"""
    tell application "Mail"
        set output to ""
        set totalFound to 0
        repeat with acct in (every account)
            if totalFound >= {DEFAULT_DIGEST_LIMIT} then exit repeat
            set acctName to name of acct
            repeat with mbox in (mailboxes of acct)
                if totalFound >= {DEFAULT_DIGEST_LIMIT} then exit repeat
                set mbName to name of mbox
                set searchResults to (every message of mbox whose subject contains "{query_escaped}")
                repeat with m in searchResults
                    if totalFound >= {DEFAULT_DIGEST_LIMIT} then exit repeat
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
        format_output(args, f"No messages found matching '{query}'.")
        return

    # Group by normalized subject (thread)
    threads = defaultdict(list)
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 6:
            msg = {
                "id": int(parts[0]) if parts[0].isdigit() else parts[0],
                "subject": parts[1],
                "sender": parts[2],
                "date": parts[3],
                "mailbox": parts[4],
                "account": parts[5],
            }
            # Normalize subject for grouping
            normalized = normalize_subject(parts[1]).lower()
            threads[normalized].append(msg)

    text = f"Related messages for '{query}' ({len(threads)} conversations):"
    for thread_subject, msgs in sorted(threads.items(), key=lambda x: -len(x[1])):
        text += f"\n\n  {thread_subject} ({len(msgs)} messages):"
        for m in msgs[:5]:
            sender = m["sender"].split("<")[0].strip().strip('"') if "<" in m["sender"] else m["sender"]
            text += f"\n    [{m['id']}] {truncate(sender, 20)} — {m['date']}"
        if len(msgs) > 5:
            text += f"\n    ... and {len(msgs) - 5} more"
    format_output(args, text, json_data=dict(threads))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    """Register AI-optimized mail subcommands."""
    p = subparsers.add_parser("summary", help="Ultra-concise one-liner per unread (AI-optimized)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_summary)

    p = subparsers.add_parser("triage", help="Unread grouped by urgency/category")
    p.add_argument("-a", "--account", help="Filter to a specific account")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_triage)

    p = subparsers.add_parser("context", help="Message + full thread history")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--limit", type=int, default=50, help="Max thread messages (default: 50)")
    p.add_argument("--all-accounts", action="store_true", help="Search all accounts (default: current only)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_context)

    p = subparsers.add_parser("find-related", help="Search + group results by conversation")
    p.add_argument("query", help="Search term")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_find_related)
