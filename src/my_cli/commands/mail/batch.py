"""Batch mail operations: batch-read, batch-flag, batch-move, batch-delete."""

from datetime import datetime, timedelta

from my_cli.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    DEFAULT_MAILBOX,
    resolve_account,
)
from my_cli.util.applescript import escape, run
from my_cli.util.dates import to_applescript_date
from my_cli.util.formatting import die, format_output
from my_cli.commands.mail.undo import log_batch_operation


# ---------------------------------------------------------------------------
# batch-read — mark all as read in a mailbox
# ---------------------------------------------------------------------------

def cmd_batch_read(args) -> None:
    """Mark all messages as read in a mailbox."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX

    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set unreadMsgs to (every message of mb whose read status is false)
        set ct to count of unreadMsgs
        set cap to 1000
        if ct < cap then set cap to ct
        repeat with i from 1 to cap
            set m to item i of unreadMsgs
            set read status of m to true
        end repeat
        return cap
    end tell
    """

    result = run(script)
    count = int(result) if result.isdigit() else 0
    format_output(args, f"Marked {count} messages as read in {mailbox} [{account}].",
                  json_data={"mailbox": mailbox, "account": account, "marked_read": count})


# ---------------------------------------------------------------------------
# batch-flag — flag all from a sender
# ---------------------------------------------------------------------------

