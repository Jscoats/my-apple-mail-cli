"""Mailbox management commands: create-mailbox, delete-mailbox, empty-trash."""

import subprocess

from mxctl.config import resolve_account
from mxctl.util.applescript import escape, run
from mxctl.util.formatting import die, format_output
from mxctl.util.mail_helpers import resolve_mailbox


def create_mailbox(account: str, name: str) -> dict:
    """Create a new mailbox in the given account. Returns result dict."""
    acct_escaped = escape(account)
    mb_escaped = escape(name)

    script = f"""
    tell application "Mail"
        set acct to account "{acct_escaped}"
        make new mailbox with properties {{name:"{mb_escaped}"}} at acct
        return "created"
    end tell
    """

    run(script)
    return {"mailbox": name, "account": account, "status": "created"}


def delete_mailbox(account: str, name: str) -> dict:
    """Delete a mailbox and all its messages. Returns result dict with message count."""
    acct_escaped = escape(account)
    mb_escaped = escape(name)

    # Check message count
    count_script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        return count of messages of mb
    end tell
    """
    try:
        count_result = run(count_script)
        msg_count = int(count_result) if count_result.isdigit() else 0
    except SystemExit:
        msg_count = 0

    delete_script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        delete mb
        return "deleted"
    end tell
    """

    run(delete_script)
    return {"mailbox": name, "account": account, "status": "deleted", "messages_deleted": msg_count}


def cmd_create_mailbox(args) -> None:
    """Create a new mailbox."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    name = args.name

    data = create_mailbox(account, name)
    format_output(
        args,
        f"Mailbox '{name}' created in account '{account}'.",
        json_data=data,
    )


def cmd_delete_mailbox(args) -> None:
    """Delete a mailbox and all its messages."""
    account = resolve_account(getattr(args, "account", None))
    if not account:
        die("Account required. Use -a ACCOUNT.")
    name = args.name

    if not getattr(args, "force", False):
        die(f"Deleting mailbox '{name}' is permanent and cannot be undone. Re-run with --force to confirm.")

    data = delete_mailbox(account, name)
    msg_count = data["messages_deleted"]
    warning = f" ({msg_count} messages were deleted)" if msg_count > 0 else ""
    format_output(
        args,
        f"Mailbox '{name}' deleted from account '{account}'.{warning}",
        json_data=data,
    )


def empty_trash(account: str | None, all_accounts: bool) -> dict:
    """Open the erase-deleted-items dialog for an account or all accounts.

    Returns dict with keys: account (label), status, messages.
    status is one of: "already_empty", "confirmation_pending".
    Has Mail.app and System Events side effects (opens a confirmation dialog).
    """
    if all_accounts:
        menu_item = "In All Accounts\u2026"
        label = "all accounts"
        msg_count = None  # unknown when erasing all accounts
    else:
        menu_item = f"{account}\u2026"
        label = account

        # Count messages before erase so we can report it
        acct_escaped = escape(account)
        trash_mb = resolve_mailbox(account, "Trash")
        trash_mb_escaped = escape(trash_mb)
        count_script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set trashMb to mailbox "{trash_mb_escaped}" of acct
            return count of messages of trashMb
        end tell
        """
        try:
            count_result = run(count_script)
            msg_count = int(count_result) if count_result.isdigit() else 0
        except SystemExit:
            msg_count = 0

        if msg_count == 0:
            return {"account": label, "status": "already_empty", "messages": 0}

    # Use System Events to click the menu — this triggers a native
    # confirmation dialog that the user must approve.
    menu_escaped = escape(menu_item)
    ui_script = f"""
    tell application "Mail" to activate
    delay 0.5
    tell application "System Events"
        tell process "Mail"
            click menu item "{menu_escaped}" of menu 1 of menu item ¬
                "Erase Deleted Items" of menu "Mailbox" of menu bar 1
        end tell
    end tell
    return "dialog_opened"
    """

    try:
        result = subprocess.run(
            ["osascript", "-e", ui_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            err = result.stderr.strip()
            if "Can't get menu item" in err:
                die(f"Menu item '{menu_item}' not found. Check account name.")
            die(f"Failed to open erase dialog: {err}")
    except subprocess.TimeoutExpired:
        die("Timed out waiting for Mail.app menu.")

    return {"account": label, "status": "confirmation_pending", "messages": msg_count}


def cmd_empty_trash(args) -> None:
    """Empty the Trash via Mail.app's Erase Deleted Items menu.

    Uses System Events to trigger the menu command, which opens a
    confirmation dialog for the user to approve manually.
    """
    account = resolve_account(getattr(args, "account", None))
    all_accounts = getattr(args, "all", False)

    if not account and not all_accounts:
        die("Account required. Use -a ACCOUNT or --all.")

    data = empty_trash(account, all_accounts)
    label = data["account"]
    msg_count = data["messages"]

    if data["status"] == "already_empty":
        format_output(
            args,
            f"Trash is already empty for '{account}'.",
            json_data=data,
        )
        return

    count_msg = f" ({msg_count} messages)" if msg_count is not None else ""
    format_output(
        args,
        f"Erase dialog opened for {label}{count_msg}. Confirm in Mail.app to permanently delete.",
        json_data=data,
    )


def register(subparsers) -> None:
    """Register mailbox management subcommands."""
    p = subparsers.add_parser("create-mailbox", help="Create a new mailbox")
    p.add_argument("name", help="Mailbox name")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_create_mailbox)

    p = subparsers.add_parser("delete-mailbox", help="Delete a mailbox (and all messages)")
    p.add_argument("name", help="Mailbox name")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--force", action="store_true", help="Confirm permanent deletion (required)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_delete_mailbox)

    p = subparsers.add_parser("empty-trash", help="Empty Trash (opens confirmation dialog)")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("--all", action="store_true", help="Erase deleted items in all accounts")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_empty_trash)
