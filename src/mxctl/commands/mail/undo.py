"""Batch operation undo: undo, undo --list."""

from __future__ import annotations

import json
import os
from datetime import datetime

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_LONG,
    CONFIG_DIR,
    UNDO_LOG_FILE,
    file_lock,
)
from mxctl.util.applescript import escape, run
from mxctl.util.formatting import die, format_output

MAX_UNDO_OPERATIONS = 10
UNDO_MAX_AGE_MINUTES = 30


def _entry_age_minutes(entry: dict) -> float | None:
    """Return the age of an undo entry in minutes, or None if timestamp is missing/invalid."""
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        entry_time = datetime.fromisoformat(ts)
        return (datetime.now() - entry_time).total_seconds() / 60
    except (ValueError, TypeError):
        return None


def _is_fresh(entry: dict) -> bool:
    """Return True if the undo entry is younger than UNDO_MAX_AGE_MINUTES."""
    age = _entry_age_minutes(entry)
    if age is None:
        return False
    return age < UNDO_MAX_AGE_MINUTES


def _load_undo_log(include_stale: bool = False) -> list[dict]:
    """Load undo log from disk.

    By default, only returns entries younger than UNDO_MAX_AGE_MINUTES.
    Pass include_stale=True to load all entries regardless of age.
    """
    if not os.path.isfile(UNDO_LOG_FILE):
        return []
    with file_lock(UNDO_LOG_FILE), open(UNDO_LOG_FILE) as f:
        try:
            raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
    if include_stale:
        return list(raw)
    return [entry for entry in raw if _is_fresh(entry)]


