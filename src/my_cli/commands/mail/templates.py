"""Email templates management."""

import json
import os

from my_cli.config import CONFIG_DIR, TEMPLATES_FILE, file_lock
from my_cli.util.formatting import format_output, die


def _load_templates() -> dict:
    """Load templates from disk."""
    if os.path.isfile(TEMPLATES_FILE):
        with file_lock(TEMPLATES_FILE):
            with open(TEMPLATES_FILE) as f:
                try:
                    return json.load(f)
                except (json.JSONDecodeError, OSError):
                    return {}
    return {}


def _save_templates(templates: dict) -> None:
    """Save templates to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with file_lock(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, "w") as f:
            json.dump(templates, f, indent=2)


def cmd_templates_list(args) -> None:
    """List all saved templates."""
    templates = _load_templates()

    if not templates:
        format_output(args, "No templates saved.")
        return

    # Build JSON data
    template_list = [
        {"name": name, "subject": data.get("subject", ""), "body": data.get("body", "")}
        for name, data in templates.items()
    ]

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
    templates = _load_templates()

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

    templates[name] = {"subject": subject, "body": body}
    _save_templates(templates)

    data = {"name": name, "subject": subject, "body": body}
    text = f"Template '{name}' saved successfully!\n\nSubject: {subject}\nBody: {body}"
    format_output(args, text, json_data=data)


def cmd_templates_show(args) -> None:
    """Show a specific template."""
    name = args.name
    templates = _load_templates()

    if name not in templates:
        die(f"Template '{name}' not found. Use 'my mail templates list' to see available templates.")

    template = templates[name]
    subject = template.get("subject", "")
    body = template.get("body", "")

    data = {"name": name, "subject": subject, "body": body}
    text = f"Template: {name}\n\nSubject: {subject}\n\nBody:\n{body}"
    format_output(args, text, json_data=data)


def cmd_templates_delete(args) -> None:
    """Delete a template."""
    name = args.name
    templates = _load_templates()

    if name not in templates:
        die(f"Template '{name}' not found.")

    del templates[name]
    _save_templates(templates)

    data = {"name": name, "deleted": True}
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

    # If `my mail templates` is run with no subcommand, show help
    templates_parser.set_defaults(func=lambda _: templates_parser.print_help())
