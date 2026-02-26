"""Batch mail operations: batch-read, batch-flag, batch-move, batch-delete."""

import sys
from datetime import datetime, timedelta

from mxctl.commands.mail.undo import log_batch_operation, log_fence_operation
from mxctl.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    DEFAULT_MAILBOX,
    resolve_account,
)
from mxctl.util.applescript import escape, run
from mxctl.util.dates import to_applescript_date
from mxctl.util.formatting import die, format_output
from mxctl.util.mail_helpers import resolve_mailbox

# ---------------------------------------------------------------------------
# Data functions (plain args, return dicts, no printing)
# ---------------------------------------------------------------------------


def batch_read(account: str, mailbox: str, limit: int) -> dict:
    """Mark up to `limit` unread messages as read in a mailbox. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set unreadMsgs to (every message of mb whose read status is false)
        set ct to count of unreadMsgs
        set cap to {limit}
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
    return {"mailbox": mailbox, "account": account, "marked_read": count, "limit": limit}


def batch_flag(account: str, sender: str, limit: int) -> dict:
    """Flag up to `limit` messages from a sender across all mailboxes. Returns result dict."""
    acct_escaped = escape(account)
    sender_escaped = escape(sender)

    script = f"""
    tell application "Mail"
        set output to 0
        repeat with mbox in (mailboxes of account "{acct_escaped}")
            if output >= {limit} then exit repeat
            set msgs to (every message of mbox whose sender contains "{sender_escaped}")
            repeat with m in msgs
                if output >= {limit} then exit repeat
                set flagged status of m to true
                set output to output + 1
            end repeat
        end repeat
        return output
    end tell
    """

    result = run(script)
    count = int(result) if result.isdigit() else 0
    return {"sender": sender, "account": account, "flagged": count, "limit": limit}


def batch_move(account: str, sender: str, dest_mailbox: str, dry_run: bool = False, limit: int | None = None) -> dict:
    """Move messages from a sender to a mailbox. Returns result dict."""
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
        return {"sender": sender, "account": account, "moved": 0, "total_matching": 0}

    if dry_run:
        effective_count = min(total_count, limit) if limit else total_count
        return {
            "sender": sender,
            "to_mailbox": dest_mailbox,
            "account": account,
            "would_move": effective_count,
            "total_matching": total_count,
            "dry_run": True,
        }

    # Actually move the messages and collect their IDs for undo logging
    limit_clause = f"if moveCount >= {limit} then exit repeat" if limit else ""

    move_script = f"""
    tell application "Mail"
        set destMb to mailbox "{dest_escaped}" of account "{acct_escaped}"
        set moveCount to 0
        set movedIds to {{}}
        repeat with mbox in (mailboxes of account "{acct_escaped}")
            {limit_clause}
            set sourceMbName to name of mbox
            set msgs to (every message of mbox whose sender contains "{sender_escaped}")
            repeat with m in msgs
                {limit_clause}
                try
                    set msgId to id of m
                    move m to destMb
                    set end of movedIds to msgId
                    set moveCount to moveCount + 1
                end try
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

    if moved > 0:
        log_batch_operation(
            operation_type="batch-move",
            account=account,
            message_ids=message_ids,
            source_mailbox=None,
            dest_mailbox=dest_mailbox,
            sender=sender,
        )

    return {"sender": sender, "to_mailbox": dest_mailbox, "account": account, "moved": moved}


