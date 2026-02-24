"""Message listing and reading commands: list, read, search."""

from datetime import timedelta

from my_cli.config import (
    DEFAULT_BODY_LENGTH,
    DEFAULT_MESSAGE_LIMIT,
    FIELD_SEPARATOR,
    resolve_account,
    save_message_aliases,
    validate_limit,
)
from my_cli.util.applescript import escape, run, validate_msg_id
from my_cli.util.dates import parse_date, to_applescript_date
from my_cli.util.formatting import format_output, truncate
from my_cli.util.mail_helpers import parse_message_line, resolve_mailbox, resolve_message_context


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def cmd_list(args) -> None:
    """List messages in a mailbox with optional filtering."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    limit = validate_limit(getattr(args, "limit", DEFAULT_MESSAGE_LIMIT))
    unread_only = getattr(args, "unread", False)
    after = getattr(args, "after", None)
    before = getattr(args, "before", None)

    filters = []
    if unread_only:
        filters.append("read status is false")
    if after:
        start_dt = parse_date(after)
        filters.append(f'date received >= date "{to_applescript_date(start_dt)}"')
    if before:
        end_dt = parse_date(before) + timedelta(days=1)
        filters.append(f'date received < date "{to_applescript_date(end_dt)}"')

    filter_clause = " and ".join(filters) if filters else ""
    whose_clause = f"whose {filter_clause}" if filter_clause else ""

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set allMsgs to (every message of mb {whose_clause})
        set msgCount to count of allMsgs
        set actualLimit to {limit}
        if msgCount < actualLimit then set actualLimit to msgCount
        if actualLimit = 0 then return ""
        set output to ""
        repeat with i from 1 to actualLimit
            set m to item i of allMsgs
            set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (read status of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & linefeed
        end repeat
        return output
    end tell
    """

    result = run(script)

    if not result.strip():
        filter_desc = []
        if unread_only:
            filter_desc.append("unread")
        if after:
            filter_desc.append(f"from {after}")
        if before:
            filter_desc.append(f"to {before}")
        filter_str = f" ({', '.join(filter_desc)})" if filter_desc else ""
        format_output(args, f"No messages found in {mailbox}{filter_str}.")
        return

    # Build JSON data and text output
    messages = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        msg = parse_message_line(line, ["id", "subject", "sender", "date", "read", "flagged"], FIELD_SEPARATOR)
        if msg is not None:
            messages.append(msg)

    save_message_aliases([m["id"] for m in messages])
    for i, m in enumerate(messages, 1):
        m["alias"] = i

    text = f"Messages in {mailbox} [{account}] (showing up to {limit}):"
    for m in messages:
        status_icons = []
        if not m["read"]:
            status_icons.append("UNREAD")
        if m["flagged"]:
            status_icons.append("FLAGGED")
        status_str = f" [{', '.join(status_icons)}]" if status_icons else ""
        text += f"\n- [{m['alias']}] {truncate(m['subject'], 60)}{status_str}"
        text += f"\n  From: {m['sender']}"
        text += f"\n  Date: {m['date']}"
    format_output(args, text, json_data=messages)


# ---------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------

