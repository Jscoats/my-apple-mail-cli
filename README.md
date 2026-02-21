# my-apple-mail-cli

[![CI](https://github.com/Jscoats/my-apple-mail-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Jscoats/my-apple-mail-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> A comprehensive command-line interface for Apple Mail on macOS

**Never leave your terminal.** Manage your Apple Mail with 50+ powerful commands, AI-powered workflows, and modern productivity integrations.

## ✨ Why This Exists

Love Apple Mail but wish you could control it from the terminal? You're not alone. This is the **only comprehensive CLI for Apple Mail** — no comparable tool exists with this breadth of features.

## 🚀 Key Features

- **50+ Commands** - Everything from basic operations to advanced batch processing
- **AI-Powered Workflows** - Smart inbox triage, intelligent summaries, context-aware search
- **Batch Operations with Undo** - Process hundreds of emails safely with rollback support
- **Productivity Integrations** - Send emails to Todoist, use templates, automate workflows
- **Zero Dependencies** - Pure Python stdlib, no external packages required
- **JSON Output Mode** - Every command supports `--json` for scripting and automation

## 📦 Installation

```bash
# Requires Python 3.10+ and macOS
uv tool install git+https://github.com/Jscoats/my-apple-mail-cli
```

## 🎯 Quick Start

```bash
# See what's in your inbox
my mail inbox

# AI-powered summary of unread emails (concise, one-liner per email)
my mail summary

# Triage unread emails by urgency
my mail triage

# Search for messages
my mail search "project update" --sender

# Mark all unread as read (with undo support!)
my mail batch-read -m INBOX

# Oops, undo that
my mail undo

# Create email from template
my mail draft --to colleague@company.com --template "weekly-update"

# Send email to Todoist as a task
my mail to-todoist 123 --project Work
```

## 📚 Command Categories

### Account & Mailbox Management
- `inbox` - Overview of all accounts with unread counts
- `accounts` - List all mail accounts
- `mailboxes` - List mailboxes in an account
- `create-mailbox`, `delete-mailbox` - Manage folders
- `empty-trash` - Empty trash with confirmation dialog

### Message Operations
- `list` - List messages with filters (unread, date range)
- `read` - Display full message
- `search` - Find messages by subject/sender
- `mark-read`, `mark-unread`, `flag`, `unflag` - Message actions
- `move`, `delete` - Organize messages
- `unsubscribe` - Unsubscribe from mailing lists via List-Unsubscribe header (supports one-click RFC 8058)
- `attachments`, `save-attachment` - Handle attachments

### AI-Powered Features
- `summary` - Ultra-concise summaries optimized for AI assistants
- `triage` - Smart categorization by urgency (flagged → people → notifications)
- `context` - Thread messages with parent/child relationships
- `find-related` - Discover similar messages
- `process-inbox` - Diagnostic inbox categorization

### Batch Operations
- `batch-read` - Mark all unread as read
- `batch-flag` - Flag all from sender
- `batch-move` - Move messages by sender
- `batch-delete` - Delete messages older than N days
- `undo`, `undo --list` - Rollback batch operations

### Analytics & Tools
- `stats` - Message statistics for timeframe
- `top-senders` - Most frequent senders
- `digest` - Grouped unread summary
- `show-flagged` - List flagged messages
- `weekly-review` - Past 7 days summary
- `clean-newsletters` - Archive/delete newsletter subscriptions

### Compose & Templates
- `draft` - Create email draft (supports templates)
- `templates list/create/show/delete` - Manage email templates
- `reply`, `forward` - Create response drafts

### Integrations
- `to-todoist` - Send email to Todoist as task
- `export` - Export messages to Mbox format

## 🔧 Requirements

- **macOS** (uses AppleScript to communicate with Mail.app)
- **Python 3.10+**
- **Mail.app** with at least one configured account
- **Permissions:** First run will prompt for Mail.app automation permission in System Settings

## 💡 Usage Tips

### Multi-Account Support
```bash
# Use -a to specify account
my mail list -a "Work Email"
my mail list -a "Personal"

# Set default account in ~/.config/my/config.json
{"mail": {"default_account": "iCloud"}}
```

### JSON Output for Automation
```bash
# Every command supports --json
my mail inbox --json | jq '.accounts[0].unread_count'
my mail search "invoice" --json | jq '.[].subject'
```

### Todoist Integration
```bash
# Add your Todoist API token to ~/.config/my/config.json
{"mail": {"default_account": "iCloud"}, "todoist_api_token": "your-token-here"}

# Then send any email as a Todoist task
my mail to-todoist 123 --project Work
```

To get your token: [Todoist Settings → Integrations → Developer](https://todoist.com/prefs/integrations)

### Email Templates
```bash
# Create a template
my mail templates create "meeting-followup" \
  --subject "Re: {original_subject}" \
  --body "Thanks for the meeting today..."

# Use it
my mail draft --to client@company.com --template "meeting-followup"
```

## 🏗️ Architecture

Built with modern Python patterns:
- **Zero runtime dependencies** (stdlib only)
- **Comprehensive test suite** (~1,500 LOC of tests)
- **Modular command structure** (14 focused modules)
- **AppleScript bridge** for Mail.app communication
- **Three-tier account resolution** (explicit flag → config default → last-used)

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built because no comprehensive Apple Mail CLI existed. Inspired by the need to automate email workflows without leaving the terminal.

## 📮 Contact

- **GitHub:** [@Jscoats](https://github.com/Jscoats)
- **Issues:** [Report bugs or request features](https://github.com/Jscoats/my-apple-mail-cli/issues)

---

**Like this project?** Star it on GitHub ⭐ and share it with fellow terminal enthusiasts!
