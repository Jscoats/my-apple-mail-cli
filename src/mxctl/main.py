"""Top-level argparse router for mxctl."""

import argparse
import sys

from mxctl import __version__
from mxctl.commands.mail.accounts import register as register_accounts
from mxctl.commands.mail.actions import register as register_actions
from mxctl.commands.mail.ai import register as register_ai
from mxctl.commands.mail.analytics import register as register_analytics
from mxctl.commands.mail.attachments import register as register_attachments
from mxctl.commands.mail.batch import register as register_batch
from mxctl.commands.mail.brief import register as register_brief
from mxctl.commands.mail.compose import register as register_compose
from mxctl.commands.mail.composite import register as register_composite
from mxctl.commands.mail.deadline_scan import register as register_deadline_scan
from mxctl.commands.mail.inbox_tools import register as register_inbox_tools
from mxctl.commands.mail.manage import register as register_manage
from mxctl.commands.mail.messages import register as register_messages
from mxctl.commands.mail.setup import register as register_setup
from mxctl.commands.mail.system import register as register_system
from mxctl.commands.mail.templates import register as register_templates
from mxctl.commands.mail.todoist_integration import register as register_todoist
from mxctl.commands.mail.undo import register as register_undo

_GROUPED_HELP = """\
Apple Mail from your terminal.

Commands by category:

  Setup:        init, check, accounts, mailboxes
  Reading:      inbox, count, list, read, search, thread, context, headers
  Actions:      mark-read, mark-unread, flag, unflag, move, delete
                junk, not-junk, unsubscribe, open, rules
  Compose:      draft, reply, forward, templates
  Manage:       create-mailbox, delete-mailbox, empty-trash
  Batch:        batch-read, batch-flag, batch-move, batch-delete, undo
  AI & Analytics: brief, summary, triage, find-related, digest, top-senders,
                show-flagged, weekly-review, process-inbox,
                clean-newsletters, stats
  Export:       export, attachments, save-attachment, to-todoist

Run `mxctl <command> --help` for details on any command.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mxctl",
        description=_GROUPED_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mxctl {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    register_accounts(subparsers)
    register_messages(subparsers)
    register_actions(subparsers)
    register_compose(subparsers)
    register_attachments(subparsers)
    register_manage(subparsers)
    register_batch(subparsers)
    register_analytics(subparsers)
    register_system(subparsers)
    register_composite(subparsers)
    register_ai(subparsers)
    register_brief(subparsers)
    register_todoist(subparsers)
    register_inbox_tools(subparsers)
    register_deadline_scan(subparsers)
    register_templates(subparsers)
    register_undo(subparsers)
    register_setup(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch to the handler set by set_defaults(func=...)
    try:
        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.parse_args([args.command, "--help"])
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
