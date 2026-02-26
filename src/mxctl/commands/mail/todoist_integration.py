"""Todoist integration: create tasks from emails."""

import json
import ssl
import urllib.error
import urllib.request

from mxctl.config import (
    APPLESCRIPT_TIMEOUT_SHORT,
    FIELD_SEPARATOR,
    get_config,
)
from mxctl.util.applescript import run, validate_msg_id
from mxctl.util.formatting import die, format_output
from mxctl.util.mail_helpers import resolve_message_context

# ---------------------------------------------------------------------------
# to-todoist — create a Todoist task from an email
# ---------------------------------------------------------------------------


def create_todoist_task(
    account: str,
    mailbox: str,
    acct_escaped: str,
    mb_escaped: str,
    message_id: int,
    project: str | None = None,
    priority: int = 1,
    due: str | None = None,
) -> dict:
    """Create a Todoist task from an email message. Returns the Todoist API response dict.

    Has Mail.app side effects (reads email) and network side effects (creates Todoist task).
    """
    cfg = get_config()
    token = cfg.get("todoist_api_token")
    if not token:
        die("Todoist API token not configured. Add 'todoist_api_token' to ~/.config/mxctl/config.json")
    if not isinstance(token, str) or not token.strip():
        die("Todoist API token is invalid. Check 'todoist_api_token' in ~/.config/mxctl/config.json")

    ssl_context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")

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

    result = run(script, timeout=APPLESCRIPT_TIMEOUT_SHORT)
    parts = result.split(FIELD_SEPARATOR)
    if len(parts) < 3:
        die(f"Failed to read message {message_id}.")

    subject, sender, date = parts[0], parts[1], parts[2]

    # Resolve project name to ID if provided
    project_id = None
    if project:
        projects_req = urllib.request.Request(
            "https://api.todoist.com/api/v1/projects",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(projects_req, context=ssl_context, timeout=APPLESCRIPT_TIMEOUT_SHORT) as resp:
                projects_data = json.loads(resp.read().decode("utf-8"))
            # API v1 returns paginated {"results": [...], "next_cursor": ...}
            projects = projects_data.get("results", projects_data) if isinstance(projects_data, dict) else projects_data
            match = next((p for p in projects if p.get("name", "").lower() == project.lower()), None)
            if match is None:
                die(f"Todoist project '{project}' not found. Check the name and try again.")
            project_id = match["id"]
        except (ssl.SSLError, ssl.CertificateError):
            die("SSL certificate error. Try running: /usr/bin/python3 /Applications/Python*/Install\\ Certificates.command")
        except urllib.error.HTTPError as e:
            die(f"Todoist API error resolving project ({e.code}): {e.read().decode('utf-8')}")
        except urllib.error.URLError as e:
            die(f"Network error resolving project: {e.reason}")
        except TimeoutError:
            die(f"Todoist API timed out resolving project (>{APPLESCRIPT_TIMEOUT_SHORT}s). Check your network or try again.")

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
    url = "https://api.todoist.com/api/v1/tasks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(task_data).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ssl_context, timeout=APPLESCRIPT_TIMEOUT_SHORT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (ssl.SSLError, ssl.CertificateError):
        die("SSL certificate error. Try running: /usr/bin/python3 /Applications/Python*/Install\\ Certificates.command")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        die(f"Todoist API error ({e.code}): {error_body}")
    except urllib.error.URLError as e:
        die(f"Network error: {e.reason}")
    except TimeoutError:
        die(f"Todoist API timed out creating task (>{APPLESCRIPT_TIMEOUT_SHORT}s). Check your network or try again.")


def cmd_to_todoist(args) -> None:
    """Create a Todoist task from an email."""
    account, mailbox, acct_escaped, mb_escaped = resolve_message_context(args)
    message_id = validate_msg_id(args.id)
    project = getattr(args, "project", None)
    priority = getattr(args, "priority", 1)
    due = getattr(args, "due", None)

    response_data = create_todoist_task(
        account,
        mailbox,
        acct_escaped,
        mb_escaped,
        message_id,
        project=project,
        priority=priority,
        due=due,
    )

    subject = response_data.get("content", "")
    task_url = response_data.get("url")

    text = f"Created Todoist task: {subject}"
    if task_url:
        text += f"\nURL: {task_url}"

    format_output(args, text, json_data=response_data)


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
