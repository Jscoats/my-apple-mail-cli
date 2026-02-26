"""Composite mail commands built on core: export, thread, reply, forward."""

import os
import re
from email.utils import parseaddr

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_BATCH,
    APPLESCRIPT_TIMEOUT_LONG,
    DEFAULT_MAILBOX,
    FIELD_SEPARATOR,
    MAX_EXPORT_BULK_LIMIT,
    RECORD_SEPARATOR,
    resolve_account,
    save_message_aliases,
)
from mxctl.util.applescript import escape, run, validate_msg_id
from mxctl.util.formatting import die, format_output, truncate
from mxctl.util.mail_helpers import extract_email, normalize_subject, parse_message_line

# ---------------------------------------------------------------------------
# export — save message(s) as markdown
# ---------------------------------------------------------------------------


def export_message(
    account: str,
    mailbox: str,
    message_id: int,
    dest: str,
) -> dict:
    """Export a single message as a markdown file. Returns dict with path and subject."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

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

    subject, sender, date, to_list, content = parts[:5]

    # Build markdown
    safe_subject = re.sub(r"[^\w\s-]", "", subject).strip().replace(" ", "-")[:60]
    filename = f"{safe_subject}.md" if safe_subject else f"message-{message_id}.md"

    md = f"# {subject}\n\n"
    md += f"**From:** {sender}  \n"
    md += f"**To:** {to_list.rstrip(', ')}  \n"
    md += f"**Date:** {date}  \n\n"
    md += "---\n\n"
    md += content

    dest_path = os.path.expanduser(dest)
    if os.path.isdir(dest_path):
        filepath = os.path.join(dest_path, filename)
        # Guard against path traversal in the generated filename
        real_filepath = os.path.realpath(os.path.abspath(filepath))
        real_dest = os.path.realpath(os.path.abspath(dest_path))
        if (
            not real_filepath.startswith(real_dest + os.sep) and real_filepath != real_dest
        ):  # pragma: no cover — re.sub strips dangerous chars before this
            die("Unsafe export filename: path traversal detected.")
    else:
        filepath = dest_path

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    return {"path": filepath, "subject": subject}


def export_messages(
    account: str,
    mailbox: str,
    dest: str,
    after: str | None = None,
) -> dict:
    """Export messages from a mailbox as markdown files. Returns dict with directory and count."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    whose = ""
    if after:
        from mxctl.util.dates import parse_date, to_applescript_date

        dt = parse_date(after)
        whose = f'whose date received >= date "{to_applescript_date(dt)}"'

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set msgs to (every message of mb {whose})
        set ct to count of msgs
        set cap to {MAX_EXPORT_BULK_LIMIT}
        if ct < cap then set cap to ct
        set output to ""
        repeat with i from 1 to cap
            set m to item i of msgs
            set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & (content of m) & "{RECORD_SEPARATOR}" & linefeed
        end repeat
        return output
    end tell
    """

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_BATCH)
    dest_dir = os.path.expanduser(dest)
    os.makedirs(dest_dir, exist_ok=True)

    entries = result.split(RECORD_SEPARATOR)
    exported = 0
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(FIELD_SEPARATOR)
        if len(parts) < 5:
            continue
        msg_id, subject, sender, date, content = parts[0], parts[1], parts[2], parts[3], FIELD_SEPARATOR.join(parts[4:])

        safe_subject = re.sub(r"[^\w\s-]", "", subject).strip().replace(" ", "-")[:50]
        filename = f"{safe_subject}-{msg_id}.md" if safe_subject else f"message-{msg_id}.md"

        filepath = os.path.join(dest_dir, filename)
        real_filepath = os.path.realpath(os.path.abspath(filepath))
        real_dest = os.path.realpath(os.path.abspath(dest_dir))
        if (
            not real_filepath.startswith(real_dest + os.sep) and real_filepath != real_dest
        ):  # pragma: no cover — re.sub strips dangerous chars before this
            continue

        md = f"# {subject}\n\n**From:** {sender}  \n**Date:** {date}\n\n---\n\n{content}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        exported += 1

    return {"directory": dest_dir, "exported": exported}


# Legacy private wrappers kept for test compatibility
def _export_single(args, msg_id: int, account: str, mailbox: str, dest: str) -> None:
    data = export_message(account, mailbox, msg_id, dest)
    format_output(args, f"Exported to: {data['path']}", json_data=data)


def _export_bulk(args, mailbox: str, account: str, dest: str, after: str | None) -> None:
    data = export_messages(account, mailbox, dest, after)
    format_output(
        args,
        f"Exported {data['exported']} messages to {data['directory']}",
        json_data=data,
    )


def cmd_export(args) -> None:
    """Export message(s) as markdown files."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")

    target = args.target  # could be a message ID or mailbox name
    dest = args.to
    after = getattr(args, "after", None)

    # If target is numeric, it's a single message export
    if target.isdigit():
        mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
        data = export_message(account, mailbox, int(target), dest)
        format_output(args, f"Exported to: {data['path']}", json_data=data)
    else:
        data = export_messages(account, target, dest, after)
        format_output(
            args,
            f"Exported {data['exported']} messages to {data['directory']}",
            json_data=data,
        )


