"""Setup wizard for first-time configuration: init, ai-setup."""

import os
import re
import sys
import termios
import tty

from mxctl import __version__
from mxctl.config import (  # noqa: F401 — CONFIG_DIR imported for test monkeypatching
    CONFIG_DIR,
    CONFIG_FILE,
    FIELD_SEPARATOR,
    _save_json,
    get_config,
)
from mxctl.util.applescript import run
from mxctl.util.formatting import format_output

# ANSI helpers
_G = "\x1b[1;32m"  # bold green
_C = "\x1b[1;36m"  # bold cyan
_D = "\x1b[90m"  # dim gray
_B = "\x1b[1m"  # bold
_R = "\x1b[0m"  # reset
_W = "\x1b[1;37m"  # bold white

_BANNER = f"""{_C}
                    _   _
                   | | | |
 _ __ _____  ___| |_| |
| '_ ` _ \\ \\/ / __| __| |
| | | | | |>  < (__| |_| |
|_| |_| |_/_/\\_\\___|\\__|_|{_R}

  {_B}Apple Mail from your terminal{_R} {_D}— v{__version__}{_R}
  {_D}─────────────────────────────────────────{_R}
"""

# Styled key hints for the hint bar
_K_ARROWS = f"{_D}↑/↓{_R}"
_K_SPACE = f"{_G}[Space]{_R}"
_K_ENTER = f"{_W}[Enter]{_R}"
_K_CANCEL = f"{_D}Ctrl+C cancel{_R}"

_HINT_RADIO = f"  {_K_ARROWS} navigate   {_K_SPACE} select   {_K_ENTER} confirm   {_K_CANCEL}"
_HINT_CHECKBOX = f"  {_K_ARROWS} navigate   {_K_SPACE} toggle   {_K_ENTER} confirm   {_K_CANCEL}"


def _is_interactive() -> bool:
    """True when running in a real terminal (not a pipe or test)."""
    if os.environ.get("CI") or os.environ.get("MY_CLI_NON_INTERACTIVE"):
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()


def _radio_select(prompt: str, options: list[str]) -> int:
    """Arrow-key single-select.  Returns chosen index.
    Raises KeyboardInterrupt on Ctrl+C.
    """
    current = 0
    n = len(options)

    def _render(first: bool = False) -> None:
        # In raw mode \n doesn't imply \r — always use \r\n explicitly.
        w = sys.stdout.write
        if not first:
            w(f"\r\x1b[{n + 1}A\x1b[J")
        w(f"{_B}{prompt}{_R}\r\n")
        for i, opt in enumerate(options):
            if i == current:
                w(f"  {_G}(●) {opt}{_R}\r\n")
            else:
                w(f"  ( ) {opt}\r\n")
        w(_HINT_RADIO)
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        _render(first=True)
        while True:
            ch = os.read(fd, 1)
            if ch == b"\x1b":
                seq = os.read(fd, 2)
                if seq == b"[A":
                    current = (current - 1) % n
                elif seq == b"[B":
                    current = (current + 1) % n
            elif ch in (b"\r", b"\n", b" "):
                break
            elif ch == b"\x03":
                raise KeyboardInterrupt
            _render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    sys.stdout.write(f"\r\x1b[{n + 1}A\x1b[J")
    print(f"{_B}{prompt}{_R}  {_G}{options[current]}{_R}")
    return current


def _checkbox_select(prompt: str, options: list[str]) -> list[int]:
    """Arrow-key multi-select with Space to toggle.
    Returns sorted list of selected indices.
    Raises KeyboardInterrupt on Ctrl+C.
    """
    current = 0
    selected: set[int] = set()
    n = len(options)

    def _render(first: bool = False) -> None:
        # In raw mode \n doesn't imply \r — always use \r\n explicitly.
        w = sys.stdout.write
        if not first:
            w(f"\r\x1b[{n + 1}A\x1b[J")
        w(f"{_B}{prompt}{_R}\r\n")
        for i, opt in enumerate(options):
            box = f"{_G}[x]{_R}" if i in selected else "[ ]"
            if i == current:
                w(f"  {_G}{box} {opt}{_R}\r\n")
            else:
                w(f"  {box} {opt}\r\n")
        w(_HINT_CHECKBOX)
        sys.stdout.flush()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        _render(first=True)
        while True:
            ch = os.read(fd, 1)
            if ch == b"\x1b":
                seq = os.read(fd, 2)
                if seq == b"[A":
                    current = (current - 1) % n
                elif seq == b"[B":
                    current = (current + 1) % n
            elif ch == b" ":
                selected.symmetric_difference_update({current})
            elif ch in (b"\r", b"\n"):
                break
            elif ch == b"\x03":
                raise KeyboardInterrupt
            _render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    result = sorted(selected)
    sys.stdout.write(f"\r\x1b[{n + 1}A\x1b[J")
    if result:
        names = ", ".join(options[i] for i in result)
        print(f"{_B}{prompt}{_R}  {_G}{names}{_R}")
    else:
        print(f"{_B}{prompt}{_R}  {_D}(none){_R}")
    return result


