"""Account and mailbox listing commands: inbox, accounts, mailboxes."""

import os

from mxctl.config import CONFIG_FILE, FIELD_SEPARATOR, resolve_account, save_message_aliases
from mxctl.util.applescript import escape, run
from mxctl.util.formatting import format_output, truncate

# ---------------------------------------------------------------------------
# inbox
# ---------------------------------------------------------------------------


def get_inbox_summary(account: str | None = None) -> list[dict]:
    """Fetch unread counts and recent messages across accounts."""
    if account:
        acct_escaped = escape(account)
        script = f"""
        tell application "Mail"
            set output to ""
            set acct to account "{acct_escaped}"
            set acctName to name of acct
            repeat with mbox in (mailboxes of acct)
                if name of mbox is "INBOX" then
                    try
                        set unreadCount to unread count of mbox
                        set totalCount to count of messages of mbox
                        set output to output & acctName & "{FIELD_SEPARATOR}" & unreadCount & "{FIELD_SEPARATOR}" & totalCount & linefeed
                        if unreadCount > 0 then
                            set unreadMsgs to (every message of mbox whose read status is false)
                            set previewCount to 3
                            if (count of unreadMsgs) < previewCount then set previewCount to count of unreadMsgs
                            repeat with j from 1 to previewCount
                                set m to item j of unreadMsgs
                                set output to output & "MSG" & "{FIELD_SEPARATOR}" & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & linefeed
                            end repeat
                        end if
                    end try
                    exit repeat
                end if
            end repeat
            return output
        end tell
        """
    else:
        script = f"""
        tell application "Mail"
            set output to ""
            set acctList to every account
            repeat with i from 1 to (count of acctList)
                set acct to item i of acctList
                set acctName to name of acct
                set acctEnabled to enabled of acct
                if acctEnabled then
                    repeat with mbox in (mailboxes of acct)
                        if name of mbox is "INBOX" then
                            try
                                set unreadCount to unread count of mbox
                                set totalCount to count of messages of mbox
                                set output to output & acctName & "{FIELD_SEPARATOR}" & unreadCount & "{FIELD_SEPARATOR}" & totalCount & linefeed
                                if unreadCount > 0 then
                                    set unreadMsgs to (every message of mbox whose read status is false)
                                    set previewCount to 3
                                    if (count of unreadMsgs) < previewCount then set previewCount to count of unreadMsgs
                                    repeat with j from 1 to previewCount
                                        set m to item j of unreadMsgs
                                        set output to output & "MSG" & "{FIELD_SEPARATOR}" & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & "{FIELD_SEPARATOR}" & (sender of m) & "{FIELD_SEPARATOR}" & (date received of m) & linefeed
                                    end repeat
                                end if
                            end try
                            exit repeat
                        end if
                    end repeat
                end if
            end repeat
            return output
        end tell
        """

    result = run(script)

    if not result.strip():
        return []

    accounts = []
    current = None
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if parts[0] == "MSG" and len(parts) >= 6:
            _, acct, msg_id, subject, sender, date = parts[:6]
            if current:
                current["recent_unread"].append(
                    {
                        "id": int(msg_id) if msg_id.isdigit() else msg_id,
                        "subject": subject,
                        "sender": sender,
                        "date": date,
                    }
                )
        elif len(parts) >= 3:
            acct, unread, total = parts[:3]
            current = {
                "account": acct,
                "unread": int(unread) if unread.isdigit() else 0,
                "total": int(total) if total.isdigit() else 0,
                "recent_unread": [],
            }
            accounts.append(current)

    return accounts


def cmd_inbox(args) -> None:
    """List unread counts and recent messages, optionally scoped to one account."""
    # Use only the explicitly-passed -a flag, not the config default.
    # resolve_account() would return the default account (e.g. iCloud) when no
    # flag is given, causing inbox to show only one account instead of all.
    account = getattr(args, "account", None)

    accounts = get_inbox_summary(account)

    if not accounts:
        if not os.path.isfile(CONFIG_FILE):
            format_output(
                args,
                "No mail accounts found or no INBOX mailboxes available.\nRun `mxctl init` to configure your default account.",
            )
        else:
            format_output(args, "No mail accounts found or no INBOX mailboxes available.")
        return

    # Assign sequential aliases across all accounts
    all_msg_ids = []
    for acct_data in accounts:
        for msg in acct_data["recent_unread"]:
            all_msg_ids.append(msg["id"])
    if all_msg_ids:
        save_message_aliases(all_msg_ids)
    alias_num = 0
    for acct_data in accounts:
        for msg in acct_data["recent_unread"]:
            alias_num += 1
            msg["alias"] = alias_num

    # Build text from parsed data
    text = "Inbox Summary\n" + "=" * 50
    total_unread = 0
    for acct_data in accounts:
        total_unread += acct_data["unread"]
        text += f"\n\n{acct_data['account']}:"
        text += f"\n  Unread: {acct_data['unread']} / Total: {acct_data['total']}"
        if acct_data["unread"] > 0:
            text += "\n  Recent unread:"
            for msg in acct_data["recent_unread"]:
                text += f"\n    [{msg['alias']}] {truncate(msg['subject'], 45)}"
                text += f"\n      From: {msg['sender']}"
    text += f"\n\n{'=' * 50}"
    text += f"\nTotal unread across all accounts: {total_unread}"
    format_output(args, text, json_data=accounts)


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------


