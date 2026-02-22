"""Todoist integration: create tasks from emails."""

import json
import ssl
import urllib.request
import urllib.error

from my_cli.config import (
    FIELD_SEPARATOR,
    get_config,
)
from my_cli.util.applescript import run, validate_msg_id
from my_cli.util.formatting import die, format_output
from my_cli.util.mail_helpers import resolve_message_context


# ---------------------------------------------------------------------------
# to-todoist — create a Todoist task from an email
# ---------------------------------------------------------------------------

def cmd_to_todoist(args) -> None:
    """Create a Todoist task from an email."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    project = getattr(args, "project", None)
    priority = getattr(args, "priority", 1)
    due = getattr(args, "due", None)

    # Get Todoist API token from config
    cfg = get_config()
    token = cfg.get("todoist_api_token")
    if not token:
        die("Todoist API token not configured. Add 'todoist_api_token' to ~/.config/my/config.json")

    ssl_context = ssl.create_default_context()

    # Read the email via AppleScript
    script = f"""
    tell application "Mail"
        set mb to mailbox "{mb_escaped}" of account "{acct_escaped}"
        set theMsg to first message of mb whose id is {message_id}
        set msgSubject to subject of theMsg
        set msgSender to sender of theMsg
        set msgDate to date received of theMsg
        return msgSubject & "{FIELD_SEPARATOR}" & msgSender & "{FIELD_SEPARATOR}" & (msgDate as text)
    end tell
    """

    result = run(script)
    parts = result.split(FIELD_SEPARATOR)
    if len(parts) < 3:
        die(f"Failed to read message {message_id}.")

    subject, sender, date = parts[0], parts[1], parts[2]

    # Resolve project name to ID if provided
    project_id = None
    if project:
        projects_req = urllib.request.Request(
            "https://api.todoist.com/rest/v2/projects",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(projects_req, context=ssl_context) as resp:
                projects = json.loads(resp.read().decode("utf-8"))
            match = next((p for p in projects if p.get("name", "").lower() == project.lower()), None)
            if match is None:
                die(f"Todoist project '{project}' not found. Check the name and try again.")
            project_id = match["id"]
        except urllib.error.HTTPError as e:
            die(f"Todoist API error resolving project ({e.code}): {e.read().decode('utf-8')}")
        except urllib.error.URLError as e:
            die(f"Network error resolving project: {e.reason}")

    # Build Todoist task payload
    task_data = {
        "content": subject,
        "description": f"From: {sender}\nDate: {date}\nMessage ID: {message_id}",
        "priority": priority,
    }
    if project_id:
        task_data["project_id"] = project_id
    if due:
        task_data["due_string"] = due

    # Make request to Todoist API
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(task_data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            response_data = json.loads(response.read().decode("utf-8"))
            task_url = response_data.get("url")

            text = f"Created Todoist task: {subject}"
            if task_url:
                text += f"\nURL: {task_url}"

            format_output(args, text, json_data=response_data)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        die(f"Todoist API error ({e.code}): {error_body}")
    except urllib.error.URLError as e:
        die(f"Network error: {e.reason}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers) -> None:
    # to-todoist
    p = subparsers.add_parser("to-todoist", help="Create Todoist task from email")
    p.add_argument("id", type=int, help="Message ID")
    p.add_argument("-a", "--account", help="Mail account name")
    p.add_argument("-m", "--mailbox", help="Mailbox name (default: INBOX)")
    p.add_argument("--project", help="Todoist project name (resolves to project ID via API; task goes to Inbox if omitted)")
    p.add_argument("--priority", type=int, choices=[1, 2, 3, 4], default=1, help="Priority (1-4, 4=highest)")
    p.add_argument("--due", help="Due date (natural language, e.g. 'tomorrow')")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_to_todoist)