def _step_header(step: int, total: int, title: str, hint: str) -> None:
    """Print a step header with number, title, and context hint."""
    print(f"\n  {_C}Step {step}/{total}{_R} {_D}·{_R} {_B}{title}{_R}")
    print(f"  {_D}{hint}{_R}\n")


# ---------------------------------------------------------------------------
# AI assistant setup
# ---------------------------------------------------------------------------

_SNIPPET_MARKER = "## mxctl — Apple Mail CLI"

_MXCTL_AI_SNIPPET = """\

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
"""

_AI_TOOL_NAMES = ["Claude Code", "Cursor", "Windsurf", "Other (copy-paste)", "Skip"]

# (path_template, scope)
# scope "global"  → expand ~ and write to user home area
# scope "project" → join with os.getcwd() and write to current directory
_AI_TOOL_TARGETS: dict[str, tuple[str, str]] = {
    "Claude Code": ("~/.claude/CLAUDE.md", "global"),
    "Cursor": (".cursorrules", "project"),
    "Windsurf": (".windsurfrules", "project"),
}


def cmd_ai_setup(args) -> None:
    """Configure an AI assistant to use mxctl."""
    # --print: dump raw snippet to stdout and exit (no wizard, pipeable)
    if getattr(args, "print_snippet", False):
        sys.stdout.write(_MXCTL_AI_SNIPPET.lstrip("\n"))
        return

    print(f"\n  {_B}mxctl AI Assistant Setup{_R}")
    print(f"  {_D}Add mxctl to your AI assistant's context so it knows your commands.{_R}\n")

    # --- Select tool ---
    if _is_interactive():
        try:
            idx = _radio_select("  Which AI assistant do you use?", _AI_TOOL_NAMES)
        except KeyboardInterrupt:
            print(f"\n  {_D}Setup cancelled.{_R}")
            return
        tool = _AI_TOOL_NAMES[idx]
    else:
        print("  AI assistants:")
        for i, name in enumerate(_AI_TOOL_NAMES, start=1):
            print(f"    {i}. {name}")
        while True:
            try:
                raw = input(f"\n  Select [1-{len(_AI_TOOL_NAMES)}]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n  {_D}Setup cancelled.{_R}")
                return
            if raw.isdigit() and 1 <= int(raw) <= len(_AI_TOOL_NAMES):
                tool = _AI_TOOL_NAMES[int(raw) - 1]
                break
            print(f"  Please enter a number between 1 and {len(_AI_TOOL_NAMES)}.")

    if tool == "Skip":
        print(f"  {_D}Skipped.{_R}")
        return

    if tool == "Other (copy-paste)":
        print(f"\n  {_B}Copy this into your AI assistant's context or rules file:{_R}\n")
        print(_MXCTL_AI_SNIPPET)
        return

    # --- Resolve target path ---
    path_template, scope = _AI_TOOL_TARGETS[tool]
    if scope == "global":
        target = os.path.expanduser(path_template)
    else:
        target = os.path.join(os.getcwd(), path_template)

    print(f"  {_D}Target: {target}{_R}")

    # --- Already configured? ---
    if os.path.isfile(target):
        with open(target) as f:
            existing = f.read()
        if _SNIPPET_MARKER in existing:
            print(f"  {_G}✓{_R} mxctl is already configured in {os.path.basename(target)}.")
            if getattr(args, "json", False):
                format_output(args, "", json_data={"status": "already_configured", "file": target})
            return

    # --- Preview ---
    print(f"\n  {_B}The following will be appended to {os.path.basename(target)}:{_R}\n")
    for line in _MXCTL_AI_SNIPPET.strip().splitlines():
        print(f"  {_D}{line}{_R}")
    print()

    # --- Confirm ---
    try:
        answer = input(f"  Write to {os.path.basename(target)}? [{_B}Y{_R}/{_B}n{_R}]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {_D}Cancelled.{_R}")
        return

    if answer == "n":
        print(f"  {_D}Cancelled.{_R}")
        return

    # --- Write ---
    dir_path = os.path.dirname(target)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(target, "a") as f:
        f.write(_MXCTL_AI_SNIPPET)

    scope_note = (
        "This applies globally to all Claude Code sessions."
        if scope == "global"
        else f"This applies to the current project ({os.getcwd()})."
    )
    print(f"\n  {_G}Done!{_R} mxctl added to {target}")
    print(f"  {_D}{scope_note}{_R}")

    if getattr(args, "json", False):
        format_output(args, "", json_data={"status": "written", "file": target})


