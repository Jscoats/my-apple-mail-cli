<h1 align="center">
  <code>mxctl</code>
</h1>

<p align="center">
  <a href="https://pypi.org/project/mxctl/"><img src="https://img.shields.io/pypi/v/mxctl.svg" alt="PyPI"></a>
  <a href="https://github.com/Jscoats/mxctl/actions/workflows/ci.yml"><img src="https://github.com/Jscoats/mxctl/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
  <a href="https://github.com/Jscoats/mxctl"><img src="https://img.shields.io/badge/coverage-100%25-brightgreen.svg" alt="Coverage: 100%"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT"></a>
</p>

> Apple Mail from your terminal.

**50 commands.** Triage with AI, batch-process newsletters, turn emails into Todoist tasks — all from the terminal. Every command supports `--json` for scripting and AI workflows. Zero external dependencies.

<p align="center">
  <img src="demo/demo.gif" alt="mxctl demo — inbox, triage, summary, and batch operations" width="700">
</p>

## Table of Contents

- [Key Features](#key-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Example Output](#example-output)
- [Command Categories](#command-categories)
- [Requirements](#requirements)
- [Usage Tips](#usage-tips)
- [Built for AI Workflows](#built-for-ai-workflows)
- [AI Demos](#ai-demos)
- [Architecture](#architecture)
- [Why Not X?](#why-not-x)
- [Contributing](#contributing)

## Key Features

- **50 Commands** - Everything from basic operations to advanced batch processing
- **Any Account, One Interface** - iCloud, Gmail, Outlook, Exchange, IMAP -- whatever Mail.app has, this works with
- **Gmail Mailbox Translation** - Automatically maps standard names (`Trash`, `Spam`, `Sent`) to Gmail's `[Gmail]/...` paths
- **Built for AI Workflows** - Every command supports `--json` output designed for AI assistants to read and act on
- **Todoist Integration** - Turn any email into a task with `mxctl to-todoist` (project, priority, due date)
- **Batch Operations with Undo** - Process hundreds of emails safely with rollback support
- **Zero Dependencies** - Pure Python stdlib, no external packages required
- **Works with Your Existing Setup** - Doesn't replace Mail.app, extends it

## Installation

```bash
# Requires Python 3.10+ and macOS
pip install mxctl

# Or with uv (faster)
uv tool install mxctl
```

Then run the setup wizard — it detects your Mail.app accounts, configures Gmail mailbox translation, and optionally connects Todoist:

<p align="center">
  <img src="demo/init-demo.gif" alt="mxctl init — setup wizard detecting accounts, configuring Gmail, and connecting Todoist" width="700">
</p>

## Quick Start

```bash
# First time? Set up your default account
mxctl init

# See what's in your inbox
mxctl inbox

# Smart summary of unread emails (concise, one-liner per email)
mxctl summary

# Triage unread emails by urgency
mxctl triage

# Search for messages
mxctl search "project update" --sender

# Mark all unread as read (with undo support!)
mxctl batch-read -m INBOX

# Oops, undo that
mxctl undo

# Create email from template
mxctl draft --to colleague@company.com --template "weekly-update"

# Send email to Todoist as a task
mxctl to-todoist 123 --project Work
```

## Example Output

### `mxctl inbox`
```
Inbox Overview
------------------------------------------
  iCloud             3 unread   (47 total)
  Work Email         12 unread  (203 total)
  Johnny.Coats84@gmail.com  0 unread  (18 total)
------------------------------------------
  Total              15 unread
```

### `mxctl triage`
```
Triage -- 15 Unread Messages
==========================================

[URGENT -- 2]
  #4821  Sarah Johnson       Re: Contract review deadline TODAY
  #4819  boss@company.com    Q4 budget approval needed

[PEOPLE -- 5]
  #4820  mom@gmail.com       Thanksgiving plans?
  #4818  john.smith@work.com Project kickoff Thursday?
  #4817  recruiter@corp.com  Opportunity at TechCorp
  #4815  friend@gmail.com    Weekend hiking trip
  #4814  alice@work.com      Coffee catch-up?

[NOTIFICATIONS -- 8]
  #4816  GitHub              [mxctl] PR #12 merged
  #4813  noreply@bank.com    Statement available
  ... and 6 more
```

### `mxctl summary`
```
15 unread -- iCloud + Work Email

* Contract review deadline TODAY -- Sarah Johnson (urgent, reply needed)
* Q4 budget approval -- boss@company.com (action required)
* Thanksgiving plans -- mom@gmail.com (personal, low urgency)
* Project kickoff Thursday -- john.smith@work.com (confirm attendance)
* PR #12 merged -- GitHub notification (no action needed)
* 10 more notifications and newsletters
```

## Command Categories

### Setup
- `init` - First-time setup wizard (auto-detects Mail accounts, configures default account and optional Todoist token)
- `ai-setup` - Configure your AI assistant to use mxctl (Claude Code, Cursor, Windsurf, Ollama, and others)

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
- `triage` - Smart categorization by urgency (flagged -> people -> notifications)
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
- `export` - Export messages as markdown (use `--to` for destination path/directory)

## Requirements

- **macOS 12 or later** (uses AppleScript to communicate with Mail.app)
- **Python 3.10+**
- **Mail.app** with at least one configured account
- **Permissions:** First run will prompt for Mail.app automation permission in System Settings
- **Note:** Mail.app will be launched automatically if it is not already running -- this is normal macOS/AppleScript behavior

## Usage Tips

### Multi-Account Support

Works with any combination of iCloud, Gmail, Outlook, Exchange, or custom IMAP accounts -- whatever you have configured in Mail.app.

```bash
# Commands default to your primary account (set during init)
mxctl list

# Switch accounts with -a
mxctl list -a "Work Email"
mxctl list -a "Personal"

# Commands like inbox, summary, and triage scan ALL accounts automatically
mxctl inbox
```

**Three-tier account resolution:** Commands use the first available: (1) explicit `-a` flag, (2) default account from config, (3) last-used account from state.

### Gmail Mailbox Translation

Gmail uses non-standard mailbox names (`[Gmail]/Spam` instead of `Junk`, `[Gmail]/Sent Mail` instead of `Sent Messages`, etc.). If you tag your Gmail accounts during `mxctl init`, the CLI auto-translates standard names so you don't have to remember Gmail's conventions.

```bash
# These just work -- no need to type [Gmail]/... paths
mxctl list -a "Work Gmail" -m Trash     # -> [Gmail]/Trash
mxctl list -a "Work Gmail" -m Spam      # -> [Gmail]/Spam
mxctl list -a "Work Gmail" -m Sent      # -> [Gmail]/Sent Mail
mxctl list -a "Work Gmail" -m Archive   # -> [Gmail]/All Mail

# iCloud and other accounts pass through unchanged
mxctl list -a "iCloud" -m Trash         # -> Trash (no translation)
```

Supported translations: `Trash`, `Spam`/`Junk`, `Sent`/`Sent Messages`, `Archive`/`All Mail`, `Drafts`, `Starred`, `Important`.

### Todoist Integration

Turn any email into a Todoist task without leaving the terminal. The task includes the email subject, sender, and a link back to the message.

```bash
# Set up during init, or add manually to ~/.config/mxctl/config.json
mxctl init  # step 3 prompts for your Todoist API token

# Send an email to Todoist
mxctl to-todoist 123

# With project and priority
mxctl to-todoist 123 --project "Work" --priority 3

# With a due date (natural language)
mxctl to-todoist 123 --due "next Monday"
```

To get your token: [Todoist Settings -> Integrations -> Developer](https://todoist.com/prefs/integrations)

### Short Message Aliases

Listing commands assign short numbers starting from `[1]` -- no more copying 5-digit IDs:

```bash
mxctl list                    # Shows [1], [2], [3]...
mxctl read 1                  # Read message [1]
mxctl flag 2                  # Flag message [2]
mxctl move 3 --to Archive     # Move message [3]
```

Aliases update each time you run a listing command (`list`, `inbox`, `search`, `triage`, `summary`, etc.). Full message IDs still work if you prefer them. JSON output includes both `id` (real) and `alias` (short number).

### JSON Output for Automation
```bash
# Every command supports --json
mxctl inbox --json | jq '.accounts[0].unread_count'
mxctl search "invoice" --json | jq '.[].subject'
```

### Export Messages
```bash
# Export a single message
mxctl export 123 --to ~/Documents/mail/ -a "iCloud"

# Bulk export all messages in a mailbox
mxctl export "Work" --to ~/Documents/mail/ -a "Work Email"

# Bulk export messages after a date
mxctl export "INBOX" --to ~/Documents/mail/ -a "iCloud" --after 2026-01-01
```

Note: The destination flag is `--to` (not `--dest`).

### Email Templates
```bash
# Create a template
mxctl templates create "meeting-followup" \
  --subject "Re: {original_subject}" \
  --body "Thanks for the meeting today..."

# Use it
mxctl draft --to client@company.com --template "meeting-followup"
```

## Built for AI Workflows

Every command supports `--json`, making your inbox data available to any AI assistant. Commands like `summary`, `triage`, and `context` are specifically designed to give AI a structured understanding of your inbox in seconds.

### Pointing Your AI Assistant to mxctl

For an AI assistant to use mxctl effectively, it needs to know the tool is available. The fastest way is the built-in setup command:

```bash
mxctl ai-setup
```

It walks you through selecting your AI assistant (Claude Code, Cursor, or Windsurf), previews the snippet it will write, and asks for confirmation before touching any file. Run it once; skip it any time you don't need it.

#### Manual setup

If you prefer to set things up yourself, add this block to your assistant's context file (`~/.claude/CLAUDE.md` for Claude Code, `.cursorrules` for Cursor, `.windsurfrules` for Windsurf):

````markdown
## mxctl — Apple Mail CLI

`mxctl` manages Apple Mail from the terminal. Use it to read, triage, and act on email without opening Mail.app.

Key commands:
- `mxctl inbox` — unread counts across all accounts
- `mxctl triage` — categorize unread mail by urgency
- `mxctl summary` — concise one-liner per unread message
- `mxctl list [-a ACCOUNT] [--unread] [--limit N]` — list messages
- `mxctl read ID [-a ACCOUNT] [-m MAILBOX]` — read a message
- `mxctl search QUERY [--sender]` — search messages
- `mxctl mark-read ID` / `mxctl flag ID` — message actions
- `mxctl batch-move --from-sender ADDR --to-mailbox MAILBOX` — bulk move
- `mxctl batch-delete --older-than DAYS -m MAILBOX` — bulk delete
- `mxctl undo` — roll back the last batch operation
- `mxctl to-todoist ID --project NAME` — turn an email into a task

Add `--json` to any command for structured output. Run `mxctl --help` for all 50 commands.
Default account is set in `~/.config/mxctl/config.json`. Use `-a "Account Name"` to switch accounts.
````

#### Local AI (Ollama, LM Studio, Aider, etc.)

For local models, use `--print` to dump the raw snippet and pipe it wherever you need:

```bash
# Copy to clipboard
mxctl ai-setup --print | pbcopy

# Append to an Ollama Modelfile
mxctl ai-setup --print >> ~/Modelfile

# Save as a reusable system prompt file
mxctl ai-setup --print > ~/.config/mxctl-prompt.md

# Pass to Aider
mxctl ai-setup --print > .aider.prompt.md
```

`--print` outputs clean markdown with no interactive prompts — it's designed for piping.

#### Ad-hoc: inject the full command list on demand

For a one-off session with any AI tool, paste the full command reference directly into the chat:

```bash
mxctl --help
```

The output is concise enough to fit in any context window and gives the AI everything it needs to pick the right command.

### With Claude Code
```bash
# Just ask Claude to check your mail
"Run mxctl triage and tell me what's urgent"
"Summarize my unread mail and create Todoist tasks for anything that needs action"
```

### With any AI tool
```bash
# Pipe structured data to any LLM CLI
mxctl summary --json | llm "What needs my attention?"

# Feed triage results to AI for prioritization
mxctl triage --json | llm "Draft responses for the urgent items"
```

### For scripting and automation
```bash
# Unread count for your status bar
mxctl count

# Export to JSON for any workflow
mxctl inbox --json | jq '.accounts[].unread_count'
```

The CLI is the bridge between Mail.app and whatever tools you use -- AI, scripts, or both.

## AI Demos

These demos show how an AI assistant (like Claude Code) uses mxctl to manage your inbox conversationally. You say what you want in plain English, and the AI picks the right commands, checks before acting, and reports back.

### Inbox triage and drafting

The AI triages your inbox, marks newsletters as read, flags important messages for follow-up, and drafts a reply to your mom -- all from a single request.

<p align="center">
  <img src="demo/ai-demo.gif" alt="AI assistant triaging inbox, flagging messages, and drafting a reply" width="700">
</p>

### Bulk sender cleanup

The AI finds your noisiest senders, dry-runs the deletes so you can see what would be removed, then cleans up 60 marketing emails in seconds. Everything is undoable with `mxctl undo`.

<p align="center">
  <img src="demo/batch-delete-demo.gif" alt="AI assistant finding top spammy senders and batch-deleting 60 messages" width="700">
</p>

### Newsletter unsubscribe

The AI analyzes which newsletters you actually read vs. ignore, then unsubscribes from the ones with 0% open rate while leaving the ones you engage with. One-click unsubscribe when the header supports it, browser fallback when it doesn't.

<p align="center">
  <img src="demo/unsubscribe-demo.gif" alt="AI assistant analyzing newsletter read rates and unsubscribing from unread ones" width="700">
</p>

## Architecture

Built with modern Python patterns:
- **Zero runtime dependencies** (stdlib only)
- **Comprehensive test suite** (673 tests)
- **Modular command structure** (16 focused modules)
- **AppleScript bridge** for Mail.app communication
- **Three-tier account resolution** (explicit flag -> config default -> last-used)

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

## Why Not X?

| | **mxctl** | **mutt/neomutt** | **Gmail/Outlook API** | **Raw AppleScript** |
|---|---|---|---|---|
| **Approach** | Extends Mail.app | Replaces Mail.app | Per-provider SDK | DIY scripting |
| **Multi-account** | Any account in Mail.app | Config per account | Separate auth per provider | Manual per account |
| **macOS integration** | Notifications, Rules, Continuity | None (terminal-only) | None | Partial |
| **Structured output** | `--json` on every command | Text only | JSON (provider-specific) | Raw text |
| **AI-ready** | Built for it (triage, summary) | No | Build it yourself | No |
| **Batch + undo** | Built-in with rollback | No undo | Build it yourself | No |
| **Setup** | `pip install mxctl && mxctl init` | Extensive config | OAuth flows + API keys | Write your own scripts |
| **Dependencies** | Zero (stdlib only) | Varies | SDK + auth libraries | None |

**In short:** mutt replaces Mail.app (you lose macOS integration). Provider APIs lock you into one service. Raw AppleScript works but you're building everything from scratch. mxctl gives you 50 structured commands on top of the Mail.app you already use.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

Built to automate email workflows without leaving the terminal.

## Contact

- **GitHub:** [@Jscoats](https://github.com/Jscoats)
- **Issues:** [Report bugs or request features](https://github.com/Jscoats/mxctl/issues)

---

**Like this project?** Star it on GitHub and share it with fellow terminal enthusiasts!
