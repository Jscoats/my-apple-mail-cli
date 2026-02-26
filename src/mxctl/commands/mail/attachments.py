"""Attachment commands: attachments (list), save-attachment."""

import os

from mxctl.util.applescript import escape, run, sanitize_path, validate_msg_id
from mxctl.util.applescript_templates import list_attachments
from mxctl.util.formatting import die, format_output, truncate
from mxctl.util.mail_helpers import resolve_message_context


def get_attachments(account: str, mailbox: str, message_id: int) -> dict:
    """Return subject and attachment list for a message.

    Returns dict with keys: subject (str), attachments (list[str]).
    """
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    script = list_attachments(f'"{acct_escaped}"', f'"{mb_escaped}"', message_id)
    result = run(script)
    lines = result.strip().split("\n")

    subject = lines[0] if lines else "Unknown"
    att_list = [a for a in lines[1:] if a.strip()] if len(lines) > 1 else []
    return {"subject": subject, "attachments": att_list}


def save_attachment(
    account: str,
    mailbox: str,
    message_id: int,
    attachment: str,
    output_dir: str,
) -> dict:
    """Save a named attachment from a message to disk.

    *attachment* may be an index string (e.g. "1") or a name/prefix.
    *output_dir* must be an existing directory path.

    Returns dict with keys: message_id, subject, attachment, saved_to.
    """
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    if not os.path.isdir(output_dir):
        die(f"Output directory does not exist: {output_dir}")

    list_script = list_attachments(f'"{acct_escaped}"', f'"{mb_escaped}"', message_id)
    result = run(list_script)
    lines = result.strip().split("\n")

    if len(lines) <= 1:
        subject = lines[0] if lines else "Unknown"
        die(f"No attachments found in message '{truncate(subject, 50)}'.")

    subject = lines[0]
    att_list = [a for a in lines[1:] if a.strip()]

    # Resolve attachment name (could be index or name)
    att_name = None
    if attachment.isdigit():
        # Index-based (1-indexed)
        idx = int(attachment) - 1
        if 0 <= idx < len(att_list):
            att_name = att_list[idx]
        else:
            die(f"Attachment index {attachment} out of range (1-{len(att_list)}).")
    else:
        # Name-based (exact match or prefix match)
        exact_matches = [a for a in att_list if a == attachment]
        if exact_matches:
            att_name = exact_matches[0]
        else:
            prefix_matches = [a for a in att_list if a.startswith(attachment)]
            if len(prefix_matches) == 1:
                att_name = prefix_matches[0]
            elif len(prefix_matches) > 1:
                die(f"Ambiguous attachment name '{attachment}'. Matches: {', '.join(prefix_matches)}")
            else:
                die(f"Attachment '{attachment}' not found. Available: {', '.join(att_list)}")

    # Build save path
    save_path = os.path.join(output_dir, att_name)

    # Guard against path traversal (e.g. att_name = "../../.ssh/authorized_keys")
    real_save = os.path.realpath(os.path.abspath(save_path))
    real_base = os.path.realpath(os.path.abspath(output_dir))
    if not real_save.startswith(real_base + os.sep) and real_save != real_base:
        die("Unsafe attachment filename: path traversal detected.")

    att_name_escaped = escape(att_name)
    save_path_posix_escaped = escape(save_path)

    save_script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        repeat with att in (mail attachments of theMsg)
            if name of att is "{att_name_escaped}" then
                save att in POSIX file "{save_path_posix_escaped}"
                return "saved"
            end if
        end repeat
        error "Attachment not found"
    end tell
    """

    try:
        run(save_script)
    except SystemExit:
        die(f"Failed to save attachment '{att_name}'.")

    if not os.path.isfile(save_path):
        die(f"Attachment save reported success but file not found: {save_path}")

    return {
        "message_id": message_id,
        "subject": subject,
        "attachment": att_name,
        "saved_to": save_path,
    }


def cmd_attachments(args) -> None:
    """List attachments on a message."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = validate_msg_id(args.id)

    data = get_attachments(account, mailbox, message_id)
    subject = data["subject"]
    att_list = data["attachments"]

    if not att_list:
        format_output(
            args,
            f"No attachments in message '{truncate(subject, 50)}'.",
            json_data=data,
        )
        return

    text = f"Attachments in '{truncate(subject, 50)}':"
    for i, att in enumerate(att_list, 1):
        text += f"\n  {i}. {att}"
    format_output(args, text, json_data=data)


def cmd_save_attachment(args) -> None:
    """Save an attachment from a message to disk."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    attachment = args.attachment
    output_dir = sanitize_path(getattr(args, "output_dir", "~/Downloads"))

    data = save_attachment(account, mailbox, message_id, attachment, output_dir)
    att_name = data["attachment"]
    subject = data["subject"]
    save_path = data["saved_to"]

    format_output(
        args,
        f"Saved attachment '{att_name}' from message '{truncate(subject, 50)}' to:\n  {save_path}",
        json_data=data,
    )


def register(subparsers) -> None:
    """Register attachment subcommands."""
    # attachments (list)
    p = subparsers.add_parser("attachments", help="List attachments on a message")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_attachments)

    # save-attachment
    p = subparsers.add_parser("save-attachment", help="Save an attachment from a message")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("attachment", help="Attachment name or index (1-based)")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--output-dir", help="Output directory (default: ~/Downloads)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_save_attachment)
