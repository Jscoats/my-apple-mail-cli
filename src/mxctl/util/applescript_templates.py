"""Reusable AppleScript template functions to reduce duplication.

Common patterns extracted from command modules:
1. Inbox iteration across all accounts
2. Message iteration with cap/limit
3. Single message lookup by ID
4. Field output assembly with separators
5. All-mailboxes iteration across one or all accounts

Each template function returns a complete AppleScript string.
Use FIELD_SEPARATOR from config.py in the templates.
"""


def inbox_iterator_all_accounts(inner_operations: str, cap: int = 20, account: str | None = None) -> str:
    """Generate AppleScript to iterate over INBOX in all enabled accounts (or one).

    Args:
        inner_operations: AppleScript code to execute for each INBOX message.
                         Available variables: m (message), acct (account),
                         acctName (account name), mbox (INBOX mailbox)
        cap: Maximum number of messages per inbox
        account: If provided, scope iteration to this single account name

    Returns:
        Complete AppleScript string

    Example:
        inner_ops = f'set output to output & acctName & "{FIELD_SEPARATOR}" & (id of m) & "{FIELD_SEPARATOR}" & (subject of m) & linefeed'
        script = inbox_iterator_all_accounts(inner_ops, cap=30)
        script = inbox_iterator_all_accounts(inner_ops, cap=30, account="iCloud")
    """
    if account:
        from mxctl.util.applescript import escape

        acct_escaped = escape(account)
        outer_open = f'set acct to account "{acct_escaped}"\n        set acctName to name of acct'
        outer_close = ""
    else:
        outer_open = (
            "repeat with acct in (every account)\n            if enabled of acct then\n                set acctName to name of acct"
        )
        outer_close = "            end if\n        end repeat"

    return f"""
    tell application "Mail"
        set output to ""
        set totalFound to 0
        {outer_open}
            repeat with mbox in (mailboxes of acct)
                if name of mbox is "INBOX" then
                    try
                        set unreadMsgs to (every message of mbox whose read status is false)
                        set cap to {cap}
                        if (count of unreadMsgs) < cap then set cap to (count of unreadMsgs)
                        repeat with j from 1 to cap
                            set m to item j of unreadMsgs
                            {inner_operations}
                            set totalFound to totalFound + 1
                        end repeat
                    end try
                    exit repeat
                end if
            end repeat
        {outer_close}
        return output
    end tell
    """


def set_message_property(account_var: str, mailbox_var: str, message_id: int, property_name: str, property_value: str) -> str:
    """Generate AppleScript to set a message property and return subject.

    Args:
        account_var: Variable name or escaped account name
        mailbox_var: Variable name or escaped mailbox name
        message_id: Message ID
        property_name: Property to set (e.g., 'read status', 'flagged status')
        property_value: Value to set (e.g., 'true', 'false')

    Returns:
        Complete AppleScript string

    Example:
        script = set_message_property(
            '"iCloud"', '"INBOX"', 12345,
            'read status', 'true'
        )
    """
    return f"""
    tell application "Mail"
        set mb to mailbox {mailbox_var} of account {account_var}
        set theMsg to first message of mb whose id is {message_id}
        set {property_name} of theMsg to {property_value}
        return subject of theMsg
    end tell
    """


def mailbox_iterator(inner_operations: str, account: str | None = None) -> str:
    """Generate AppleScript to iterate over every mailbox in one or all accounts.

    Unlike inbox_iterator_all_accounts (which only looks at the INBOX mailbox),
    this iterates over ALL mailboxes of the account(s).  Useful for whole-account
    scans such as flagged-message or attachment searches.

    Args:
        inner_operations: AppleScript code to execute inside each mailbox.
                         Available variables: mb (mailbox), acct (account)
        account: If provided, scope iteration to this single (already-escaped)
                 account name string, e.g. ``escape(account)``

    Returns:
        Complete AppleScript string

    Example:
        inner_ops = (
            'set flaggedMsgs to (every message of mb whose flagged status is true)\\n'
            'repeat with m in flaggedMsgs\\n'
            '    set output to output & (id of m) & linefeed\\n'
            'end repeat'
        )
        script = mailbox_iterator(inner_ops, account="iCloud")
        script = mailbox_iterator(inner_ops)  # all accounts
    """
    if account:
        acct_block = f'set acct to account "{account}"\n        repeat with mb in (every mailbox of acct)\n            {inner_operations}\n        end repeat'
    else:
        acct_block = (
            "repeat with acct in (every account)\n"
            "            if enabled of acct then\n"
            f"                repeat with mb in (every mailbox of acct)\n"
            f"                    {inner_operations}\n"
            "                end repeat\n"
            "            end if\n"
            "        end repeat"
        )

    return f"""
    tell application "Mail"
        set output to ""
        {acct_block}
        return output
    end tell
    """


def list_attachments(account_var: str, mailbox_var: str, message_id: int) -> str:
    """Generate AppleScript to list message attachments.

    Args:
        account_var: Variable name or escaped account name
        mailbox_var: Variable name or escaped mailbox name
        message_id: Message ID

    Returns:
        Complete AppleScript string (subject on first line, attachments below)

    Example:
        script = list_attachments('"iCloud"', '"INBOX"', 12345)
    """
    return f"""
    tell application "Mail"
        set mb to mailbox {mailbox_var} of account {account_var}
        set theMsg to first message of mb whose id is {message_id}
        set msgSubject to subject of theMsg
        set output to msgSubject & linefeed
        repeat with att in (mail attachments of theMsg)
            set attName to name of att
            set output to output & attName & linefeed
        end repeat
        return output
    end tell
    """
