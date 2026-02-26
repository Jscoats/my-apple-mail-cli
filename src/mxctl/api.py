"""Public Python API for mxctl.

Import data functions for programmatic access to Apple Mail.
CLI behavior is unchanged — this module provides the same data
without formatting or printing.

Usage:
    from mxctl.api import list_messages, read_message
    messages = get_messages(account="iCloud", mailbox="INBOX")
"""

# --- Account & Mailbox ---
from mxctl.commands.mail.accounts import (
    get_accounts,
    get_inbox_summary,
    get_mailboxes,
    get_unread_count,
)

# --- Actions ---
from mxctl.commands.mail.actions import (
    delete_message,
    mark_junk,
    move_message,
    not_junk,
    open_message,
    set_flag_status,
    set_read_status,
)

# --- AI / Smart Commands ---
from mxctl.commands.mail.ai import (
    find_related,
    get_context,
    get_summary,
    get_triage,
)

# --- Analytics ---
from mxctl.commands.mail.analytics import (
    get_digest,
    get_flagged_messages,
    get_stats,
    get_top_senders,
)

# --- Attachments ---
from mxctl.commands.mail.attachments import (
    get_attachments,
    save_attachment,
)

# --- Batch Operations ---
from mxctl.commands.mail.batch import (
    batch_delete,
    batch_flag,
    batch_move,
    batch_read,
)

# --- Compose ---
from mxctl.commands.mail.compose import create_draft

# --- Composite ---
from mxctl.commands.mail.composite import (
    create_forward,
    create_reply,
    export_message,
    export_messages,
    get_thread,
)

# --- Inbox Tools ---
from mxctl.commands.mail.inbox_tools import (
    get_inbox_categories,
    get_newsletter_senders,
    get_weekly_review,
)

# --- Mailbox Management ---
from mxctl.commands.mail.manage import (
    create_mailbox,
    delete_mailbox,
    empty_trash,
)

# --- Messages ---
from mxctl.commands.mail.messages import (
    get_messages,
    read_message,
    search_messages,
)

# --- System ---
from mxctl.commands.mail.system import (
    check_mail_status,
    get_headers,
    get_raw_headers,
    get_rules,
    toggle_rule,
)

# --- Templates ---
from mxctl.commands.mail.templates import (
    create_template,
    delete_template,
    get_template,
    get_templates,
)

# --- Todoist Integration ---
from mxctl.commands.mail.todoist_integration import create_todoist_task

# --- Undo ---
from mxctl.commands.mail.undo import (
    list_undo_history,
    undo_last,
)

__all__ = [
    # Account & Mailbox
    "get_accounts",
    "get_inbox_summary",
    "get_mailboxes",
    "get_unread_count",
    # Messages
    "get_messages",
    "read_message",
    "search_messages",
    # Actions
    "delete_message",
    "mark_junk",
    "move_message",
    "not_junk",
    "open_message",
    "set_flag_status",
    "set_read_status",
    # Attachments
    "get_attachments",
    "save_attachment",
    # Compose
    "create_draft",
    # Templates
    "create_template",
    "delete_template",
    "get_template",
    "get_templates",
    # Batch Operations
    "batch_delete",
    "batch_flag",
    "batch_move",
    "batch_read",
    # Analytics
    "get_digest",
    "get_flagged_messages",
    "get_stats",
    "get_top_senders",
    # AI / Smart Commands
    "find_related",
    "get_context",
    "get_summary",
    "get_triage",
    # Inbox Tools
    "get_inbox_categories",
    "get_newsletter_senders",
    "get_weekly_review",
    # Composite
    "create_forward",
    "create_reply",
    "export_message",
    "export_messages",
    "get_thread",
    # Mailbox Management
    "create_mailbox",
    "delete_mailbox",
    "empty_trash",
    # System
    "check_mail_status",
    "get_headers",
    "get_raw_headers",
    "get_rules",
    "toggle_rule",
    # Undo
    "list_undo_history",
    "undo_last",
    # Todoist Integration
    "create_todoist_task",
]
