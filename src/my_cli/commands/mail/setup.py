"""Setup wizard for first-time configuration: init."""

import os
import sys
import tty
import termios

from my_cli.config import CONFIG_DIR, CONFIG_FILE, FIELD_SEPARATOR, get_config, _save_json  # noqa: F401 — CONFIG_DIR imported for test monkeypatching
from my_cli.util.applescript import run
from my_cli.util.formatting import format_output

# ANSI helpers
_G = "\x1b[1;32m"   # bold green
_D = "\x1b[90m"     # dim gray
_B = "\x1b[1m"      # bold
_R = "\x1b[0m"      # reset
_W = "\x1b[1;37m"   # bold white

# Styled key hints for the hint bar
_K_ARROWS = f"{_D}↑/↓{_R}"
_K_SPACE  = f"{_G}[Space]{_R}"
_K_ENTER  = f"{_W}[Enter]{_R}"
_K_CANCEL = f"{_D}Ctrl+C cancel{_R}"

_HINT_RADIO    = f"  {_K_ARROWS} navigate   {_K_SPACE} select   {_K_ENTER} confirm   {_K_CANCEL}"
_HINT_CHECKBOX = f"  {_K_ARROWS} navigate   {_K_SPACE} toggle   {_K_ENTER} confirm   {_K_CANCEL}"


def _is_interactive() -> bool:
    """True when running in a real terminal (not a pipe or test)."""
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


def cmd_init(args) -> None:
    """Interactive setup wizard to configure the my mail CLI."""
    # Check for existing config
    if os.path.isfile(CONFIG_FILE):
        existing = get_config()
        default_acct = existing.get("mail", {}).get("default_account") or existing.get("default_account", "")
        print(f"Existing config found. Default account: {default_acct or '(none)'}")
        try:
            answer = input("Reconfigure? [y/N]: ").strip().lower()
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            return
        except EOFError:
            answer = "n"
        if answer != "y":
            print("Keeping existing configuration.")
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
        print("Error: No mail accounts found. Make sure Mail.app is configured.")
        return

    # Parse accounts
    accounts = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(FIELD_SEPARATOR)
        if len(parts) >= 3:
            name, email, enabled_str = parts[0], parts[1], parts[2]
            accounts.append({
                "name": name,
                "email": email,
                "enabled": enabled_str.strip().lower() == "true",
            })

    enabled_accounts = [a for a in accounts if a["enabled"]]

    if not enabled_accounts:
        print("Error: No enabled mail accounts found.")
        return

    # --- Select primary account ---
    if len(enabled_accounts) == 1:
        chosen = enabled_accounts[0]
        print(f"Auto-selected the only enabled account: {chosen['name']} ({chosen['email']})")
    elif _is_interactive():
        try:
            opts = [f"{a['name']} ({a['email']})" for a in enabled_accounts]
            idx = _radio_select("Select primary account:", opts)
            chosen = enabled_accounts[idx]
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            return
    else:
        # Non-interactive fallback (tests, pipes)
        print("\nAvailable mail accounts:")
        for i, acct in enumerate(enabled_accounts, start=1):
            print(f"  {i}. {acct['name']} ({acct['email']})")
        while True:
            try:
                raw = input(f"\nSelect primary account [1-{len(enabled_accounts)}]: ").strip()
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
                return
            except EOFError:
                raw = "1"
            if raw.isdigit() and 1 <= int(raw) <= len(enabled_accounts):
                chosen = enabled_accounts[int(raw) - 1]
                break
            print(f"Please enter a number between 1 and {len(enabled_accounts)}.")

    # --- Select Gmail accounts ---
    gmail_accounts: list[str] = []
    if len(enabled_accounts) == 1:
        try:
            ans = input(f"\nIs '{enabled_accounts[0]['name']}' a Gmail account? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            ans = "n"
        if ans == "y":
            gmail_accounts = [enabled_accounts[0]["name"]]
    elif _is_interactive():
        try:
            opts = [f"{a['name']} ({a['email']})" for a in enabled_accounts]
            indices = _checkbox_select("Which accounts are Gmail?", opts)
            gmail_accounts = [enabled_accounts[i]["name"] for i in indices]
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            return
    else:
        # Non-interactive fallback
        print("\nWhich accounts are Gmail? (enables automatic mailbox name translation)")
        print("Enter numbers separated by commas, or press Enter to skip.")
        for i, acct in enumerate(enabled_accounts, start=1):
            print(f"  {i}. {acct['name']} ({acct['email']})")
        try:
            raw_gmail = input("Gmail accounts: ").strip()
        except (KeyboardInterrupt, EOFError):
            raw_gmail = ""
        if raw_gmail:
            for part in raw_gmail.split(","):
                part = part.strip()
                if part.isdigit() and 1 <= int(part) <= len(enabled_accounts):
                    gmail_accounts.append(enabled_accounts[int(part) - 1]["name"])

    if gmail_accounts:
        print("  Mailbox names like 'Spam', 'Trash', 'Sent' will auto-map to [Gmail]/... equivalents.")

    # --- Todoist API token ---
    todoist_token = ""
    try:
        raw_token = input("\nTodoist API token (press Enter to skip): ").strip()
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        return
    except EOFError:
        raw_token = ""
    if raw_token:
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
    success_text = (
        f"\nConfiguration saved to {CONFIG_FILE}\n"
        f"  Default account: {chosen['name']} ({chosen['email']})\n"
    )
    if gmail_accounts:
        success_text += f"  Gmail accounts: {', '.join(gmail_accounts)}\n"
    if todoist_token:
        success_text += "  Todoist token: saved\n"
    success_text += (
        "\nTry these commands to get started:\n"
        "  my mail inbox          # unread counts\n"
        "  my mail list           # recent messages\n"
        "  my mail summary        # AI-concise unread\n"
    )

    if getattr(args, "json", False):
        format_output(args, success_text, json_data=config)
    else:
        print(success_text)


def register(subparsers) -> None:
    p = subparsers.add_parser("init", help="Setup wizard for first-time configuration")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_init)