def _save_undo_log(operations: list[dict]) -> None:
    """Save undo log to disk, keeping only the last MAX_UNDO_OPERATIONS."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Keep only the most recent operations
    trimmed = operations[-MAX_UNDO_OPERATIONS:]
    with file_lock(UNDO_LOG_FILE), open(UNDO_LOG_FILE, "w") as f:
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
    operations.append(
        {
            "timestamp": datetime.now().isoformat(),
            "operation": operation_type,
            "account": account,
            "message_ids": message_ids,
            "source_mailbox": source_mailbox,
            "dest_mailbox": dest_mailbox,
            "sender": sender,
            "older_than_days": older_than_days,
        }
    )
    _save_undo_log(operations)


def log_fence_operation(operation_type: str) -> None:
    """Log a fence sentinel for operations that cannot be undone (e.g. batch-read, batch-flag).

    This claims the undo slot so that a subsequent `mxctl undo` does not silently
    skip past these operations and accidentally undo an earlier undoable entry.
    """
    operations = _load_undo_log(include_stale=True)
    operations.append(
        {
            "type": "fence",
            "operation": operation_type,
            "timestamp": datetime.now().isoformat(),
        }
    )
    _save_undo_log(operations)


# ---------------------------------------------------------------------------
# Data functions (plain args, return dicts/lists, no printing)
# ---------------------------------------------------------------------------


def list_undo_history() -> list[dict]:
    """Return the list of recent undoable operations."""
    return _load_undo_log()


def undo_last(force: bool = False) -> dict:
    """Undo the most recent batch operation. Returns result dict.

    Raises SystemExit (via die()) on unrecoverable errors.
    """
    all_ops = _load_undo_log(include_stale=True)
    fresh_ops = [op for op in all_ops if _is_fresh(op)]

    if not all_ops:
        die("No recent batch operations to undo.")

    if not fresh_ops and not force:
        most_recent = all_ops[-1]
        age = _entry_age_minutes(most_recent)
        age_str = f"{int(age)} minutes ago" if age is not None else "unknown time ago"
        die(
            f"Nothing recent to undo (most recent operation was {age_str}). "
            f"Run `mxctl undo --list` to see older operations and use "
            f"`mxctl undo --force` to run them."
        )

    operations = fresh_ops if not force else all_ops
    if not operations:
        die("No batch operations to undo.")  # pragma: no cover — earlier guards catch all empty cases

    last_op = operations.pop()

    if last_op.get("type") == "fence":
        op_name = last_op.get("operation", "unknown")
        if not force:
            die(
                f"The most recent operation ({op_name}) cannot be undone. "
                f"Use `mxctl undo --list` to see older undoable operations, "
                f"or `mxctl undo --force` to skip to the next undoable entry."
            )
        if not operations:
            die("No undoable operations remain after skipping the fence.")
        last_op = operations.pop()

    operation_type = last_op["operation"]
    account = last_op["account"]
    message_ids = last_op.get("message_ids", [])

    if not message_ids:
        die(f"No message IDs recorded for operation '{operation_type}'. Cannot undo.")

    acct_escaped = escape(account)

    try:
        if operation_type == "batch-move":
            dest_mailbox = last_op.get("dest_mailbox")
            if not dest_mailbox:
                die("Incomplete operation data. Cannot undo batch-move.")

            dest_escaped = escape(dest_mailbox)
            inbox_escaped = escape("INBOX")
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
            _save_undo_log(operations)
            total = len(message_ids)
            if moved == 0:
                msg = f"Nothing to restore (0 of {total} messages found — they may have already been moved or deleted)."
            else:
                msg = f"Undid batch-move: moved {moved}/{total} messages from '{sender}' back to INBOX from '{dest_mailbox}'."
            return {
                "message": msg,
                "operation": "undo-batch-move",
                "account": account,
                "from_mailbox": dest_mailbox,
                "to_mailbox": "INBOX",
                "sender": sender,
                "restored": moved,
                "total": total,
            }

        elif operation_type == "batch-delete":
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
            total = len(message_ids)
            if moved == 0:
                msg = f"Nothing to restore (0 of {total} messages found — they may have already been moved or deleted)."
            else:
                msg = f"Undid batch-delete: moved {moved}/{total} messages from Trash back to '{restore_mailbox}'."
            if restore_note and moved > 0:
                msg += f" Note: {restore_note}"
            json_result = {
                "message": msg,
                "operation": "undo-batch-delete",
                "account": account,
                "from_mailbox": "Trash",
                "to_mailbox": restore_mailbox,
                "sender": sender,
                "restored": moved,
                "total": total,
            }
            if restore_note:
                json_result["note"] = restore_note
            _save_undo_log(operations)
            return json_result

        else:
            die(f"Unknown operation type '{operation_type}'. Cannot undo.")

    except (Exception, KeyboardInterrupt):
        operations.append(last_op)
        _save_undo_log(operations)
        raise

    # Unreachable, but satisfies type checker
    return {}  # pragma: no cover


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------


def cmd_undo_list(args) -> None:
    """List recent undoable operations."""
    operations = list_undo_history()
    if not operations:
        format_output(args, "No recent batch operations to undo.", json_data={"operations": []})
        return

    text = f"Recent batch operations ({len(operations)}):"
    for i, op in enumerate(reversed(operations), 1):
        is_fence = op.get("type") == "fence"
        prefix = "[no undo] " if is_fence else ""
        ts = op.get("timestamp", "")
        text += f"\n  {i}. {prefix}{op['operation']} — {ts}"
        if not is_fence:
            if op.get("sender"):
                text += f" from {op['sender']}"
            if op.get("source_mailbox"):
                text += f" from {op['source_mailbox']}"
            if op.get("dest_mailbox"):
                text += f" to {op['dest_mailbox']}"
            if op.get("older_than_days"):
                text += f" (older than {op['older_than_days']} days)"
            text += f" ({len(op.get('message_ids', []))} messages)"

    format_output(args, text, json_data={"operations": list(reversed(operations))})


def cmd_undo(args) -> None:
    """Undo the most recent batch operation."""
    force = getattr(args, "force", False)
    result = undo_last(force=force)
    msg = result.pop("message", "")
    format_output(args, msg, json_data=result)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register undo mail subcommands."""
    p = subparsers.add_parser("undo", help="Undo most recent batch operation")
    p.add_argument("--list", action="store_true", dest="list_operations", help="List recent undoable operations")
    p.add_argument("--force", action="store_true", help="Bypass the 30-minute freshness check")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=lambda args: cmd_undo_list(args) if args.list_operations else cmd_undo(args))
