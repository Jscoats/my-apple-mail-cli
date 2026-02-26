"""Shared helper functions for mail commands to eliminate code duplication."""

from __future__ import annotations

import os
import re
import sys
from argparse import Namespace
from email.utils import parseaddr

from mxctl.config import CONFIG_FILE, DEFAULT_MAILBOX, get_gmail_accounts, resolve_account
from mxctl.util.applescript import escape
from mxctl.util.formatting import die

# Friendly name → Gmail IMAP folder name
GMAIL_MAILBOX_MAP: dict[str, str] = {
    "trash": "[Gmail]/Trash",
    "spam": "[Gmail]/Spam",
    "junk": "[Gmail]/Spam",
    "sent": "[Gmail]/Sent Mail",
    "sent messages": "[Gmail]/Sent Mail",
    "archive": "[Gmail]/All Mail",
    "all mail": "[Gmail]/All Mail",
    "drafts": "[Gmail]/Drafts",
    "starred": "[Gmail]/Starred",
    "important": "[Gmail]/Important",
}


def resolve_mailbox(account: str, mailbox: str) -> str:
    """Translate friendly mailbox names to Gmail IMAP names when applicable.

    If the account is configured as a Gmail account and the mailbox name
    matches a known alias, returns the correct [Gmail]/... folder name.
    Otherwise returns the mailbox unchanged.

    Examples:
        resolve_mailbox("ASU Gmail", "Spam")   -> "[Gmail]/Spam"
        resolve_mailbox("ASU Gmail", "Trash")  -> "[Gmail]/Trash"
        resolve_mailbox("iCloud", "Trash")     -> "Trash"
        resolve_mailbox("ASU Gmail", "[Gmail]/Spam") -> "[Gmail]/Spam"  (passthrough)
        resolve_mailbox("ASU Gmail", "INBOX")  -> "INBOX"  (passthrough)
    """
    if account not in get_gmail_accounts():
        return mailbox
    # Already a [Gmail]/... path or INBOX — pass through unchanged
    if mailbox.startswith("[Gmail]/") or mailbox.upper() == "INBOX":
        return mailbox
    return GMAIL_MAILBOX_MAP.get(mailbox.lower(), mailbox)


def resolve_message_context(args: Namespace) -> tuple[str, str, str, str]:
    """Resolve and escape account/mailbox from args.

    Returns tuple: (account, mailbox, acct_escaped, mb_escaped)
    Dies if account is not set.
    """
    account = resolve_account(getattr(args, "account", None))
    if not account:
        if not os.path.isfile(CONFIG_FILE):
            die("No account configured. Run `mxctl init` to get started.")
        else:
            die("No default account set. Run `mxctl init` to configure one, or use -a ACCOUNT.")
    if not os.path.isfile(CONFIG_FILE):
        print(f"Note: No config file found. Using last-used account '{account}'. Run `mxctl init` to create a config.", file=sys.stderr)
    mailbox = getattr(args, "mailbox", None) or DEFAULT_MAILBOX
    mailbox = resolve_mailbox(account, mailbox)

    acct_escaped = escape(account)
    mb_escaped = escape(mailbox)

    return account, mailbox, acct_escaped, mb_escaped


def parse_email_headers(raw: str) -> dict[str, str | list[str]]:
    """Parse raw email headers into a dict (multi-value keys become lists)."""
    headers: dict[str, str | list[str]] = {}
    current_key: str | None = None
    for line in raw.split("\n"):
        if ": " in line and not line.startswith(" ") and not line.startswith("\t"):
            key, _, val = line.partition(": ")
            current_key = key
            if key in headers:
                if isinstance(headers[key], list):
                    headers[key].append(val)
                else:
                    headers[key] = [headers[key], val]
            else:
                headers[key] = val
        elif current_key and (line.startswith(" ") or line.startswith("\t")):
            if isinstance(headers[current_key], list):
                headers[current_key][-1] += " " + line.strip()
            else:
                headers[current_key] += " " + line.strip()
    return headers


def extract_email(sender_str: str) -> str:
    """Extract email address from sender string.

    Examples:
        "John Doe <john@example.com>" -> "john@example.com"
        "jane@example.com" -> "jane@example.com"
        "<admin@site.org>" -> "admin@site.org"
    """
    _, email = parseaddr(sender_str)
    return email if email else sender_str


def extract_display_name(sender: str) -> str:
    """Extract the display name from a sender string.

    Examples:
        '"John Doe" <john@example.com>' -> 'John Doe'
        'John Doe <john@example.com>'   -> 'John Doe'
        'jane@example.com'              -> 'jane@example.com'
    """
    if "<" in sender:
        return sender.split("<")[0].strip().strip('"')
    return sender


def parse_message_line(
    line: str,
    fields: list[str],
    separator: str,
) -> dict | None:
    """Parse a single FIELD_SEPARATOR-delimited AppleScript output line into a dict.

    Args:
        line: A single raw output line from AppleScript.
        fields: Ordered list of field names corresponding to each split part.
            The last field name absorbs all remaining parts (useful when a field
            like 'body' or 'content' may itself contain the separator).
        separator: The field separator string (typically FIELD_SEPARATOR).

    Returns:
        A dict mapping field names to string values, or None if the line has
        fewer parts than required (i.e. len(fields) fields).

    Special coercions applied automatically:
        - Fields named 'id' or ending in '_id': coerced to int when the value
          is a digit string, otherwise kept as-is.
        - Fields named 'read', 'flagged', 'junk', 'deleted', 'forwarded',
          'replied': coerced to bool (True when value lower() == 'true').

    Example::
        parse_message_line(line, ["id", "subject", "sender", "date"], SEP)
        # -> {"id": 42, "subject": "Hello", "sender": "...", "date": "..."}
    """
    parts = line.split(separator)
    if len(parts) < len(fields):
        return None

    _BOOL_FIELDS = {"read", "flagged", "junk", "deleted", "forwarded", "replied"}
    result: dict = {}
    for i, name in enumerate(fields):
        if i == len(fields) - 1:
            # Last field absorbs remaining parts
            raw = separator.join(parts[i:])
        else:
            raw = parts[i]

        if name == "id" or name.endswith("_id"):
            result[name] = int(raw) if raw.isdigit() else raw
        elif name in _BOOL_FIELDS:
            result[name] = raw.lower() == "true"
        else:
            result[name] = raw

    return result


def normalize_subject(subject: str) -> str:
    """Normalize email subject by removing Re:/Fwd:/Fw:/AW:/SV:/VS: prefixes.

    Handles international reply prefixes:
    - Re: (English/most languages)
    - Fwd/Fw: (English forward)
    - AW: (German - Antwort)
    - SV: (Swedish/Norwegian - Svar)
    - VS: (Finnish - Vastaus)

    Handles multiple nested prefixes like "Re: Re: Fwd: Original Subject".
    """
    # Loop to handle multiple nested prefixes
    while True:
        normalized = re.sub(r"^(Re|Fwd|Fw|AW|SV|VS):\s*", "", subject, flags=re.IGNORECASE).strip()
        if normalized == subject:
            break
        subject = normalized
    return subject
