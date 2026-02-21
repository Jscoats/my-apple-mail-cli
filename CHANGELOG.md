# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2025-02-14

### Added

- **Account management** — `inbox`, `accounts`, `mailboxes`, `create-mailbox`, `delete-mailbox`, `empty-trash`
- **Message operations** — `list`, `read`, `search`, `mark-read`, `mark-unread`, `flag`, `unflag`, `move`, `delete`
- **AI-powered features** — `summary`, `triage`, `context`, `find-related`, `process-inbox`
- **Batch operations with undo** — `batch-read`, `batch-flag`, `batch-move`, `batch-delete`, `undo`
- **Analytics** — `stats`, `top-senders`, `digest`, `show-flagged`, `weekly-review`, `clean-newsletters`
- **Compose & templates** — `draft` with template support, `reply`, `forward`, `templates` subcommands
- **Integrations** — `to-todoist` for sending emails as Todoist tasks, `export` for Mbox format
- **System tools** — `check`, `headers`, `rules`, `signatures`, `junk`, `not-junk`
- Multi-account support with three-tier account resolution
- `--json` output mode on every command
- Comprehensive test suite (146 tests)
- Zero runtime dependencies (Python stdlib only)
