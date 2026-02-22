"""Batch operation undo: undo, undo --list."""

from __future__ import annotations

import json
import os
from datetime import datetime

from my_cli.config import (
    CONFIG_DIR,
    APPLESCRIPT_TIMEOUT_LONG,
    file_lock,
    UNDO_LOG_FILE,
)
from my_cli.util.applescript import escape, run
from my_cli.util.formatting import die, format_output

MAX_UNDO_OPERATIONS = 10


def _load_undo_log() -> list[dict]:
    """Load undo log from disk."""
    if not os.path.isfile(UNDO_LOG_FILE):
        return []
    with file_lock(UNDO_LOG_FILE):
        with open(UNDO_LOG_FILE) as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []


def _save_undo_log(operations: list[dict]) -> None:
    """Save undo log to disk, keeping only the last MAX_UNDO_OPERATIONS."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Keep only the most recent operations
    trimmed = operations[-MAX_UNDO_OPERATIONS:]
    with file_lock(UNDO_LOG_FILE):
        with open(UNDO_LOG_FILE, "w") as f:
            json.dump(trimmed, f, indent=2)


def log_batch_operation(
    operation_type: str,
    account: str,
    message_ids: list[int],
    source_mailbox: str | None = None,
    dest_mailbox: str | None = None,
    sender: str | None = None,
    older_than_days: int | None = None,
) -> None:
    """Log a batch operation for potential undo."""
    operations = _load_undo_log()
    operations.append({
        "timestamp": datetime.now().isoformat(),
        "operation": operation_type,
        "account": account,
        "message_ids": message_ids,
        "source_mailbox": source_mailbox,
        "dest_mailbox": dest_mailbox,
        "sender": sender,
        "older_than_days": older_than_days,
    })
    _save_undo_log(operations)


def cmd_undo_list(args) -> None:
    """List recent undoable operations."""
    operations = _load_undo_log()
    if not operations:
        format_output(args, "No recent batch operations to undo.",
                      json_data={"operations": []})
        return

    # Build text output
    text = f"Recent batch operations ({len(operations)}):"
    for i, op in enumerate(reversed(operations), 1):
        text += f"\n{i}. [{op['timestamp']}] {op['operation']}"
        if op.get("sender"):
            text += f" from {op['sender']}"
        if op.get("source_mailbox"):
            text += f" from {op['source_mailbox']}"
        if op.get("dest_mailbox"):
            text += f" to {op['dest_mailbox']}"
        if op.get("older_than_days"):
            text += f" (older than {op['older_than_days']} days)"
        text += f" — {len(op.get('message_ids', []))} messages"

    format_output(args, text, json_data={"operations": list(reversed(operations))})


def cmd_undo(args) -> None:
    """Undo the most recent batch operation."""
    operations = _load_undo_log()
    if not operations:
        die("No recent batch operations to undo.")

    # Pop the most recent operation — do NOT write the log yet;
    # only commit removal after the restore work succeeds.
    last_op = operations.pop()

    operation_type = last_op["operation"]
    account = last_op["account"]
    message_ids = last_op.get("message_ids", [])

    if not message_ids:
        die(f"No message IDs recorded for operation '{operation_type}'. Cannot undo.")

    acct_escaped = escape(account)

    try:
        if operation_type == "batch-move":
            # Reverse move: move messages back from dest
            # Note: batch-move can pull from multiple source mailboxes, so we move back to INBOX as default
            dest_mailbox = last_op.get("dest_mailbox")
            if not dest_mailbox:
                die("Incomplete operation data. Cannot undo batch-move.")

            # Move messages back from dest to INBOX (safest default since source could be multiple mailboxes)
            dest_escaped = escape(dest_mailbox)
            inbox_escaped = escape("INBOX")

            # Build AppleScript to move messages back
            # We'll iterate through message_ids and try to move them
            id_list = ", ".join(str(mid) for mid in message_ids)

            script = f"""
            tell application "Mail"
                set acct to account "{acct_escaped}"
                set destMb to mailbox "{dest_escaped}" of acct
                set inboxMb to mailbox "{inbox_escaped}" of acct
                set movedCount to 0
                set targetIds to {{{id_list}}}
                repeat with targetId in targetIds
                    try
                        set msgs to (every message of destMb whose id is targetId)
                        if (count of msgs) > 0 then
                            set m to item 1 of msgs
                            move m to inboxMb
                            set movedCount to movedCount + 1
                        end if
                    end try
                end repeat
                return movedCount
            end tell
            """

            result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
            moved = int(result) if result.isdigit() else 0
            sender = last_op.get("sender", "unknown sender")
            _save_undo_log(operations)  # commit removal only on success
            format_output(args, f"Undid batch-move: moved {moved}/{len(message_ids)} messages from '{sender}' back to INBOX from '{dest_mailbox}'.",
                          json_data={
                              "operation": "undo-batch-move",
                              "account": account,
                              "from_mailbox": dest_mailbox,
                              "to_mailbox": "INBOX",
                              "sender": sender,
                              "restored": moved,
                              "total": len(message_ids),
                          })

        elif operation_type == "batch-delete":
            # Reverse delete: move messages from Trash back to source_mailbox (or INBOX if unknown)
            source_mailbox = last_op.get("source_mailbox")
            restore_mailbox = source_mailbox if source_mailbox else "INBOX"
            restore_note = None if source_mailbox else "Original mailbox unknown; restored to INBOX."

            trash_escaped = escape("Trash")
            restore_escaped = escape(restore_mailbox)

            id_list = ", ".join(str(mid) for mid in message_ids)

            script = f"""
            tell application "Mail"
                set acct to account "{acct_escaped}"
                set trashMb to mailbox "{trash_escaped}" of acct
                set restoreMb to mailbox "{restore_escaped}" of acct
                set movedCount to 0
                set targetIds to {{{id_list}}}
                repeat with targetId in targetIds
                    try
                        set msgs to (every message of trashMb whose id is targetId)
                        if (count of msgs) > 0 then
                            set m to item 1 of msgs
                            move m to restoreMb
                            set movedCount to movedCount + 1
                        end if
                    end try
                end repeat
                return movedCount
            end tell
            """

            result = run(script, timeout=APPLESCRIPT_TIMEOUT_LONG)
            moved = int(result) if result.isdigit() else 0
            sender = last_op.get("sender", "unknown sender")
            msg = f"Undid batch-delete: moved {moved}/{len(message_ids)} messages from Trash back to '{restore_mailbox}'."
            if restore_note:
                msg += f" Note: {restore_note}"
            json_result = {
                "operation": "undo-batch-delete",
                "account": account,
                "from_mailbox": "Trash",
                "to_mailbox": restore_mailbox,
                "sender": sender,
                "restored": moved,
                "total": len(message_ids),
            }
            if restore_note:
                json_result["note"] = restore_note
            _save_undo_log(operations)  # commit removal only on success
            format_output(args, msg, json_data=json_result)

        else:
            die(f"Unknown operation type '{operation_type}'. Cannot undo.")

    except BaseException:
        operations.append(last_op)
        _save_undo_log(operations)  # put it back
        raise


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    """Register undo mail subcommands."""
    p = subparsers.add_parser("undo", help="Undo most recent batch operation")
    p.add_argument("--list", action="store_true", dest="list_operations", help="List recent undoable operations")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=lambda args: cmd_undo_list(args) if args.list_operations else cmd_undo(args))