def cmd_init(args) -> None:
    """Interactive setup wizard to configure mxctl."""
    print(_BANNER)

    # Check for existing config
    if os.path.isfile(CONFIG_FILE):
        existing = get_config()
        default_acct = existing.get("mail", {}).get("default_account") or existing.get("default_account", "")
        print(f"  {_D}Existing config found. Default account:{_R} {_B}{default_acct or '(none)'}{_R}")
        try:
            answer = input(f"  Reconfigure? [{_B}y{_R}/{_B}N{_R}]: ").strip().lower()
        except KeyboardInterrupt:
            print(f"\n  {_D}Setup cancelled.{_R}")
            return
        except EOFError:
            answer = "n"
        if answer != "y":
            print(f"  {_D}Keeping existing configuration.{_R}")
            if getattr(args, "json", False):
                format_output(args, "", json_data=existing)
            return

    # Detect accounts via AppleScript
    script = f"""
tell application "Mail"
    set output to ""
    repeat with acct in (every account)
        set acctName to name of acct
        set acctEmail to user name of acct
        set acctEnabled to enabled of acct
        set output to output & acctName & "{FIELD_SEPARATOR}" & acctEmail & "{FIELD_SEPARATOR}" & acctEnabled & linefeed
    end repeat
    return output
end tell
"""
    result = run(script)

    if not result.strip():
        print(f"  {_G}!{_R} No mail accounts found. Make sure Mail.app is configured.")
        return

    # Parse accounts
    accounts = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 3:
            name, email, enabled_str = parts[0], parts[1], parts[2]
            accounts.append(
                {
                    "name": name,
                    "email": email,
                    "enabled": enabled_str.strip().lower() == "true",
                }
            )

    enabled_accounts = [a for a in accounts if a["enabled"]]

    if not enabled_accounts:
        print(f"  {_G}!{_R} No enabled mail accounts found.")
        return

    total_steps = 3

    # --- Step 1: Select primary account ---
    _step_header(1, total_steps, "Default Account", "Which account should commands use when you don't specify -a?")

    if len(enabled_accounts) == 1:
        chosen = enabled_accounts[0]
        print(f"  {_G}Auto-selected:{_R} {chosen['name']} ({chosen['email']})")
    elif _is_interactive():
        try:
            opts = [f"{a['name']} ({a['email']})" for a in enabled_accounts]
            idx = _radio_select("  Select primary account:", opts)
            chosen = enabled_accounts[idx]
        except KeyboardInterrupt:
            print(f"\n  {_D}Setup cancelled.{_R}")
            return
    else:
        # Non-interactive fallback (tests, pipes)
        print("  Available mail accounts:")
        for i, acct in enumerate(enabled_accounts, start=1):
            print(f"    {i}. {acct['name']} ({acct['email']})")
        while True:
            try:
                raw = input(f"\n  Select primary account [1-{len(enabled_accounts)}]: ").strip()
            except KeyboardInterrupt:
                print(f"\n  {_D}Setup cancelled.{_R}")
                return
            except EOFError:
                raw = "1"
            if raw.isdigit() and 1 <= int(raw) <= len(enabled_accounts):
                chosen = enabled_accounts[int(raw) - 1]
                break
            print(f"  Please enter a number between 1 and {len(enabled_accounts)}.")

    # --- Step 2: Select Gmail accounts ---
    _step_header(2, total_steps, "Gmail Accounts", "Gmail uses different mailbox names ([Gmail]/Spam instead of Junk).")

    gmail_accounts: list[str] = []
    if len(enabled_accounts) == 1:
        try:
            ans = input(f"  Is '{enabled_accounts[0]['name']}' a Gmail account? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            ans = "n"
        if ans == "y":
            gmail_accounts = [enabled_accounts[0]["name"]]
    elif _is_interactive():
        try:
            opts = [f"{a['name']} ({a['email']})" for a in enabled_accounts]
            indices = _checkbox_select("  Select your Gmail accounts:", opts)
            gmail_accounts = [enabled_accounts[i]["name"] for i in indices]
        except KeyboardInterrupt:
            print(f"\n  {_D}Setup cancelled.{_R}")
            return
    else:
        # Non-interactive fallback
        print("  Enter numbers separated by commas, or press Enter to skip.")
        for i, acct in enumerate(enabled_accounts, start=1):
            print(f"    {i}. {acct['name']} ({acct['email']})")
        try:
            raw_gmail = input("  Gmail accounts: ").strip()
        except (KeyboardInterrupt, EOFError):
            raw_gmail = ""
        if raw_gmail:
            for part in raw_gmail.split(","):
                part = part.strip()
                if part.isdigit() and 1 <= int(part) <= len(enabled_accounts):
                    gmail_accounts.append(enabled_accounts[int(part) - 1]["name"])

    if gmail_accounts:
        print(f"  {_D}Mailbox names will auto-translate for: {', '.join(gmail_accounts)}{_R}")

    # --- Step 3: Todoist API token ---
    _step_header(3, total_steps, "Todoist Integration", "Turn emails into tasks with `mxctl to-todoist`.")
    print(f"  {_D}Get your token: Todoist Settings > Integrations > Developer{_R}")

    todoist_token = ""
    try:
        raw_token = input(f"\n  API token {_D}(Enter to skip){_R}: ").strip()
    except KeyboardInterrupt:
        print(f"\n  {_D}Setup cancelled.{_R}")
        return
    except EOFError:
        raw_token = ""
    if raw_token:
        if not re.match(r"^[a-f0-9]{40}$", raw_token):
            print(f"  {_D}Warning: Doesn't match expected format (40 hex chars). Saving anyway.{_R}")
        todoist_token = raw_token

    # Build and write config
    config: dict = {
        "mail": {
            "default_account": chosen["name"],
        }
    }
    if gmail_accounts:
        config["mail"]["gmail_accounts"] = gmail_accounts
    if todoist_token:
        config["todoist_api_token"] = todoist_token

    _save_json(CONFIG_FILE, config)

    # Success output
    summary_parts = [f"{chosen['name']}"]
    if gmail_accounts:
        summary_parts.append(f"Gmail: {len(gmail_accounts)} account{'s' if len(gmail_accounts) != 1 else ''}")
    if todoist_token:
        summary_parts.append("Todoist: connected")

    success_text = (
        f"\n  {_G}Setup complete!{_R}\n\n"
        f"  {_D}Config saved to {CONFIG_FILE}{_R}\n"
        f"  {_B}{' · '.join(summary_parts)}{_R}\n"
        f"\n  {_B}Get started:{_R}\n"
        f"    {_G}mxctl inbox{_R}       {_D}Unread counts across all accounts{_R}\n"
        f"    {_G}mxctl summary{_R}     {_D}AI-concise one-liner per unread{_R}\n"
        f"    {_G}mxctl triage{_R}      {_D}Unread grouped by urgency{_R}\n"
        f"    {_G}mxctl --help{_R}      {_D}See all 50 commands{_R}\n"
        f"\n  {_B}Using an AI assistant?{_R}\n"
        f"    {_G}mxctl ai-setup{_R}    {_D}Point Claude Code, Cursor, or Windsurf at mxctl{_R}\n"
    )

    if getattr(args, "json", False):
        redacted = dict(config)
        if "todoist_api_token" in redacted:
            redacted = {**redacted, "todoist_api_token": "****"}
        format_output(args, success_text, json_data=redacted)
    else:
        print(success_text)


def register(subparsers) -> None:
    p = subparsers.add_parser("init", help="Setup wizard for first-time configuration")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_init)

    p2 = subparsers.add_parser(
        "ai-setup",
        help="Configure your AI assistant to use mxctl (Claude Code, Cursor, Windsurf, Ollama, and others)",
    )
    p2.add_argument("--json", action="store_true", help="Output as JSON")
    p2.add_argument(
        "--print",
        action="store_true",
        dest="print_snippet",
        help="Print the raw snippet to stdout and exit (for piping into Modelfiles, system prompts, etc.)",
    )
    p2.set_defaults(func=cmd_ai_setup)
