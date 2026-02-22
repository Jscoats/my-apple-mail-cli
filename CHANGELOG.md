# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-02-22

### Added

- `top-senders` command — rank senders by frequency with `--limit N`, `--json`, and optional mailbox filter
- `batch-delete --from-sender EMAIL` flag — delete by sender across all mailboxes, combinable with `--older-than`
- `NOREPLY_PATTERNS` centralized in `config.py` — single source of truth used by `triage`, `process-inbox`, `clean-newsletters`, and `weekly-review`
- `TEMPLATES_FILE` path centralized in `config.py` — imported by `templates.py` and `compose.py`
- File locking (`_file_lock`) applied to all JSON state reads and writes — `config.json`, `state.json`, `mail-undo.json`, `mail-templates.json`
- 30 new tests covering templates CRUD, draft error paths, and batch dry-run edge cases (196 total)

### Fixed

- **Silent output failures** — three `cmd_mailboxes`, `_list_rules`, and `weekly-review` AppleScript strings were plain strings instead of f-strings; `FIELD_SEPARATOR` was passed as literal text causing commands to silently return empty results
- `batch-delete` indexed iteration bug — list shifts after each delete causing skips and crashes
- `batch-delete` Gmail All Mail error — individual deletions wrapped in `try/end try` so one IMAP failure doesn't abort the whole batch
- `batch-delete` message IDs now logged only after a successful delete (previously logged before, so failed deletions appeared in the undo log)
- `batch-move` — no error resilience; inner loop now wrapped in `try/end try` matching `batch-delete` pattern
- `batch-move` — `--limit` only exited inner loop, allowing more messages to be processed than requested; outer loop now also checks limit
- `batch-move` and `batch-delete` — dry-run reported total matching count instead of effective count when `--limit` is set
- `cmd_not_junk` — hardcoded `"Junk"` mailbox name broke on Gmail accounts; now uses `resolve_mailbox()` for `[Gmail]/Spam` translation
- `cmd_move` — source and destination mailbox names not translated for Gmail accounts; `resolve_mailbox()` now applied to both
- `triage`, `process-inbox`, `clean-newsletters`, `weekly-review` — noreply pattern matching ran against full sender string including display name; now uses `extract_email()` to match against email address only
- `compose.py` — template file read in `cmd_draft` had no JSON error handling; corrupt file now produces a friendly error
- `compose.py` — template file read now uses `_file_lock` (previously read outside locking protocol)
- `_file_lock` — file handle leaked on each failed retry attempt; fixed with `with open(...)` context manager
- `setup.py` `cmd_init` — config written with bare `open()` bypassing `_file_lock`; now uses `_save_json()`
- `_load_json` — reads were not locked (writes were); now symmetric
- `list` command now accepts `-m`/`--mailbox` flag (was positional-only, inconsistent with all other commands)
- `inbox` and `triage` now accept `-a` / `--account` to scope results to a single account
- Gmail mailbox name mapping — `init` now asks which accounts are Gmail; `Spam`, `Trash`, `Sent`, `Archive` etc. auto-translate to `[Gmail]/...` equivalents
- `accounts --json` returning empty `[]` instead of account data
- `die()` return type corrected to `NoReturn`
- Raw `\x1F`/`\x1FEND\x1F` literals in AppleScript strings replaced with `FIELD_SEPARATOR`/`RECORD_SEPARATOR` constants throughout
- Removed dead code: unused `_convert_dates`, `account_iterator`, `single_message_lookup` functions; unused variable assignments in `todoist_integration.py` and `system.py`

## [0.1.0] - 2026-02-21

### Added

- **First-run setup** — `init` wizard for account detection and optional Todoist token configuration
- **Account management** — `inbox`, `accounts`, `mailboxes`, `create-mailbox`, `delete-mailbox`, `empty-trash`, `count` for scripting and status bars
- **Message operations** — `list`, `read`, `search`, `mark-read`, `mark-unread`, `flag`, `unflag`, `move`, `delete`, `open` for GUI access
- **AI-powered features** — `summary`, `triage`, `context`, `find-related`, `process-inbox`
- **Batch operations with undo** — `batch-read`, `batch-flag`, `batch-move`, `batch-delete`, `undo`
- **Analytics** — `stats`, `digest`, `show-flagged`, `weekly-review`, `clean-newsletters`
- **Compose & templates** — `draft` with template support, `reply`, `forward`, `templates` subcommands
- **Integrations** — `to-todoist` for sending emails as Todoist tasks, `export` for Mbox format
- **System tools** — `check`, `headers`, `rules`, `junk`, `not-junk`
- Multi-account support with three-tier account resolution
- `--json` output mode on every command
- Comprehensive test suite (166 tests)
- Zero runtime dependencies (Python stdlib only)
