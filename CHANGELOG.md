# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `top-senders` command — rank senders by frequency with `--limit N`, `--json`, and optional mailbox filter
- `batch-delete --from-sender EMAIL` flag — delete by sender across all mailboxes, combinable with `--older-than` ✓

### Fixed

- `inbox` now accepts `-a` / `--account` to scope results to a single account ✓
- `triage` now accepts `-a` / `--account` to filter unread to a single account ✓
- `batch-delete` indexed iteration bug — list shifts after each delete causing skips and crashes ✓
- `batch-delete` Gmail All Mail error — individual deletions now wrapped in `try/end try` so one IMAP failure doesn't abort the whole batch ✓
- `list` command now accepts `-m`/`--mailbox` flag (was positional-only, inconsistent with all other commands) ✓
- Gmail mailbox name mapping — `init` now asks which accounts are Gmail; `Spam`, `Trash`, `Sent`, `Archive` etc. auto-translate to `[Gmail]/...` equivalents for those accounts ✓
- `accounts --json` returning empty `[]` instead of account data
- Raw AppleScript error messages now wrapped in user-friendly output

## [0.1.0] - 2026-02-21

### Added

- **First-run setup** — `init` wizard for account detection and optional Todoist token configuration
- **Account management** — `inbox`, `accounts`, `mailboxes`, `create-mailbox`, `delete-mailbox`, `empty-trash`, `count` for scripting and status bars
- **Message operations** — `list`, `read`, `search`, `mark-read`, `mark-unread`, `flag`, `unflag`, `move`, `delete`, `open` for GUI access
- **AI-powered features** — `summary`, `triage`, `context`, `find-related`, `process-inbox`
- **Batch operations with undo** — `batch-read`, `batch-flag`, `batch-move`, `batch-delete`, `undo`
- **Analytics** — `stats`, `top-senders`, `digest`, `show-flagged`, `weekly-review`, `clean-newsletters`
- **Compose & templates** — `draft` with template support, `reply`, `forward`, `templates` subcommands
- **Integrations** — `to-todoist` for sending emails as Todoist tasks, `export` for Mbox format
- **System tools** — `check`, `headers`, `rules`, `junk`, `not-junk`
- Multi-account support with three-tier account resolution
- `--json` output mode on every command
- Comprehensive test suite (166 tests)
- Zero runtime dependencies (Python stdlib only)
