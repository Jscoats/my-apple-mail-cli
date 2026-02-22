# my-apple-mail-cli

[![CI](https://github.com/Jscoats/my-apple-mail-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Jscoats/my-apple-mail-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Automate and extend Apple Mail from the terminal — with structured output designed for AI workflows.

## ✨ Why This Exists

Use Apple Mail but want to automate it? This CLI gives you full control of Mail.app from the terminal. Every command outputs structured data that works with AI assistants, shell scripts, or status bars — so you can triage your inbox with Claude, automate workflows with scripts, or batch-process newsletters without opening Mail.app.

## 🚀 Key Features

- **49 Commands** - Everything from basic operations to advanced batch processing
- **Built for AI Workflows** - Every command supports `--json` output designed for AI assistants to read and act on
- **Batch Operations with Undo** - Process hundreds of emails safely with rollback support
- **Productivity Integrations** - Todoist, templates, scripting, status bar integration
- **Zero Dependencies** - Pure Python stdlib, no external packages required
- **Works with Your Existing Setup** - Doesn't replace Mail.app, extends it

## 📦 Installation

```bash
# Requires Python 3.10+ and macOS
pip install git+https://github.com/Jscoats/my-apple-mail-cli

# Or with uv (faster)
uv tool install git+https://github.com/Jscoats/my-apple-mail-cli
```

## 🎯 Quick Start

```bash
# First time? Set up your default account
my mail init

# See what's in your inbox
my mail inbox

# Smart summary of unread emails (concise, one-liner per email)
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

### Setup
- `init` - First-time setup wizard (auto-detects Mail accounts, configures default account and optional Todoist token)

### Account & Mailbox Management
- `inbox` - Overview of all accounts with unread counts
- `accounts` - List all mail accounts
- `mailboxes` - List mailboxes in an account
- `create-mailbox`, `delete-mailbox` - Manage folders
- `count` - Unread message count (for scripting and status bars)
- `empty-trash` - Empty trash with confirmation dialog

### Message Operations
- `list` - List messages with filters (unread, date range)
- `read` - Display full message
- `search` - Find messages by subject/sender
- `mark-read`, `mark-unread`, `flag`, `unflag` - Message actions
- `move`, `delete` - Organize messages
- `junk`, `not-junk` - Mark as spam / restore from spam (moves to INBOX)
- `open` - Open message in Mail.app GUI
- `unsubscribe` - Unsubscribe from mailing lists via List-Unsubscribe header (supports one-click RFC 8058)
- `attachments`, `save-attachment` - Handle attachments

### AI-Ready Features
- `summary` - Ultra-concise summaries optimized for AI assistants
- `triage` - Smart categorization by urgency (flagged → people → notifications)
- `context` - Thread messages with parent/child relationships
- `find-related` - Discover similar messages
- `process-inbox` - Diagnostic inbox categorization

### Batch Operations
- `batch-read` - Mark all unread as read
- `batch-flag` - Flag all from sender
- `batch-move` - Move messages by sender
- `batch-delete` - Delete messages by sender and/or age
- `undo`, `undo --list` - Rollback batch operations

### Analytics & Tools
- `stats` - Message statistics for timeframe
- `top-senders` - Most frequent senders
- `digest` - Grouped unread summary
- `show-flagged` - List flagged messages
- `weekly-review` - Past 7 days summary
- `clean-newsletters` - Archive/delete newsletter subscriptions

### System
- `check` - Trigger Mail.app to fetch new mail
- `headers` - Full email header analysis (SPF, DKIM, DMARC, hop count, return path)
- `rules` - List, enable, or disable mail rules

### Compose & Templates
- `draft` - Create email draft (supports templates)
- `templates list/create/show/delete` - Manage email templates
- `reply`, `forward` - Create response drafts
- `thread` - Show full conversation thread for a message

### Integrations
- `to-todoist` - Send email to Todoist as task
- `export` - Export messages as markdown

## 🔧 Requirements

- **macOS 12 or later** (uses AppleScript to communicate with Mail.app)
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

## 🤖 Built for AI Workflows

Every command supports `--json`, making your inbox data available to any AI assistant. Commands like `summary`, `triage`, and `context` are specifically designed to give AI a structured understanding of your inbox in seconds.

### With Claude Code
```bash
# Just ask Claude to check your mail
"Run my mail triage and tell me what's urgent"
"Summarize my unread mail and create Todoist tasks for anything that needs action"
```

### With any AI tool
```bash
# Pipe structured data to any LLM CLI
my mail summary --json | llm "What needs my attention?"

# Feed triage results to AI for prioritization
my mail triage --json | llm "Draft responses for the urgent items"
```

### For scripting and automation
```bash
# Unread count for your status bar
my mail count

# Export to JSON for any workflow
my mail inbox --json | jq '.accounts[].unread_count'
```

The CLI is the bridge between Mail.app and whatever tools you use — AI, scripts, or both.

## 🏗️ Architecture

Built with modern Python patterns:
- **Zero runtime dependencies** (stdlib only)
- **Comprehensive test suite** (292 tests across 17 test files)
- **Modular command structure** (16 focused modules)
- **AppleScript bridge** for Mail.app communication
- **Three-tier account resolution** (explicit flag → config default → last-used)

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built to automate email workflows without leaving the terminal.

## 📮 Contact

- **GitHub:** [@Jscoats](https://github.com/Jscoats)
- **Issues:** [Report bugs or request features](https://github.com/Jscoats/my-apple-mail-cli/issues)

---

**Like this project?** Star it on GitHub ⭐ and share it with fellow terminal enthusiasts!