def get_accounts() -> list[dict]:
    """Fetch all configured mail accounts."""
    script = f"""
    tell application "Mail"
        set output to ""
        repeat with acct in (every account)
            set acctName to name of acct
            set acctFullName to full name of acct
            set acctEmail to user name of acct
            set acctEnabled to enabled of acct
            set output to output & acctName & "{FIELD_SEPARATOR}" & acctFullName & "{FIELD_SEPARATOR}" & acctEmail & "{FIELD_SEPARATOR}" & acctEnabled & linefeed
        end repeat
        return output
    end tell
    """

    result = run(script)

    if not result.strip():
        return []

    accounts = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 4:
            accounts.append(
                {
                    "name": parts[0],
                    "full_name": parts[1],
                    "email": parts[2],
                    "enabled": parts[3].lower() == "true",
                }
            )

    return accounts


def cmd_accounts(args) -> None:
    """List configured mail accounts."""
    accounts = get_accounts()

    if not accounts:
        format_output(args, "No mail accounts found.")
        return

    # Build text from parsed data
    text = "Mail Accounts:"
    for acct in accounts:
        status = "enabled" if acct["enabled"] else "disabled"
        text += f"\n- {acct['name']}\n  Email: {acct['email']}\n  Name: {acct['full_name']}\n  Status: {status}"
    format_output(args, text, json_data=accounts)


# ---------------------------------------------------------------------------
# mailboxes
# ---------------------------------------------------------------------------


def get_mailboxes(account: str | None = None) -> list[dict]:
    """Fetch mailboxes with unread counts."""
    if account:
        acct_escaped = escape(account)
        script = f"""
        tell application "Mail"
            set acct to account "{acct_escaped}"
            set output to ""
            repeat with mb in (every mailbox of acct)
                set mbName to name of mb
                set mbUnread to unread count of mb
                set output to output & mbName & "{FIELD_SEPARATOR}" & mbUnread & linefeed
            end repeat
            return output
        end tell
        """
    else:
        script = f"""
        tell application "Mail"
            set output to ""
            repeat with acct in (every account)
                set acctName to name of acct
                repeat with mb in (every mailbox of acct)
                    set mbName to name of mb
                    set mbUnread to unread count of mb
                    set output to output & acctName & "{FIELD_SEPARATOR}" & mbName & "{FIELD_SEPARATOR}" & mbUnread & linefeed
                end repeat
            end repeat
            return output
        end tell
        """

    result = run(script)

    if not result.strip():
        return []

    mailboxes = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if account and len(parts) >= 2:
            mailboxes.append({"name": parts[0], "unread": int(parts[1]) if parts[1].isdigit() else 0})
        elif not account and len(parts) >= 3:
            mailboxes.append(
                {
                    "account": parts[0],
                    "name": parts[1],
                    "unread": int(parts[2]) if parts[2].isdigit() else 0,
                }
            )

    return mailboxes


def cmd_mailboxes(args) -> None:
    """List mailboxes with unread counts."""
    account = resolve_account(getattr(args, "account", None))

    mailboxes = get_mailboxes(account)

    if not mailboxes:
        msg = f"No mailboxes found in account '{account}'." if account else "No mailboxes found."
        format_output(args, msg)
        return

    # Build text from parsed data
    header = f"Mailboxes in {account}:" if account else "All Mailboxes:"
    text = header
    for mb in mailboxes:
        unread_str = f" ({mb['unread']} unread)" if mb["unread"] > 0 else ""
        if account:
            text += f"\n- {mb['name']}{unread_str}"
        else:
            text += f"\n- {mb['name']}{unread_str} [{mb['account']}]"
    format_output(args, text, json_data=mailboxes)


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


def get_unread_count(account: str | None = None, mailbox: str | None = None) -> dict:
    """Fetch unread message count for an account/mailbox or across all accounts."""
    if account:
        acct_escaped = escape(account)
        mb = mailbox or "INBOX"
        mb_escaped = escape(mb)
        script = f'''
        tell application "Mail"
            set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
            return unread count of mb
        end tell
        '''
        result = run(script)
        count = int(result.strip()) if result.strip().isdigit() else 0
        return {"unread": count, "account": account, "mailbox": mb}
    else:
        script = """
        tell application "Mail"
            set totalUnread to 0
            repeat with acct in (every account)
                if enabled of acct then
                    repeat with mbox in (mailboxes of acct)
                        if name of mbox is "INBOX" then
                            set totalUnread to totalUnread + (unread count of mbox)
                            exit repeat
                        end if
                    end repeat
                end if
            end repeat
            return totalUnread
        end tell
        """
        result = run(script)
        count = int(result.strip()) if result.strip().isdigit() else 0
        return {"unread": count, "account": "all"}


def cmd_count(args) -> None:
    """Print unread message count."""
    account = resolve_account(getattr(args, "account", None))
    mailbox = getattr(args, "mailbox", None)

    data = get_unread_count(account, mailbox)
    format_output(args, str(data["unread"]), json_data=data)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers) -> None:
    """Register account-related mail subcommands."""
    # inbox
    p = subparsers.add_parser("inbox", help="Unread counts + recent messages across all accounts")
    p.add_argument("-a", "--account", help="Filter to a specific account")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_inbox)

    # accounts
    p = subparsers.add_parser("accounts", help="List configured mail accounts")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_accounts)

    # mailboxes
    p = subparsers.add_parser("mailboxes", help="List mailboxes with unread counts")
    p.add_argument("-a", "--account", help="Filter to a specific account")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_mailboxes)

    # count
    p = subparsers.add_parser("count", help="Unread message count (for scripting)")
    p.add_argument("-a", "--account", help="Specific account")
    p.add_argument("-m", "--mailbox", help="Specific mailbox (default: INBOX)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_count)