def batch_delete(
    account: str,
    mailbox: str | None,
    older_than_days: int | None,
    sender: str | None,
    dry_run: bool = False,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    """Delete messages matching sender and/or age filters. Returns result dict."""
    acct_escaped = escape(account)

    # Build AppleScript whose-clause
    where_parts = []
    if older_than_days is not None:
        cutoff_dt = datetime.now() - timedelta(days=older_than_days)
        cutoff_applescript = to_applescript_date(cutoff_dt)
        where_parts.append(f'date received < date "{cutoff_applescript}"')
    if sender:
        sender_escaped = escape(sender)
        where_parts.append(f'sender contains "{sender_escaped}"')
    where_clause = " and ".join(where_parts)

    # Human-readable descriptions for output
    scope_desc = f"'{mailbox}'" if mailbox else "all mailboxes"
    filter_parts = []
    if sender:
        filter_parts.append(f"from '{sender}'")
    if older_than_days is not None:
        filter_parts.append(f"older than {older_than_days} days")
    filter_desc = " and ".join(filter_parts)

    # Count matching messages
    if mailbox:
        mb_escaped = escape(mailbox)
        count_script = f"""
        tell application "Mail"
            set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
            set targetMsgs to (every message of mb whose {where_clause})
            return count of targetMsgs
        end tell
        """
    else:
        count_script = f"""
        tell application "Mail"
            set total to 0
            repeat with mbox in (mailboxes of account "{acct_escaped}")
                set targetMsgs to (every message of mbox whose {where_clause})
                set total to total + (count of targetMsgs)
            end repeat
            return total
        end tell
        """

    count_result = run(count_script)
    total_count = int(count_result) if count_result.isdigit() else 0

    if total_count == 0:
        return {
            "account": account,
            "mailbox": mailbox,
            "sender": sender,
            "older_than_days": older_than_days,
            "deleted": 0,
            "filter_desc": filter_desc,
            "scope_desc": scope_desc,
        }

    if dry_run:
        effective_count = min(total_count, limit) if limit else total_count
        return {
            "account": account,
            "mailbox": mailbox,
            "sender": sender,
            "older_than_days": older_than_days,
            "would_delete": effective_count,
            "total_matching": total_count,
            "dry_run": True,
            "filter_desc": filter_desc,
            "scope_desc": scope_desc,
        }

    if not force:
        die(f"This will delete {total_count} messages {filter_desc} from {scope_desc}. Use --force to confirm.")

    # Build delete script
    limit_check = f"if deleteCount >= {limit} then exit repeat" if limit else ""
    if mailbox:
        mb_escaped = escape(mailbox)
        delete_script = f"""
        tell application "Mail"
            set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
            set targetMsgs to (every message of mb whose {where_clause})
            set deleteCount to 0
            set deletedIds to {{}}
            repeat with m in targetMsgs
                {limit_check}
                try
                    set msgId to id of m
                    delete m
                    set end of deletedIds to msgId
                    set deleteCount to deleteCount + 1
                end try
            end repeat
            set output to (deleteCount as text)
            repeat with msgId in deletedIds
                set output to output & linefeed & (msgId as text)
            end repeat
            return output
        end tell
        """
    else:
        delete_script = f"""
        tell application "Mail"
            set deleteCount to 0
            set deletedIds to {{}}
            repeat with mbox in (mailboxes of account "{acct_escaped}")
                {limit_check}
                set targetMsgs to (every message of mbox whose {where_clause})
                repeat with m in targetMsgs
                    {limit_check}
                    try
                        set msgId to id of m
                        delete m
                        set end of deletedIds to msgId
                        set deleteCount to deleteCount + 1
                    end try
                end repeat
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

    if deleted > 0:
        log_batch_operation(
            operation_type="batch-delete",
            account=account,
            message_ids=message_ids,
            source_mailbox=mailbox,
            dest_mailbox=None,
            sender=sender,
            older_than_days=older_than_days,
        )

    return {
        "account": account,
        "mailbox": mailbox,
        "sender": sender,
        "older_than_days": older_than_days,
        "deleted": deleted,
        "filter_desc": filter_desc,
        "scope_desc": scope_desc,
    }


# ---------------------------------------------------------------------------
# batch-read — mark all as read in a mailbox
# ---------------------------------------------------------------------------


def cmd_batch_read(args) -> None:
    """Mark all messages as read in a mailbox."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    limit = getattr(args, "limit", None) or 25

    result = batch_read(account, mailbox, limit)
    count = result["marked_read"]
    log_fence_operation("batch-read")
    format_output(args, f"Marked {count} messages as read in {mailbox} [{account}] (limit: {limit}).", json_data=result)
    print(
        f"Note: batch-read operations are not tracked in undo history. Use --limit N to cap scope (current: {limit} messages).",
        file=sys.stderr,
    )


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
    limit = getattr(args, "limit", None) or 25

    result = batch_flag(account, sender, limit)
    count = result["flagged"]
    log_fence_operation("batch-flag")
    format_output(args, f"Flagged {count} messages from '{sender}' in account '{account}' (limit: {limit}).", json_data=result)
    print(
        f"Note: batch-flag operations are not tracked in undo history. Use --limit N to cap scope (current: {limit} messages).",
        file=sys.stderr,
    )


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
    dest_mailbox = resolve_mailbox(account, dest_mailbox)

    dry_run = getattr(args, "dry_run", False)
    limit = getattr(args, "limit", None)

    result = batch_move(account, sender, dest_mailbox, dry_run=dry_run, limit=limit)

    if result.get("moved") == 0 and result.get("total_matching") == 0:
        format_output(args, f"No messages found from sender '{sender}'.", json_data=result)
        return

    if dry_run:
        format_output(args, f"Dry run: Would move {result['would_move']} messages from '{sender}' to '{dest_mailbox}'.", json_data=result)
        return

    moved = result["moved"]
    format_output(args, f"Moved {moved} messages from '{sender}' to '{dest_mailbox}'.", json_data=result)


# ---------------------------------------------------------------------------
# batch-delete — delete messages by sender and/or age from a mailbox
# ---------------------------------------------------------------------------


def cmd_batch_delete(args) -> None:
    """Delete messages matching sender and/or age filters."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")

    mailbox = getattr(args, "mailbox", None)
    older_than_days = getattr(args, "older_than", None)
    sender = getattr(args, "from_sender", None)
    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)
    limit = getattr(args, "limit", None)

    if older_than_days is None and sender is None:
        die("Specify --older-than <days>, --from-sender <email>, or both.")

    # --older-than without --from-sender still requires --mailbox for safety
    if older_than_days is not None and sender is None and not mailbox:
        die("--mailbox is required when using --older-than without --from-sender.")

    if mailbox:
        mailbox = resolve_mailbox(account, mailbox)

    result = batch_delete(account, mailbox, older_than_days, sender, dry_run=dry_run, force=force, limit=limit)

    filter_desc = result.get("filter_desc", "")
    scope_desc = result.get("scope_desc", "")

    if result.get("deleted") == 0 and not dry_run and "would_delete" not in result:
        format_output(
            args,
            f"No messages found {filter_desc} in {scope_desc}.",
            json_data={"account": account, "mailbox": mailbox, "sender": sender, "older_than_days": older_than_days, "deleted": 0},
        )
        return

    if dry_run:
        format_output(
            args,
            f"Dry run: Would delete {result['would_delete']} messages {filter_desc} from {scope_desc}.",
            json_data={
                "account": account,
                "mailbox": mailbox,
                "sender": sender,
                "older_than_days": older_than_days,
                "would_delete": result["would_delete"],
                "total_matching": result["total_matching"],
                "dry_run": True,
            },
        )
        return

    deleted = result["deleted"]
    format_output(
        args,
        f"Deleted {deleted} messages {filter_desc} from {scope_desc}.",
        json_data={"account": account, "mailbox": mailbox, "sender": sender, "older_than_days": older_than_days, "deleted": deleted},
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register batch mail subcommands."""
    p = subparsers.add_parser("batch-read", help="Mark messages as read in a mailbox")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--limit", type=int, default=25, help="Maximum number of messages to mark read (default: 25)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_batch_read)

    p = subparsers.add_parser("batch-flag", help="Flag messages from a sender")
    p.add_argument("--from-sender", required=True, help="Sender email to match")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--limit", type=int, default=25, help="Maximum number of messages to flag (default: 25)")
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

    p = subparsers.add_parser("batch-delete", help="Delete messages by sender and/or age")
    p.add_argument("--from-sender", help="Delete messages from this sender (across all mailboxes, or use -m to scope)")
    p.add_argument("--older-than", type=int, help="Delete messages older than N days (requires -m when used alone)")
    p.add_argument("-m", "--mailbox", help="Scope to a specific mailbox (required when using --older-than alone)")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    p.add_argument("--limit", type=int, help="Maximum number of messages to delete")
    p.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_batch_delete)