def cmd_read(args) -> None:
    """Read full message details including headers and body."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    short = getattr(args, "short", False)
    body_limit = DEFAULT_BODY_LENGTH if not short else 500

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}

        set msgId to id of theMsg
        set msgMessageId to message id of theMsg
        set msgSubject to subject of theMsg
        set msgSender to sender of theMsg
        set msgDate to date received of theMsg
        set msgRead to read status of theMsg
        set msgFlagged to flagged status of theMsg
        set msgJunk to junk mail status of theMsg
        set msgDeleted to deleted status of theMsg
        set msgForwarded to was forwarded of theMsg
        set msgReplied to was replied to of theMsg

        set toList to ""
        repeat with r in (to recipients of theMsg)
            set toList to toList & (address of r) & ","
        end repeat

        set ccList to ""
        repeat with r in (cc recipients of theMsg)
            set ccList to ccList & (address of r) & ","
        end repeat

        try
            set msgReplyTo to reply to of theMsg
        on error
            set msgReplyTo to ""
        end try

        set msgContent to content of theMsg
        set attCount to count of mail attachments of theMsg

        return (msgId as text) & "{FIELD_SEPARATOR}" & msgMessageId & "{FIELD_SEPARATOR}" & msgSubject & "{FIELD_SEPARATOR}" & msgSender & "{FIELD_SEPARATOR}" & (msgDate as text) & "{FIELD_SEPARATOR}" & (msgRead as text) & "{FIELD_SEPARATOR}" & (msgFlagged as text) & "{FIELD_SEPARATOR}" & (msgJunk as text) & "{FIELD_SEPARATOR}" & (msgDeleted as text) & "{FIELD_SEPARATOR}" & (msgForwarded as text) & "{FIELD_SEPARATOR}" & (msgReplied as text) & "{FIELD_SEPARATOR}" & toList & "{FIELD_SEPARATOR}" & ccList & "{FIELD_SEPARATOR}" & msgReplyTo & "{FIELD_SEPARATOR}" & msgContent & "{FIELD_SEPARATOR}" & (attCount as text)
    end tell
    """

    result = run(script)
    parts = result.split(FIELD_SEPARATOR)

    if len(parts) < 16:
        format_output(args, f"Message details: {result}")
        return

    (
        msg_id, message_id_header, subject, sender, date,
        read, flagged, junk, deleted, forwarded, replied,
        to_list, cc_list, reply_to, content, att_count,
    ) = parts[:16]

    # U+FFFC (object replacement character) appears where HTML emails embed
    # inline images. Replace with a readable placeholder.
    content = content.replace("\ufffc", "[image]")

    # Build JSON data
    data = {
        "id": int(msg_id) if msg_id.isdigit() else msg_id,
        "message_id": message_id_header,
        "account": account,
        "mailbox": mailbox,
        "subject": subject,
        "from": sender,
        "to": [a.strip() for a in to_list.rstrip(",").split(",") if a.strip()],
        "cc": [a.strip() for a in cc_list.rstrip(",").split(",") if a.strip()],
        "reply_to": reply_to or None,
        "date": date,
        "read": read.lower() == "true",
        "flagged": flagged.lower() == "true",
        "junk": junk.lower() == "true",
        "deleted": deleted.lower() == "true",
        "forwarded": forwarded.lower() == "true",
        "replied": replied.lower() == "true",
        "attachments": int(att_count) if att_count.isdigit() else 0,
        "body": truncate(content, body_limit),
    }

    # Build text output
    text = f"Message Details:\nID: {msg_id}\nMessage-ID: {message_id_header}"
    text += f"\nAccount: {account}\nMailbox: {mailbox}"
    text += f"\n\nSubject: {subject}\nFrom: {sender}\nTo: {to_list.rstrip(',')}"
    if cc_list.strip(","):
        text += f"\nCC: {cc_list.rstrip(',')}"
    if reply_to:
        text += f"\nReply-To: {reply_to}"
    text += f"\nDate: {date}"
    text += "\n\nStatus:"
    text += f"\n  Read: {read}  Flagged: {flagged}  Junk: {junk}"
    text += f"\n  Forwarded: {forwarded}  Replied: {replied}"
    text += f"\n\nAttachments: {att_count}"
    text += f"\n\n--- Body ---\n{truncate(content, body_limit)}"
    format_output(args, text, json_data=data)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def cmd_search(args) -> None:
    """Search messages by subject or sender."""
    query = args.query
    field = "sender" if getattr(args, "sender", False) else "subject"
    account = resolve_account(getattr(args, "account", None))
    mailbox = getattr(args, "mailbox", None)
    limit = validate_limit(getattr(args, "limit", DEFAULT_MESSAGE_LIMIT))

    query_escaped = escape(query)
    if mailbox and account:
        mailbox = resolve_mailbox(account, mailbox)

    if mailbox and account:
        acct_escaped = escape(account)
        mb_escaped = escape(mailbox)
        script = f"""
        tell application "Mail"
            set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
            set searchResults to (every message of mb whose {field} contains "{query_escaped}")
            set resultCount to count of searchResults
            set actualLimit to {limit}
            if resultCount < actualLimit then set actualLimit to resultCount
            if actualLimit = 0 then return ""
            set output to ""
            repeat with i from 1 to actualLimit
                set m to item i of searchResults
                set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (read status of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & "{FIELD_SEPARATOR}" & "{mb_escaped}" & "{FIELD_SEPARATOR}" & "{acct_escaped}" & linefeed
            end repeat
            return output
        end tell
        """
    elif account:
        acct_escaped = escape(account)
        script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set output to ""
            set totalFound to 0
            repeat with mb in (every mailbox of acct)
                if totalFound >= {limit} then exit repeat
                set mbName to name of mb
                set searchResults to (every message of mb whose {field} contains "{query_escaped}")
                repeat with m in searchResults
                    if totalFound >= {limit} then exit repeat
                    set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (read status of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & "{acct_escaped}" & linefeed
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
                    set searchResults to (every message of mb whose {field} contains "{query_escaped}")
                    repeat with m in searchResults
                        if totalFound >= {limit} then exit repeat
                        set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (read status of m) & "{FIELD_SEPARATOR}" & (flagged status of m) & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & acctName & linefeed
                        set totalFound to totalFound + 1
                    end repeat
                end repeat
            end repeat
            return output
        end tell
        """

    result = run(script)

    if not result.strip():
        scope = ""
        if mailbox and account:
            scope = f" in {mailbox} [{account}]"
        elif account:
            scope = f" in {account}"
        format_output(args, f"No messages found matching '{query}' in {field}{scope}.")
        return

    # Build JSON data and text output
    messages = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        msg = parse_message_line(
            line,
            ["id", "subject", "sender", "date", "read", "flagged", "mailbox", "account"],
            FIELD_SEPARATOR,
        )
        if msg is not None:
            messages.append(msg)

    save_message_aliases([m["id"] for m in messages])
    for i, m in enumerate(messages, 1):
        m["alias"] = i

    text = f"Search results for '{query}' in {field} (up to {limit}):"
    for m in messages:
        status_icons = []
        if not m["read"]:
            status_icons.append("UNREAD")
        if m["flagged"]:
            status_icons.append("FLAGGED")
        status_str = f" [{', '.join(status_icons)}]" if status_icons else ""
        text += f"\n- [{m['alias']}] {truncate(m['subject'], 50)}{status_str}"
        text += f"\n  From: {m['sender']}"
        text += f"\n  Date: {m['date']}"
        text += f"\n  Location: {m['mailbox']} [{m['account']}]"
    format_output(args, text, json_data=messages)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    """Register message listing and reading subcommands."""
    # list
    p = subparsers.add_parser("list", help="List messages in a mailbox")
    p.add_argument("-m", "--mailbox", default=None, help="Mailbox name (default: INBOX)")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--unread", action="store_true", help="Only show unread messages")
    p.add_argument("--limit", type=int, default=DEFAULT_MESSAGE_LIMIT, help="Max messages to show")
    p.add_argument("--after", help="Filter messages after date (YYYY-MM-DD)")
    p.add_argument("--before", help="Filter messages before date (YYYY-MM-DD)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_list)

    # read
    p = subparsers.add_parser("read", help="Read full message details")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--short", action="store_true", help="Truncate body to 500 chars")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_read)

    # search
    p = subparsers.add_parser("search", help="Search messages by subject or sender")
    p.add_argument("query", help="Search term")
    p.add_argument("--sender", action="store_true", help="Search in sender instead of subject")
    p.add_argument("-a", "--account", help="Limit to specific account")
    p.add_argument("-m", "--mailbox", help="Limit to specific mailbox (requires -a)")
    p.add_argument("--limit", type=int, default=DEFAULT_MESSAGE_LIMIT, help="Max results")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_search)
