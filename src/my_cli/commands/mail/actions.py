"""Message action commands: mark-read, mark-unread, flag, unflag, move, delete, unsubscribe."""

import re
import ssl
import subprocess
import urllib.request
import urllib.error

from my_cli.config import APPLESCRIPT_TIMEOUT_SHORT, FIELD_SEPARATOR, resolve_account
from my_cli.util.applescript import escape, run
from my_cli.util.applescript_templates import set_message_property
from my_cli.util.formatting import die, format_output, truncate
from my_cli.util.mail_helpers import resolve_message_context, parse_email_headers


def _mark_read_status(args, read_status: bool) -> None:
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = args.id
    read_val = "true" if read_status else "false"

    script = set_message_property(
        f'"{acct_escaped}"', f'"{mb_escaped}"', message_id,
        'read status', read_val
    )

    subject = run(script)
    status_word = "read" if read_status else "unread"
    format_output(args, f"Message '{truncate(subject, 50)}' marked as {status_word}.",
                  json_data={"id": message_id, "subject": subject, "status": status_word})


def _flag_status(args, flagged: bool) -> None:
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = args.id
    flagged_val = "true" if flagged else "false"

    script = set_message_property(
        f'"{acct_escaped}"', f'"{mb_escaped}"', message_id,
        'flagged status', flagged_val
    )

    subject = run(script)
    status_word = "flagged" if flagged else "unflagged"
    format_output(args, f"Message '{truncate(subject, 50)}' {status_word}.",
                  json_data={"id": message_id, "subject": subject, "status": status_word})


def cmd_mark_read(args) -> None:
    """Mark a message as read."""
    _mark_read_status(args, True)


def cmd_mark_unread(args) -> None:
    """Mark a message as unread."""
    _mark_read_status(args, False)


def cmd_flag(args) -> None:
    """Flag a message."""
    _flag_status(args, True)


def cmd_unflag(args) -> None:
    """Unflag a message."""
    _flag_status(args, False)


def cmd_move(args) -> None:
    """Move a message to a different mailbox."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    source = getattr(args, "from_mailbox", None)
    dest = getattr(args, "to_mailbox", None)
    if not source or not dest:
        die("Both --from and --to mailboxes are required.")
    message_id = args.id

    acct_escaped = escape(account)
    src_escaped = escape(source)
    dest_escaped = escape(dest)

    script = f"""
    tell application "Mail"
        set srcMb to mailbox "{src_escaped}" of account "{acct_escaped}"
        set destMb to mailbox "{dest_escaped}" of account "{acct_escaped}"
        set theMsg to first message of srcMb whose id is {message_id}
        set msgSubject to subject of theMsg
        move theMsg to destMb
        return msgSubject
    end tell
    """

    subject = run(script)
    format_output(args, f"Message '{truncate(subject, 50)}' moved from '{source}' to '{dest}'.",
                  json_data={"id": message_id, "subject": subject, "from": source, "to": dest})


def cmd_delete(args) -> None:
    """Delete a message by moving it to Trash."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = args.id

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        set msgSubject to subject of theMsg
        delete theMsg
        return msgSubject
    end tell
    """

    subject = run(script)
    format_output(args, f"Message '{truncate(subject, 50)}' moved to Trash.",
                  json_data={"id": message_id, "subject": subject, "status": "deleted"})


# ---------------------------------------------------------------------------
# unsubscribe — extract List-Unsubscribe and act on it
# ---------------------------------------------------------------------------



def _extract_urls(header_value: str) -> tuple[list[str], list[str]]:
    """Extract https and mailto URLs from a List-Unsubscribe header value.

    Returns (https_urls, mailto_urls).
    """
    https_urls = re.findall(r"<(https?://[^>]+)>", header_value)
    mailto_urls = re.findall(r"<(mailto:[^>]+)>", header_value)
    return https_urls, mailto_urls


def cmd_unsubscribe(args) -> None:
    """Unsubscribe from a mailing list via List-Unsubscribe header."""
    dry_run = getattr(args, "dry_run", False)
    force_open = getattr(args, "open", False)
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = args.id

    # Fetch headers + subject
    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        set subj to subject of theMsg
        set hdrs to all headers of theMsg
        return subj & "{FIELD_SEPARATOR}" & "HEADER_SPLIT" & "{FIELD_SEPARATOR}" & hdrs
    end tell
    """

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_SHORT)
    parts = result.split(FIELD_SEPARATOR + "HEADER_SPLIT" + FIELD_SEPARATOR, 1)
    subject = parts[0] if len(parts) >= 1 else "Unknown"
    raw_headers = parts[1] if len(parts) >= 2 else ""

    headers = parse_email_headers(raw_headers)

    unsub_header = headers.get("List-Unsubscribe", "")
    if isinstance(unsub_header, list):
        unsub_header = ", ".join(unsub_header)

    unsub_post = headers.get("List-Unsubscribe-Post", "")
    if isinstance(unsub_post, list):
        unsub_post = " ".join(unsub_post)

    if not unsub_header:
        format_output(args,
                      f"No unsubscribe option found for '{truncate(subject, 50)}'.\n"
                      "This email doesn't include a List-Unsubscribe header.",
                      json_data={"id": message_id, "subject": subject, "unsubscribe": False,
                                "reason": "No List-Unsubscribe header found"})
        return

    https_urls, mailto_urls = _extract_urls(unsub_header)
    one_click = bool(unsub_post and "One-Click" in unsub_post and https_urls)

    # Dry-run: just show what we found
    if dry_run:
        text = f"Unsubscribe info for '{truncate(subject, 50)}':"
        text += f"\n  One-click supported: {'Yes' if one_click else 'No'}"
        if https_urls:
            text += "\n  HTTPS URLs:"
            for u in https_urls:
                text += f"\n    {truncate(u, 100)}"
        if mailto_urls:
            text += "\n  Mailto:"
            for u in mailto_urls:
                text += f"\n    {u}"
        format_output(args, text, json_data={
            "id": message_id, "subject": subject, "one_click_supported": one_click,
            "https_urls": https_urls, "mailto_urls": mailto_urls})
        return

    # Attempt one-click unsubscribe (RFC 8058)
    if one_click and not force_open:
        url = https_urls[0]
        try:
            # Use macOS system cert bundle to avoid SSL errors with uv Python
            ctx = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
            req = urllib.request.Request(
                url,
                data=b"List-Unsubscribe=One-Click",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=APPLESCRIPT_TIMEOUT_SHORT, context=ctx)
            status = resp.status
            format_output(args,
                          f"Unsubscribed from '{truncate(subject, 50)}' via one-click (HTTP {status}).",
                          json_data={"id": message_id, "subject": subject, "unsubscribed": True,
                                    "method": "one-click", "status_code": status})
            return
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            # One-click failed, fall through to browser
            err_msg = str(e)
            if not getattr(args, "json", False):
                print(f"One-click failed ({err_msg}), opening in browser instead...")

    # Fall back to opening HTTPS URL in browser
    if https_urls:
        url = https_urls[0]
        subprocess.run(["open", url], check=False)
        format_output(args,
                      f"Opened unsubscribe page for '{truncate(subject, 50)}' in browser.",
                      json_data={"id": message_id, "subject": subject, "unsubscribed": "pending",
                                "method": "browser", "url": url})
        return

    # Only mailto available
    if mailto_urls:
        addr = mailto_urls[0].replace("mailto:", "")
        format_output(args,
                      f"No HTTPS unsubscribe link. Mailto only:\n  {addr}\n"
                      "Send an email to that address to unsubscribe.",
                      json_data={"id": message_id, "subject": subject, "unsubscribed": False,
                                "method": "mailto_only", "mailto": addr})
        return


