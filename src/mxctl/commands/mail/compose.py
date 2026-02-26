"""Draft creation command."""

import json
import os

from mxctl.config import TEMPLATES_FILE, file_lock, resolve_account
from mxctl.util.applescript import escape, run
from mxctl.util.formatting import die, format_output


def create_draft(
    account: str,
    to_addr: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict:
    """Create a draft email in Mail.app. Returns result dict.

    Has Mail.app side effects (opens a draft window).
    """
    acct_escaped = escape(account)
    subject_escaped = escape(subject)
    body_escaped = escape(body)

    to_commands = []
    for addr in to_addr.split(","):
        addr = addr.strip()
        if addr:
            to_commands.append(f'make new to recipient at end of to recipients with properties {{address:"{escape(addr)}"}}')

    cc_commands = []
    if cc:
        for addr in cc.split(","):
            addr = addr.strip()
            if addr:
                cc_commands.append(f'make new cc recipient at end of cc recipients with properties {{address:"{escape(addr)}"}}')

    bcc_commands = []
    if bcc:
        for addr in bcc.split(","):
            addr = addr.strip()
            if addr:
                bcc_commands.append(f'make new bcc recipient at end of bcc recipients with properties {{address:"{escape(addr)}"}}')

    all_recipient_commands = "\n        ".join(to_commands + cc_commands + bcc_commands)

    script = f"""
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
            {all_recipient_commands}
        end tell
        return "draft created"
    end tell
    """

    run(script)

    data = {
        "status": "draft_created",
        "to": to_addr,
        "subject": subject,
        "account": account,
    }
    if cc:
        data["cc"] = cc
    if bcc:
        data["bcc"] = bcc
    return data


def cmd_draft(args) -> None:
    """Create a draft email for manual review and sending."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")

    to_addr = args.to
    subject = args.subject
    body = args.body
    cc = getattr(args, "cc", None)
    bcc = getattr(args, "bcc", None)

    # Handle template loading
    template_name = getattr(args, "template", None)
    if template_name:
        if os.path.isfile(TEMPLATES_FILE):
            with file_lock(TEMPLATES_FILE), open(TEMPLATES_FILE) as f:
                try:
                    templates = json.load(f)
                except (json.JSONDecodeError, OSError):
                    die("Templates file is corrupt. Run 'mxctl templates list' to diagnose.")
            if template_name not in templates:
                die(f"Template '{template_name}' not found. Use 'mxctl templates list' to see available templates.")
            template = templates[template_name]
            # Apply template, allowing flag overrides
            if not subject:
                subject = template.get("subject", "")
            if not body:
                body = template.get("body", "")
        else:
            die("No templates file found. Create templates with 'mxctl templates create'.")

    # Validate that we have subject and body
    if not subject:
        die("Subject required. Use --subject or --template.")
    if not body:
        die("Body required. Use --body or --template.")

    data = create_draft(account, to_addr, subject, body, cc=cc, bcc=bcc)

    text = f"Draft created successfully!\n\nTo: {to_addr}"
    if cc:
        text += f"\nCC: {cc}"
    if bcc:
        text += f"\nBCC: {bcc}"
    text += f"\nSubject: {subject}"
    text += "\n\nThe draft is open in Mail.app for review. You must manually click Send."

    format_output(args, text, json_data=data)


def register(subparsers) -> None:
    """Register email composition subcommands."""
    p = subparsers.add_parser("draft", help="Create a draft email (does NOT send)")
    p.add_argument("--to", required=True, help="Recipient email(s), comma-separated")
    p.add_argument("--subject", help="Email subject (or use --template)")
    p.add_argument("--body", help="Email body (plain text, or use --template)")
    p.add_argument("--template", help="Load subject/body from template (flags override template values)")
    p.add_argument("--cc", help="CC recipient(s), comma-separated")
    p.add_argument("--bcc", help="BCC recipient(s), comma-separated")
    p.add_argument("-a", "--account", help="Mail account to send from")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_draft)