# ---------------------------------------------------------------------------
# thread — show conversation thread
# ---------------------------------------------------------------------------


def get_thread(
    account: str,
    mailbox: str,
    message_id: int,
    limit: int = 100,
    all_accounts: bool = False,
) -> dict:
    """Fetch thread messages for a given message. Returns dict with thread_subject and messages list."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    # Get the subject to find related messages
    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        return subject of theMsg
    end tell
    """
    subject = run(script)

    # Strip Re:/Fwd: prefixes to get the thread subject
    thread_subject = normalize_subject(subject)
    thread_escaped = escape(thread_subject)

    # Search for messages with this subject (default: current account only)
    if all_accounts:
        acct_loop = "repeat with acct in (every account)\nset acctName to name of acct"
        acct_loop_end = "end repeat"
    else:
        acct_loop = f'set acct to account "{acct_escaped}"\nset acctName to name of acct'
        acct_loop_end = ""

    script2 = f"""
    tell application "Mail"
        set output to ""
        set totalFound to 0
        {acct_loop}
            repeat with mbox in (mailboxes of acct)
                if totalFound >= {limit} then exit repeat
                set mbName to name of mbox
                set msgs to (every message of mbox whose subject contains "{thread_escaped}")
                repeat with m in msgs
                    if totalFound >= {limit} then exit repeat
                    set output to output & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & acctName & linefeed
                    set totalFound to totalFound + 1
                end repeat
            end repeat
        {acct_loop_end}
        return output
    end tell
    """

    result = run(script2, timeout=APPLESCRIPT_TIMEOUT_LONG)

    messages = []
    if result.strip():
        for line in result.strip().split("\n"):
            if not line.strip():
                continue
            msg = parse_message_line(line, ["id", "subject", "sender", "date", "mailbox", "account"], FIELD_SEPARATOR)
            if msg is not None:
                messages.append(msg)

    return {"thread_subject": thread_subject, "messages": messages}


def cmd_thread(args) -> None:
    """Show full conversation thread for a message."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    message_id = validate_msg_id(args.id)
    limit = getattr(args, "limit", 100)
    all_accounts = getattr(args, "all_accounts", False)

    data = get_thread(account, mailbox, message_id, limit=limit, all_accounts=all_accounts)
    thread_subject = data["thread_subject"]
    messages = data["messages"]

    if not messages:
        format_output(args, f"No thread found for '{thread_subject}'.", json_data=data)
        return

    save_message_aliases([m["id"] for m in messages])
    for i, m in enumerate(messages, 1):
        m["alias"] = i

    text = f"Thread: {thread_subject} ({len(messages)} messages):"
    for m in messages:
        text += f"\n  [{m['alias']}] {truncate(m['subject'], 50)}"
        text += f"\n    From: {m['sender']}  Date: {m['date']}"
    format_output(args, text, json_data=messages)


# ---------------------------------------------------------------------------
# reply — create a reply draft
# ---------------------------------------------------------------------------


def create_reply(
    account: str,
    mailbox: str,
    message_id: int,
    body: str,
) -> dict:
    """Create a reply draft for a message. Returns dict with status, to, and subject."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    # Get original message details
    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        set msgSubject to subject of theMsg
        set msgSender to sender of theMsg
        set msgDate to date received of theMsg
        set msgContent to content of theMsg
        return msgSubject & "{FIELD_SEPARATOR}" & msgSender & "{FIELD_SEPARATOR}" & msgDate & "{FIELD_SEPARATOR}" & msgContent
    end tell
    """

    result = run(script)
    parts = result.split(FIELD_SEPARATOR)
    if len(parts) < 4:
        die("Failed to read original message.")

    orig_subject, orig_sender, orig_date, orig_content = parts[0], parts[1], parts[2], FIELD_SEPARATOR.join(parts[3:])

    reply_subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
    # Extract email from sender
    reply_to = extract_email(orig_sender)
    if not reply_to or "@" not in reply_to:
        die(f"Cannot determine reply address from sender: '{orig_sender}'")

    # Build reply body with quote
    quoted = "\n".join(f"> {line}" for line in orig_content.split("\n")[:20])
    full_body = f"{body}\n\nOn {orig_date}, {orig_sender} wrote:\n{quoted}"

    body_escaped = escape(full_body)
    subject_escaped = escape(reply_subject)
    reply_to_escaped = escape(reply_to)

    draft_script = f"""
    tell application "Mail"
        set emailAddrs to get (email addresses of account "{acct_escaped}")
        if class of emailAddrs is list then
            set senderEmail to item 1 of emailAddrs
        else
            set senderEmail to emailAddrs
        end if
        set newMsg to make new outgoing message with properties {{subject:"{subject_escaped}", content:"{body_escaped}", visible:true}}
        tell newMsg
            set sender to senderEmail
            make new to recipient at end of to recipients with properties {{address:"{reply_to_escaped}"}}
        end tell
        return "draft created"
    end tell
    """

    run(draft_script)

    return {"status": "reply_draft_created", "to": reply_to, "subject": reply_subject}


def cmd_reply(args) -> None:
    """Create a reply draft for a message."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    message_id = validate_msg_id(args.id)
    body = args.body

    data = create_reply(account, mailbox, message_id, body)
    format_output(
        args,
        f"Reply draft created.\nTo: {data['to']}\nSubject: {data['subject']}\n\nOpen in Mail.app to review and send.",
        json_data=data,
    )