def cmd_batch_flag(args) -> None:
    """Flag all messages from a specific sender."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    sender = getattr(args, "from_sender", None)
    if not sender:
        die("--from-sender is required.")

    acct_escaped = escape(account)
    sender_escaped = escape(sender)

    script = f"""
    tell application "Mail"
        set output to 0
        repeat with mbox in (mailboxes of account "{acct_escaped}")
            set msgs to (every message of mbox whose sender contains "{sender_escaped}")
            repeat with m in msgs
                set flagged status of m to true
                set output to output + 1
            end repeat
        end repeat
        return output
    end tell
    """

    result = run(script)
    count = int(result) if result.isdigit() else 0
    format_output(args, f"Flagged {count} messages from '{sender}' in account '{account}'.",
                  json_data={"sender": sender, "account": account, "flagged": count})


# ---------------------------------------------------------------------------
# batch-move — move all messages from a sender to a folder
# ---------------------------------------------------------------------------

def cmd_batch_move(args) -> None:
    """Move all messages from a sender to a mailbox."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    sender = getattr(args, "from_sender", None)
    if not sender:
        die("--from-sender is required.")
    dest_mailbox = getattr(args, "to_mailbox", None)
    if not dest_mailbox:
        die("--to-mailbox is required.")

    dry_run = getattr(args, "dry_run", False)
    limit = getattr(args, "limit", None)

    acct_escaped = escape(account)
    sender_escaped = escape(sender)
    dest_escaped = escape(dest_mailbox)

    # First, count matching messages
    count_script = f"""
    tell application "Mail"
        set output to 0
        repeat with mbox in (mailboxes of account "{acct_escaped}")
            set msgs to (every message of mbox whose sender contains "{sender_escaped}")
            set output to output + (count of msgs)
        end repeat
        return output
    end tell
    """

    count_result = run(count_script)
    total_count = int(count_result) if count_result.isdigit() else 0

    if total_count == 0:
        format_output(args, f"No messages found from sender '{sender}'.",
                      json_data={"sender": sender, "account": account, "moved": 0})
        return

    if dry_run:
        format_output(args, f"Dry run: Would move {total_count} messages from '{sender}' to '{dest_mailbox}'.",
                      json_data={"sender": sender, "to_mailbox": dest_mailbox, "account": account, "would_move": total_count, "dry_run": True})
        return

    # Actually move the messages and collect their IDs for undo logging
    limit_clause = f"if moveCount >= {limit} then exit repeat" if limit else ""

    move_script = f"""
    tell application "Mail"
        set destMb to mailbox "{dest_escaped}" of account "{acct_escaped}"
        set moveCount to 0
        set movedIds to {{}}
        repeat with mbox in (mailboxes of account "{acct_escaped}")
            set sourceMbName to name of mbox
            set msgs to (every message of mbox whose sender contains "{sender_escaped}")
            repeat with m in msgs
                {limit_clause}
                set msgId to id of m
                set end of movedIds to msgId
                move m to destMb
                set moveCount to moveCount + 1
            end repeat
        end repeat
        set output to (moveCount as text)
        repeat with msgId in movedIds
            set output to output & linefeed & (msgId as text)
        end repeat
        return output
    end tell
    """

    result = run(move_script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    lines = result.strip().split("\n")
    moved = int(lines[0]) if lines and lines[0].isdigit() else 0
    message_ids = [int(line) for line in lines[1:] if line.isdigit()]

    # Log the operation for undo
    if moved > 0:
        # We don't track source mailbox per-message, so we'll use None
        # The undo will move from dest back to the original location
        log_batch_operation(
            operation_type="batch-move",
            account=account,
            message_ids=message_ids,
            source_mailbox=None,  # Multiple source mailboxes possible
            dest_mailbox=dest_mailbox,
            sender=sender,
        )

    format_output(args, f"Moved {moved} messages from '{sender}' to '{dest_mailbox}'.",
                  json_data={"sender": sender, "to_mailbox": dest_mailbox, "account": account, "moved": moved})


# ---------------------------------------------------------------------------
# batch-delete — delete messages older than N days from a mailbox
# ---------------------------------------------------------------------------

def cmd_batch_delete(args) -> None:
    """Delete messages older than N days from a mailbox."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None)
    if not mailbox:
        die("--mailbox is required. This command will not delete from all mailboxes.")

    older_than_days = getattr(args, "older_than", None)
    if older_than_days is None:
        die("--older-than <days> is required.")

    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)
    limit = getattr(args, "limit", None)

    cutoff_dt = datetime.now() - timedelta(days=older_than_days)
    cutoff_applescript = to_applescript_date(cutoff_dt)

    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    # Count messages that would be deleted
    count_script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set oldMsgs to (every message of mb whose date received < date "{cutoff_applescript}")
        return count of oldMsgs
    end tell
    """

    count_result = run(count_script)
    total_count = int(count_result) if count_result.isdigit() else 0

    if total_count == 0:
        format_output(args, f"No messages found older than {older_than_days} days in '{mailbox}'.",
                      json_data={"mailbox": mailbox, "account": account, "older_than_days": older_than_days, "deleted": 0})
        return

    if dry_run:
        format_output(args, f"Dry run: Would delete {total_count} messages older than {older_than_days} days from '{mailbox}'.",
                      json_data={"mailbox": mailbox, "account": account, "older_than_days": older_than_days, "would_delete": total_count, "dry_run": True})
        return

    # Require confirmation unless --force
    if not force:
        die(f"This will delete {total_count} messages from '{mailbox}' older than {older_than_days} days. Use --force to confirm.")

    # Actually delete the messages and collect their IDs for undo logging
    _limit_clause = f"if deleteCount >= {limit} then exit repeat" if limit else ""  # noqa: F841

    delete_script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set oldMsgs to (every message of mb whose date received < date "{cutoff_applescript}")
        set deleteCount to 0
        set deletedIds to {{}}
        set cap to {limit if limit else 'count of oldMsgs'}
        if (count of oldMsgs) < cap then set cap to count of oldMsgs
        repeat with i from 1 to cap
            set m to item i of oldMsgs
            set msgId to id of m
            set end of deletedIds to msgId
            delete m
            set deleteCount to deleteCount + 1
        end repeat
        set output to (deleteCount as text)
        repeat with msgId in deletedIds
            set output to output & linefeed & (msgId as text)
        end repeat
        return output
    end tell
    """

    result = run(delete_script, timeout=APPLESCRIPT_TIMEOUT_LONG)
    lines = result.strip().split("\n")
    deleted = int(lines[0]) if lines and lines[0].isdigit() else 0
    message_ids = [int(line) for line in lines[1:] if line.isdigit()]

    # Log the operation for undo
    if deleted > 0:
        log_batch_operation(
            operation_type="batch-delete",
            account=account,
            message_ids=message_ids,
            source_mailbox=mailbox,
            dest_mailbox=None,
            older_than_days=older_than_days,
        )

    format_output(args, f"Deleted {deleted} messages older than {older_than_days} days from '{mailbox}'.",
                  json_data={"mailbox": mailbox, "account": account, "older_than_days": older_than_days, "deleted": deleted})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    """Register batch mail subcommands."""
    p = subparsers.add_parser("batch-read", help="Mark all messages as read in a mailbox")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_batch_read)

    p = subparsers.add_parser("batch-flag", help="Flag all messages from a sender")
    p.add_argument("--from-sender", required=True, help="Sender email to match")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_batch_flag)

    p = subparsers.add_parser("batch-move", help="Move all messages from a sender to a mailbox")
    p.add_argument("--from-sender", required=True, help="Sender email to match")
    p.add_argument("--to-mailbox", required=True, help="Destination mailbox")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--dry-run", action="store_true", help="Show what would be moved without moving")
    p.add_argument("--limit", type=int, help="Maximum number of messages to move")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_batch_move)

    p = subparsers.add_parser("batch-delete", help="Delete messages older than N days from a mailbox")
    p.add_argument("--older-than", type=int, required=True, help="Delete messages older than N days")
    p.add_argument("-m", "--mailbox", required=True, help="Mailbox name (required for safety)")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    p.add_argument("--limit", type=int, help="Maximum number of messages to delete")
    p.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_batch_delete)
