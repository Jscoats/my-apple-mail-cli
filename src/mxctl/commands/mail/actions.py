"""Message action commands: mark-read, mark-unread, flag, unflag, move, delete, unsubscribe."""

import ipaddress
import re
import socket
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from mxctl.config import APPLESCRIPT_TIMEOUT_SHORT, FIELD_SEPARATOR, resolve_account
from mxctl.util.applescript import escape, run, validate_msg_id
from mxctl.util.applescript_templates import set_message_property
from mxctl.util.formatting import die, format_output, truncate
from mxctl.util.mail_helpers import parse_email_headers, resolve_mailbox, resolve_message_context

# ---------------------------------------------------------------------------
# Data functions (plain args, return dicts, no printing)
# ---------------------------------------------------------------------------


def set_read_status(account: str, mailbox: str, message_id: int, read_status: bool) -> dict:
    """Mark a message as read or unread. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)
    read_val = "true" if read_status else "false"

    script = set_message_property(f'"{acct_escaped}"', f'"{mb_escaped}"', message_id, "read status", read_val)

    subject = run(script)
    status_word = "read" if read_status else "unread"
    return {"id": message_id, "subject": subject, "status": status_word, "account": account, "mailbox": mailbox}


def set_flag_status(account: str, mailbox: str, message_id: int, flagged: bool) -> dict:
    """Mark a message as flagged or unflagged. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)
    flagged_val = "true" if flagged else "false"

    script = set_message_property(f'"{acct_escaped}"', f'"{mb_escaped}"', message_id, "flagged status", flagged_val)

    subject = run(script)
    status_word = "flagged" if flagged else "unflagged"
    return {"id": message_id, "subject": subject, "status": status_word, "account": account, "mailbox": mailbox}


def move_message(account: str, source_mailbox: str, message_id: int, dest_mailbox: str) -> dict:
    """Move a message to a different mailbox. Returns result dict."""
    acct_escaped = escape(account)
    src_escaped = escape(source_mailbox)
    dest_escaped = escape(dest_mailbox)

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
    return {"id": message_id, "subject": subject, "from": source_mailbox, "to": dest_mailbox, "account": account}


def delete_message(account: str, mailbox: str, message_id: int) -> dict:
    """Delete a message by moving it to Trash. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

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
    return {"id": message_id, "subject": subject, "status": "deleted", "account": account, "mailbox": mailbox}


def mark_junk(account: str, mailbox: str, message_id: int) -> dict:
    """Mark a message as junk. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    script = set_message_property(f'"{acct_escaped}"', f'"{mb_escaped}"', message_id, "junk mail status", "true")

    subject = run(script)
    return {"id": message_id, "subject": subject, "status": "junk", "account": account, "mailbox": mailbox}


