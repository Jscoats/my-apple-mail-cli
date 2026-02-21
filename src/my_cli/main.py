"""Top-level argparse router for the `my` CLI."""

import argparse
import sys

from my_cli.commands.mail import register_mail_subcommand


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="my",
        description="Personal CLI toolkit",
    )
    subparsers = parser.add_subparsers(dest="command")

    register_mail_subcommand(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch to the handler set by set_defaults(func=...)
    try:
        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.parse_args([args.command, "--help"])
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
