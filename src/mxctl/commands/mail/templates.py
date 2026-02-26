"""Email templates management."""

import json
import os

from mxctl.config import CONFIG_DIR, TEMPLATES_FILE, file_lock
from mxctl.util.formatting import die, format_output


def _load_templates() -> dict:
    """Load templates from disk."""
    if os.path.isfile(TEMPLATES_FILE):
        with file_lock(TEMPLATES_FILE), open(TEMPLATES_FILE) as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def _save_templates(templates: dict) -> None:
    """Save templates to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with file_lock(TEMPLATES_FILE), open(TEMPLATES_FILE, "w") as f:
        json.dump(templates, f, indent=2)
    os.chmod(TEMPLATES_FILE, 0o600)


def get_templates() -> list[dict]:
    """Return all saved templates as a list of dicts."""
    templates = _load_templates()
    return [{"name": name, "subject": data.get("subject", ""), "body": data.get("body", "")} for name, data in templates.items()]


def get_template(name: str) -> dict:
    """Return a single template by name. Raises SystemExit if not found."""
    templates = _load_templates()
    if name not in templates:
        die(f"Template '{name}' not found. Use 'mxctl templates list' to see available templates.")
    template = templates[name]
    return {"name": name, "subject": template.get("subject", ""), "body": template.get("body", "")}


def create_template(name: str, subject: str, body: str) -> dict:
    """Create or update a template. Returns the saved template dict."""
    templates = _load_templates()
    templates[name] = {"subject": subject, "body": body}
    _save_templates(templates)
    return {"name": name, "subject": subject, "body": body}


def delete_template(name: str) -> dict:
    """Delete a template by name. Returns confirmation dict."""
    templates = _load_templates()
    if name not in templates:
        die(f"Template '{name}' not found.")
    del templates[name]
    _save_templates(templates)
    return {"name": name, "deleted": True}


def cmd_templates_list(args) -> None:
    """List all saved templates."""
    templates = _load_templates()

    if not templates:
        format_output(args, "No templates saved.")
        return

    template_list = get_templates()

    # Build text output
    text = "Email Templates:"
    for name, data in templates.items():
        subject = data.get("subject", "")
        body = data.get("body", "")
        text += f"\n\n{name}:"
        text += f"\n  Subject: {subject}"
        text += f"\n  Body: {body[:80]}{'...' if len(body) > 80 else ''}"

    format_output(args, text, json_data=template_list)


def cmd_templates_create(args) -> None:
    """Create or update a template."""
    name = args.name

    # Check if interactive or flag-based
    if args.subject is None or args.body is None:
        # Interactive mode
        print(f"Creating template '{name}'")
        print("Enter subject (use {{original_subject}} as placeholder):")
        subject = input("> ").strip()
        print("Enter body:")
        body = input("> ").strip()
    else:
        subject = args.subject
        body = args.body

    data = create_template(name, subject, body)
    text = f"Template '{name}' saved successfully!\n\nSubject: {subject}\nBody: {body}"
    format_output(args, text, json_data=data)


def cmd_templates_show(args) -> None:
    """Show a specific template."""
    name = args.name
    data = get_template(name)
    subject = data["subject"]
    body = data["body"]
    text = f"Template: {name}\n\nSubject: {subject}\n\nBody:\n{body}"
    format_output(args, text, json_data=data)


def cmd_templates_delete(args) -> None:
    """Delete a template."""
    name = args.name
    data = delete_template(name)
    text = f"Template '{name}' deleted successfully."
    format_output(args, text, json_data=data)


def register(subparsers) -> None:
    """Register email templates subcommands."""
    # Create templates subcommand group
    templates_parser = subparsers.add_parser("templates", help="Manage email templates")
    templates_sub = templates_parser.add_subparsers(dest="templates_command")

    # list
    p = templates_sub.add_parser("list", help="List all saved templates")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_templates_list)

    # create
    p = templates_sub.add_parser("create", help="Create or update a template")
    p.add_argument("name", help="Template name")
    p.add_argument("--subject", help="Template subject (use {original_subject} as placeholder)")
    p.add_argument("--body", help="Template body")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_templates_create)

    # show
    p = templates_sub.add_parser("show", help="Show a specific template")
    p.add_argument("name", help="Template name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_templates_show)

    # delete
    p = templates_sub.add_parser("delete", help="Delete a template")
    p.add_argument("name", help="Template name")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_templates_delete)

    # If `mxctl templates` is run with no subcommand, show help
    templates_parser.set_defaults(func=lambda _: templates_parser.print_help())
