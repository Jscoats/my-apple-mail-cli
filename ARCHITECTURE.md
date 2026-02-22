# Architecture

This document explains the high-level design of my-apple-mail-cli for contributors.

## Overview

my-apple-mail-cli is a Python CLI that controls Apple Mail via AppleScript. It uses zero external runtime dependencies — everything is built on Python's standard library.

```
User → CLI (argparse) → Command Module → AppleScript Bridge → Mail.app
```

## Directory Structure

```
src/my_cli/
├── main.py                        # Top-level argparse router
├── config.py                      # Constants, account resolution, validation
├── util/
│   ├── applescript.py             # run(), escape(), sanitize_path()
│   ├── applescript_templates.py   # Reusable AppleScript patterns
│   ├── formatting.py             # format_output(), truncate(), die()
│   ├── mail_helpers.py           # resolve_message_context(), normalize_subject()
│   └── dates.py                  # parse_date(), to_applescript_date()
└── commands/
    └── mail/                      # All mail subcommands (16 modules)
        ├── __init__.py            # Imports and wires all registered command modules
        ├── accounts.py            # inbox, accounts, mailboxes
        ├── messages.py            # list, read, search
        ├── actions.py             # mark-read, mark-unread, flag, unflag, move, delete
        ├── compose.py             # draft (supports --template)
        ├── attachments.py         # attachments, save-attachment
        ├── manage.py              # create-mailbox, delete-mailbox, empty-trash
        ├── batch.py               # batch-read, batch-flag, batch-move, batch-delete
        ├── analytics.py           # stats, top-senders, digest, show-flagged
        ├── setup.py               # init (first-time setup wizard)
        ├── system.py              # check, headers, rules, junk, not-junk
        ├── composite.py           # export, thread, reply, forward
        ├── ai.py                  # summary, triage, context, find-related
        ├── templates.py           # templates list/create/show/delete
        ├── todoist_integration.py # to-todoist
        ├── inbox_tools.py         # process-inbox, clean-newsletters, weekly-review
        └── undo.py                # undo, undo --list
```

## AppleScript Bridge

All Mail.app interaction goes through `util/applescript.py`, which wraps `osascript -e`. This module provides:

- **`run(script, timeout=30)`** — Execute an AppleScript string and return stdout
- **`escape(string)`** — Sanitize strings for safe embedding in AppleScript
- **`sanitize_path(path)`** — Expand and resolve file paths

AppleScript returns multi-field data using `FIELD_SEPARATOR` (ASCII Unit Separator `\x1f`) and `RECORD_SEPARATOR` (ASCII Record Separator `\x1e`), defined in `config.py`. Command modules split on these to parse structured responses from Mail.app.

Reusable AppleScript patterns (inbox iteration, message lookup) live in `applescript_templates.py` to avoid duplication across commands.

## Three-Tier Account Resolution

When a command needs a mail account, resolution follows this priority:

1. **Explicit flag** — `-a "Account Name"` on the command line
2. **Config default** — `default_account` in `~/.config/my/config.json`
3. **Last-used** — Most recently used account stored in `state.json`

This is implemented in `config.py:resolve_account()` and used by `util/mail_helpers.py:resolve_message_context()`.

## Command Registration

Each command module in `commands/mail/` exports a `register(subparsers)` function that adds its commands to the argparse tree. The `commands/mail/__init__.py` router explicitly imports and calls all `register()` functions.

To add a new command:

1. Add a handler function in the appropriate module (or create a new one)
2. Add argparse registration in that module's `register()` function
3. The router picks it up automatically

## Output Convention

Every command supports `--json` for structured output. The `format_output(args, text, json_data=...)` function in `util/formatting.py` handles routing — it checks `args.json` and outputs either human-readable text or JSON accordingly.

## Batch Operations & Undo

Batch commands (`batch-read`, `batch-move`, `batch-delete`, `batch-flag`) log their operations to `mail-undo.json`. The `undo` command reads this log to reverse the most recent batch operation. Up to 10 operations are retained.

## Testing

Tests live in `tests/` and use `unittest.mock` to mock AppleScript calls. No actual Mail.app interaction happens during testing. Run with `pytest`.

The suite has 292 tests across 17 test files covering command parsing, AppleScript output parsing, error paths, date handling, formatting, config resolution, batch operations, undo logging, templates, and AI classification logic.