# ---------------------------------------------------------------------------
# forward — create a forward draft
# ---------------------------------------------------------------------------


def create_forward(
    account: str,
    mailbox: str,
    message_id: int,
    to_addr: str,
) -> dict:
    """Create a forward draft for a message. Returns dict with status, to, and subject."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        set msgSubject to subject of theMsg
        set msgSender to sender of theMsg
        set msgDate to date received of theMsg
        set msgContent to content of theMsg
        return msgSubject & "{FIELD_SEPARATOR}" & msgSender & "{FIELD_SEPARATOR}" & msgDate & "{FIELD_SEPARATOR}" & msgContent
    end tell
    """

    result = run(script)
    parts = result.split(FIELD_SEPARATOR)
    if len(parts) < 4:
        die("Failed to read original message.")

    orig_subject, orig_sender, orig_date, orig_content = parts[0], parts[1], parts[2], FIELD_SEPARATOR.join(parts[3:])

    fwd_subject = f"Fwd: {orig_subject}" if not orig_subject.lower().startswith("fwd:") else orig_subject
    fwd_body = f"---------- Forwarded message ----------\nFrom: {orig_sender}\nDate: {orig_date}\nSubject: {orig_subject}\n\n{orig_content}"

    # Extract email from to_addr (handles both bare and formatted addresses)
    _, to_email = parseaddr(to_addr)
    if not to_email or "@" not in to_email:
        die(f"Cannot determine forward address from: '{to_addr}'")

    body_escaped = escape(fwd_body)
    subject_escaped = escape(fwd_subject)
    to_escaped = escape(to_email)

    draft_script = f"""
    tell application "Mail"
        set emailAddrs to get (email addresses of account "{acct_escaped}")
        if class of emailAddrs is list then
            set senderEmail to item 1 of emailAddrs
        else
            set senderEmail to emailAddrs
        end if
        set newMsg to make new outgoing message with properties {{subject:"{subject_escaped}", content:"{body_escaped}", visible:true}}
        tell newMsg
            set sender to senderEmail
            make new to recipient at end of to recipients with properties {{address:"{to_escaped}"}}
        end tell
        return "draft created"
    end tell
    """

    run(draft_script)

    return {"status": "forward_draft_created", "to": to_addr, "subject": fwd_subject}


def cmd_forward(args) -> None:
    """Create a forward draft for a message."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    message_id = validate_msg_id(args.id)
    to_addr = args.to

    data = create_forward(account, mailbox, message_id, to_addr)
    format_output(
        args,
        f"Forward draft created.\nTo: {to_addr}\nSubject: {data['subject']}\n\nOpen in Mail.app to review and send.",
        json_data=data,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register composite mail subcommands."""
    # export
    p = subparsers.add_parser("export", help="Export message(s) as markdown")
    p.add_argument("target", help="Message ID (single) or mailbox name (bulk)")
    p.add_argument("--to", required=True, help="Destination path or directory")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox for single message export (default: INBOX)")
    p.add_argument("--after", help="For bulk export: only messages after date (YYYY-MM-DD)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_export)

    # thread
    p = subparsers.add_parser("thread", help="Show full conversation thread")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--limit", type=int, default=100, help="Max thread messages (default: 100)")
    p.add_argument("--all-accounts", action="store_true", help="Search all accounts (default: current only)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_thread)

    # reply
    p = subparsers.add_parser("reply", help="Create a reply draft")
    p.add_argument("id", type=int, help="Message ID to reply to")
    p.add_argument("--body", required=True, help="Reply text")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_reply)

    # forward
    p = subparsers.add_parser("forward", help="Create a forward draft")
    p.add_argument("id", type=int, help="Message ID to forward")
    p.add_argument("--to", required=True, help="Recipient email")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_forward)