def open_message(account: str, mailbox: str, message_id: int) -> dict:
    """Open a message in Mail.app. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

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
    return {"opened": True, "message_id": message_id, "account": account, "mailbox": mailbox, "subject": subject}


# ---------------------------------------------------------------------------
# CLI handler helpers (take args, call data functions, print)
# ---------------------------------------------------------------------------


def _mark_read_status(args, read_status: bool) -> None:
    account, mailbox, _, _ = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    result = set_read_status(account, mailbox, message_id, read_status)
    status_word = result["status"]
    format_output(args, f"Message '{truncate(result['subject'], 50)}' marked as {status_word}.", json_data=result)


def _flag_status(args, flagged: bool) -> None:
    account, mailbox, _, _ = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    result = set_flag_status(account, mailbox, message_id, flagged)
    status_word = result["status"]
    format_output(args, f"Message '{truncate(result['subject'], 50)}' {status_word}.", json_data=result)


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
    message_id = validate_msg_id(args.id)

    source = resolve_mailbox(account, source)
    dest = resolve_mailbox(account, dest)

    result = move_message(account, source, message_id, dest)
    format_output(args, f"Message '{truncate(result['subject'], 50)}' moved from '{source}' to '{dest}'.", json_data=result)


def cmd_delete(args) -> None:
    """Delete a message by moving it to Trash."""
    account, mailbox, _, _ = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    result = delete_message(account, mailbox, message_id)
    format_output(args, f"Message '{truncate(result['subject'], 50)}' moved to Trash.", json_data=result)


# ---------------------------------------------------------------------------
# unsubscribe — extract List-Unsubscribe and act on it
# ---------------------------------------------------------------------------


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private_url(url: str) -> bool:
    """Return True if the URL resolves to a private or loopback address."""
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        addr = ipaddress.ip_address(socket.gethostbyname(hostname))
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except (OSError, ValueError):
        # DNS failure or invalid address — block to be safe
        return True


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
    message_id = validate_msg_id(args.id)

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
        format_output(
            args,
            f"No unsubscribe option found for '{truncate(subject, 50)}'.\nThis email doesn't include a List-Unsubscribe header.",
            json_data={"id": message_id, "subject": subject, "unsubscribe": False, "reason": "No List-Unsubscribe header found"},
        )
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
        format_output(
            args,
            text,
            json_data={
                "id": message_id,
                "subject": subject,
                "one_click_supported": one_click,
                "https_urls": https_urls,
                "mailto_urls": mailto_urls,
            },
        )
        return

    # Attempt one-click unsubscribe (RFC 8058)
    if one_click and not force_open:
        url = https_urls[0]
        if _is_private_url(url):
            die(f"Refused to POST to private/internal address: {url}")
        try:
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
            format_output(
                args,
                f"Unsubscribed from '{truncate(subject, 50)}' via one-click (HTTP {status}).",
                json_data={"id": message_id, "subject": subject, "unsubscribed": True, "method": "one-click", "status_code": status},
            )
            return
        except (urllib.error.URLError, OSError) as e:
            # One-click failed, fall through to browser
            err_msg = str(e)
            if not getattr(args, "json", False):
                print(f"One-click failed ({err_msg}), opening in browser instead...")

    # Fall back to opening HTTPS URL in browser
    if https_urls:
        url = https_urls[0]
        subprocess.run(["open", url], check=False)
        format_output(
            args,
            f"Opened unsubscribe page for '{truncate(subject, 50)}' in browser.",
            json_data={"id": message_id, "subject": subject, "unsubscribed": "pending", "method": "browser", "url": url},
        )
        return

    # Only mailto available
    if mailto_urls:
        addr = mailto_urls[0].replace("mailto:", "")
        format_output(
            args,
            f"No HTTPS unsubscribe link. Mailto only:\n  {addr}\nSend an email to that address to unsubscribe.",
            json_data={"id": message_id, "subject": subject, "unsubscribed": False, "method": "mailto_only", "mailto": addr},
        )
        return


# ---------------------------------------------------------------------------
# junk / not-junk
# ---------------------------------------------------------------------------


def cmd_junk(args) -> None:
    """Mark a message as junk or spam."""
    import sys

    account, mailbox, _, _ = resolve_message_context(args)
    message_id = validate_msg_id(args.id)

    # Run the AppleScript; if message not found, give a cross-account hint
    try:
        result = mark_junk(account, mailbox, message_id)
    except SystemExit:
        # mark_junk() already printed the error; add an actionable hint and re-raise
        explicit_account = getattr(args, "account", None)
        if not explicit_account:
            print(
                "Hint: If this message belongs to another account, use -a ACCOUNT.\n      Run `mxctl accounts` to see account names.",
                file=sys.stderr,
            )
        raise

    format_output(
        args,
        f"Message '{truncate(result['subject'], 50)}' marked as junk.",
        json_data=result,
    )


def _try_not_junk_in_mailbox(
    acct_escaped: str, junk_escaped: str, inbox_escaped: str, message_id: int, subject: str = "", sender: str = ""
) -> str | None:
    """Try to mark a message as not-junk from a specific mailbox.

    Uses subprocess directly so that individual mailbox attempts can fail silently
    (returning None) without calling sys.exit. The module-level run() always exits
    on error, which would prevent trying fallback mailboxes.

    When subject and sender are provided, searches by subject+sender in the junk
    mailbox (because AppleScript message IDs are mailbox-specific and become invalid
    after a cross-mailbox move). Falls back to ID-based lookup only when no
    subject/sender context is available.

    Returns the message subject string on success, None if the message or mailbox
    was not found.
    """
    import subprocess as _subprocess

    if subject and sender:
        # Search by subject + sender — avoids stale-ID problem after cross-mailbox moves
        subj_esc = escape(subject)
        sender_esc = escape(sender)
        script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set junkMb to mailbox "{junk_escaped}" of acct
            set inboxMb to mailbox "{inbox_escaped}" of acct
            set theMsg to first message of junkMb whose (subject is "{subj_esc}" and sender is "{sender_esc}")
            set msgSubject to subject of theMsg
            set junk mail status of theMsg to false
            move theMsg to inboxMb
            return msgSubject
        end tell
        """
    else:
        # Fallback: look up by numeric ID (works if the message hasn't moved mailboxes)
        script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set junkMb to mailbox "{junk_escaped}" of acct
            set inboxMb to mailbox "{inbox_escaped}" of acct
            set theMsg to first message of junkMb whose id is {message_id}
            set msgSubject to subject of theMsg
            set junk mail status of theMsg to false
            move theMsg to inboxMb
            return msgSubject
        end tell
        """
    result = _subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    err_lower = result.stderr.strip().lower()
    if "can't get message" in err_lower or "can't get mailbox" in err_lower or "no messages matched" in err_lower:
        return None
    # Unexpected error — return None silently (don't leak internal AppleScript errors to user)
    return None


def not_junk(account: str, message_id: int, custom_mailbox: str | None = None) -> dict:
    """Mark a message as not junk and move it back to INBOX.

    Searches the Junk mailbox (and Gmail [Gmail]/Spam for Gmail accounts) because
    AppleScript message IDs become invalid in the original mailbox once a message
    is moved to Junk.

    Uses subject+sender search (not ID) to find the message in the junk folder,
    since IDs are mailbox-specific and become stale after a cross-mailbox move.
    If custom_mailbox is given, only that mailbox is tried.

    Returns a result dict on success, or raises SystemExit on failure.
    """
    import sys

    acct_escaped = escape(account)
    inbox_mailbox = resolve_mailbox(account, "INBOX")
    inbox_escaped = escape(inbox_mailbox)

    # Try to fetch the original message details (subject + sender) so we can
    # search by content in the junk folder.  This succeeds when called immediately
    # after cmd_junk (the original INBOX message is still accessible by ID before
    # the AppleScript cache expires), and fails gracefully after a restart.
    orig_subject = ""
    orig_sender = ""
    try:
        import subprocess as _subprocess

        fetch_script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set inboxMb to mailbox "{inbox_escaped}" of acct
            set theMsg to first message of inboxMb whose id is {message_id}
            return (subject of theMsg) & "{FIELD_SEPARATOR}" & (sender of theMsg)
        end tell
        """
        fetch_result = _subprocess.run(
            ["osascript", "-e", fetch_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if fetch_result.returncode == 0:
            parts = fetch_result.stdout.strip().split(FIELD_SEPARATOR, 1)
            if len(parts) == 2:
                orig_subject, orig_sender = parts[0], parts[1]
    except Exception:
        pass  # Non-fatal — fall back to ID-based lookup below

    if custom_mailbox:
        # User explicitly specified where to look — trust them, single attempt
        candidates = [resolve_mailbox(account, custom_mailbox)]
    else:
        # Build a prioritized list of junk folder candidates
        junk_primary = resolve_mailbox(account, "Junk")
        candidates = [junk_primary]
        from mxctl.config import get_gmail_accounts

        if account in get_gmail_accounts():
            if "[Gmail]/Spam" not in candidates:
                candidates.append("[Gmail]/Spam")
            # Gmail's label architecture means messages may only be findable via All Mail
            if "[Gmail]/All Mail" not in candidates:
                candidates.append("[Gmail]/All Mail")
        else:
            # For non-Gmail accounts also try "Spam" as an alias
            if "Spam" not in candidates:
                candidates.append("Spam")

    # Try each candidate mailbox until the message is found
    for junk_mailbox in candidates:
        junk_escaped = escape(junk_mailbox)
        subject = _try_not_junk_in_mailbox(
            acct_escaped,
            junk_escaped,
            inbox_escaped,
            message_id,
            subject=orig_subject,
            sender=orig_sender,
        )
        if subject is not None:
            return {"id": message_id, "subject": subject, "status": "not_junk", "moved_to": "INBOX"}

    # All candidates failed — message not found in any junk folder
    tried = ", ".join(f'"{m}"' for m in candidates)
    print(
        f"Error: Message {message_id} not found in junk folder(s) ({tried}).\n"
        "The message may have already been moved, or use -m MAILBOX to specify its location.",
        file=sys.stderr,
    )
    sys.exit(1)


def cmd_not_junk(args) -> None:
    """Mark a message as not junk and move it back to INBOX.

    Searches the Junk mailbox (and Gmail [Gmail]/Spam for Gmail accounts) because
    AppleScript message IDs become invalid in the original mailbox once a message
    is moved to Junk.

    Uses subject+sender search (not ID) to find the message in the junk folder,
    since IDs are mailbox-specific and become stale after a cross-mailbox move.
    If a custom -m MAILBOX is given, only that mailbox is tried.
    """
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    message_id = validate_msg_id(args.id)
    custom_mailbox = getattr(args, "mailbox", None)

    result = not_junk(account, message_id, custom_mailbox=custom_mailbox)
    format_output(
        args,
        f"Message '{truncate(result['subject'], 50)}' marked as not junk and moved to INBOX.",
        json_data=result,
    )


def cmd_open(args) -> None:
    """Open a message in Mail.app."""
    account, mailbox, _, _ = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    result = open_message(account, mailbox, message_id)
    format_output(
        args,
        f"Opened message {message_id} in Mail.app",
        json_data=result,
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
    p.add_argument("-m", "--mailbox", help="Source mailbox (default: Junk)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_not_junk)

    # open
    p = subparsers.add_parser("open", help="Open message in Mail.app")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_open)
