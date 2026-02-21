"""Setup wizard for first-time configuration: init."""

import json
import os

from my_cli.config import CONFIG_DIR, CONFIG_FILE, FIELD_SEPARATOR, get_config
from my_cli.util.applescript import run
from my_cli.util.formatting import format_output


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
    script = """
tell application "Mail"
    set output to ""
    repeat with acct in (every account)
        set acctName to name of acct
        set acctEmail to user name of acct
        set acctEnabled to enabled of acct
        set output to output & acctName & "\x1F" & acctEmail & "\x1F" & acctEnabled & linefeed
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

    # Auto-select if only one enabled account
    if len(enabled_accounts) == 1:
        chosen = enabled_accounts[0]
        print(f"Auto-selected the only enabled account: {chosen['name']} ({chosen['email']})")
    else:
        # Display numbered list
        print("\nAvailable mail accounts:")
        for i, acct in enumerate(enabled_accounts, start=1):
            print(f"  {i}. {acct['name']} ({acct['email']})")

        while True:
            try:
                raw = input(f"\nSelect account [1-{len(enabled_accounts)}]: ").strip()
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
                return
            except EOFError:
                raw = "1"
            if raw.isdigit() and 1 <= int(raw) <= len(enabled_accounts):
                chosen = enabled_accounts[int(raw) - 1]
                break
            print(f"Please enter a number between 1 and {len(enabled_accounts)}.")

    # Optionally ask for Todoist API token
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
    config = {
        "mail": {
            "default_account": chosen["name"],
        }
    }
    if todoist_token:
        config["todoist_api_token"] = todoist_token

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    # Success output
    success_text = (
        f"\nConfiguration saved to {CONFIG_FILE}\n"
        f"  Default account: {chosen['name']} ({chosen['email']})\n"
    )
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
