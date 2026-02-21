"""System mail commands: check, headers, rules, signatures, junk, not-junk."""

from my_cli.config import (
    DEFAULT_MAILBOX,
    FIELD_SEPARATOR,
    resolve_account,
)
from my_cli.util.applescript import escape, run
from my_cli.util.formatting import die, format_output, truncate
from my_cli.util.mail_helpers import parse_email_headers


# ---------------------------------------------------------------------------
# check — trigger mail fetch
# ---------------------------------------------------------------------------

def cmd_check(args) -> None:
    """Trigger Mail.app to check for new mail."""
    script = """
    tell application "Mail"
        check for new mail
        return "ok"
    end tell
    """
    run(script)
    format_output(args, "Mail check triggered.", json_data={"status": "checked"})


# ---------------------------------------------------------------------------
# headers
# ---------------------------------------------------------------------------

def cmd_headers(args) -> None:
    """Show email headers with authentication details."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    message_id = args.id

    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        return all headers of theMsg
    end tell
    """

    result = run(script)
    raw = getattr(args, "raw", False)

    if raw:
        print(result)
        return

    # Parse all headers
    headers = parse_email_headers(result)

    # Extract useful info
    from_addr = headers.get("From", "?")
    to_addr = headers.get("To", "?")
    subject = headers.get("Subject", "?")
    date = headers.get("Date", "?")
    msg_id = headers.get("Message-Id") or headers.get("Message-ID", "?")
    reply_to = headers.get("Reply-To", "")
    in_reply_to = headers.get("In-Reply-To", "")
    list_unsubscribe = headers.get("List-Unsubscribe", "")

    # Authentication summary
    auth_results = headers.get("Authentication-Results", "")
    if isinstance(auth_results, list):
        auth_results = " | ".join(auth_results)
    spf = "?"
    dkim = "?"
    dmarc = "?"
    if "spf=pass" in auth_results:
        spf = "pass"
    elif "spf=fail" in auth_results:
        spf = "FAIL"
    elif "spf=softfail" in auth_results:
        spf = "softfail"
    if "dkim=pass" in auth_results:
        dkim = "pass"
    elif "dkim=fail" in auth_results:
        dkim = "FAIL"
    if "dmarc=pass" in auth_results:
        dmarc = "pass"
    elif "dmarc=fail" in auth_results:
        dmarc = "FAIL"

    # Count hops
    received = headers.get("Received", [])
    if isinstance(received, str):
        received = [received]
    hops = len(received)

    # Return path (bounce address)
    return_path = headers.get("Return-Path", "")

    text = f"From: {from_addr}\nTo: {to_addr}\nSubject: {subject}\nDate: {date}\nMessage-ID: {msg_id}"
    if reply_to:
        text += f"\nReply-To: {reply_to}"
    if in_reply_to:
        text += f"\nIn-Reply-To: {in_reply_to}"
    if return_path:
        text += f"\nReturn-Path: {return_path}"
    text += f"\n\nAuth: SPF={spf}  DKIM={dkim}  DMARC={dmarc}"
    text += f"\nHops: {hops}"
    if list_unsubscribe:
        text += f"\nUnsubscribe: {truncate(list_unsubscribe, 80)}"
    format_output(args, text, json_data=headers)


# ---------------------------------------------------------------------------
# rules — list/enable/disable/apply mail rules
# ---------------------------------------------------------------------------

def cmd_rules(args) -> None:
    """List or manage mail rules."""
    action = getattr(args, "action", None)
    rule_name = getattr(args, "rule_name", None)
    _mailbox = getattr(args, "mailbox", None)  # noqa: F841

    if action == "enable" and rule_name:
        _toggle_rule(args, rule_name, True)
    elif action == "disable" and rule_name:
        _toggle_rule(args, rule_name, False)
    else:
        _list_rules(args)


def _list_rules(args) -> None:
    script = """
    tell application "Mail"
        set output to ""
        repeat with r in (every rule)
            set rName to name of r
            set rEnabled to enabled of r
            set output to output & rName & "{FIELD_SEPARATOR}" & rEnabled & linefeed
        end repeat
        return output
    end tell
    """
    result = run(script)
    if not result.strip():
        format_output(args, "No mail rules found.")
        return

    rules = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 2:
            rules.append({"name": parts[0], "enabled": parts[1].lower() == "true"})

    text = "Mail Rules:"
    for rule in rules:
        status = "ON" if rule["enabled"] else "OFF"
        text += f"\n  [{status}] {rule['name']}"
    format_output(args, text, json_data=rules)


def _toggle_rule(args, name: str, enabled: bool) -> None:
    name_escaped = escape(name)
    val = "true" if enabled else "false"
    script = f"""
    tell application "Mail"
        set r to first rule whose name is "{name_escaped}"
        set enabled of r to {val}
        return name of r
    end tell
    """
    result = run(script)
    word = "enabled" if enabled else "disabled"
    format_output(args, f"Rule '{result}' {word}.", json_data={"rule": result, "status": word})


# ---------------------------------------------------------------------------
# signatures
# ---------------------------------------------------------------------------

def cmd_signatures(args) -> None:
    """List email signatures."""
    # AppleScript doesn't have great signature access, but we can try
    script = """
    tell application "Mail"
        set output to ""
        repeat with sig in (every signature)
            set sigName to name of sig
            set output to output & sigName & linefeed
        end repeat
        return output
    end tell
    """
    result = run(script)
    if not result.strip():
        format_output(args, "No signatures found.")
        return

    sigs = [s.strip() for s in result.strip().split("\n") if s.strip()]
    text = "Email Signatures:"
    for s in sigs:
        text += f"\n  - {s}"
    format_output(args, text, json_data=sigs)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    """Register system mail subcommands."""
    p = subparsers.add_parser("check", help="Trigger fetch for new mail")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_check)

    p = subparsers.add_parser("headers", help="Email header summary (auth, hops, reply-to)")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--raw", action="store_true", help="Show full raw headers instead of summary")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_headers)

    p = subparsers.add_parser("rules", help="List/manage mail rules")
    p.add_argument("action", nargs="?", choices=["enable", "disable"], help="Action to perform")
    p.add_argument("rule_name", nargs="?", help="Rule name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_rules)

    p = subparsers.add_parser("signatures", help="List email signatures")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_signatures)