# ---------------------------------------------------------------------------
# junk / not-junk
# ---------------------------------------------------------------------------

def cmd_junk(args) -> None:
    """Mark a message as junk or spam."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = args.id

    script = set_message_property(
        f'"{acct_escaped}"', f'"{mb_escaped}"', message_id,
        'junk mail status', 'true'
    )

    subject = run(script)
    format_output(
        args,
        f"Message '{truncate(subject, 50)}' marked as junk.",
        json_data={"id": message_id, "subject": subject, "status": "junk"}
    )


def cmd_not_junk(args) -> None:
    """Mark a message as not junk and move it back to INBOX."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    message_id = args.id

    acct_escaped = escape(account)

    # Find the message in Junk mailbox and move back to INBOX
    script = f"""
    tell application "Mail"
        set acct to account "{acct_escaped}"
        set junkMb to mailbox "Junk" of acct
        set inboxMb to mailbox "INBOX" of acct
        set theMsg to first message of junkMb whose id is {message_id}
        set msgSubject to subject of theMsg
        set junk mail status of theMsg to false
        move theMsg to inboxMb
        return msgSubject
    end tell
    """

    subject = run(script)
    format_output(
        args,
        f"Message '{truncate(subject, 50)}' marked as not junk and moved to INBOX.",
        json_data={"id": message_id, "subject": subject, "status": "not_junk", "moved_to": "INBOX"}
    )


def cmd_open(args) -> None:
    """Open a message in Mail.app."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = args.id

    script = f"""
    tell application "Mail"
        set theMb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to (first message of theMb whose id is {message_id})
        set msgSubject to subject of theMsg
        if (count of message viewers) is 0 then
            make new message viewer
        end if
        set selected mailboxes of first message viewer to {{theMb}}
        set selected messages of first message viewer to {{theMsg}}
        activate
        return msgSubject
    end tell
    """

    subject = run(script)
    format_output(
        args,
        f"Opened message {message_id} in Mail.app",
        json_data={
            "opened": True,
            "message_id": message_id,
            "account": account,
            "mailbox": mailbox,
            "subject": subject,
        },
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    """Register message action subcommands."""
    # mark-read
    p = subparsers.add_parser("mark-read", help="Mark message as read")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_mark_read)

    # mark-unread
    p = subparsers.add_parser("mark-unread", help="Mark message as unread")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_mark_unread)

    # flag
    p = subparsers.add_parser("flag", help="Flag a message")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_flag)

    # unflag
    p = subparsers.add_parser("unflag", help="Unflag a message")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_unflag)

    # move
    p = subparsers.add_parser("move", help="Move message to different mailbox")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--from", dest="from_mailbox", required=True, help="Source mailbox")
    p.add_argument("--to", dest="to_mailbox", required=True, help="Destination mailbox")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_move)

    # delete
    p = subparsers.add_parser("delete", help="Delete message (move to Trash)")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_delete)

    # unsubscribe
    p = subparsers.add_parser("unsubscribe", help="Unsubscribe from a mailing list")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--dry-run", action="store_true", help="Show unsubscribe links without acting")
    p.add_argument("--open", action="store_true", help="Force open in browser (skip one-click)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_unsubscribe)

    # junk
    p = subparsers.add_parser("junk", help="Mark message as junk/spam")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_junk)

    # not-junk
    p = subparsers.add_parser("not-junk", help="Mark message as not junk and move to INBOX")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_not_junk)

    # open
    p = subparsers.add_parser("open", help="Open message in Mail.app")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_open)
