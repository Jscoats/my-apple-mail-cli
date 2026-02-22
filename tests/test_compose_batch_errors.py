"""Tests for compose.py error paths and batch.py dry-run edge cases."""

import json
from argparse import Namespace
from unittest.mock import Mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**kwargs):
    defaults = {"json": False, "account": "iCloud", "mailbox": "INBOX"}
    defaults.update(kwargs)
    return Namespace(**defaults)


# ---------------------------------------------------------------------------
# compose.py: cmd_draft error paths
# ---------------------------------------------------------------------------

class TestDraftErrors:
    def test_draft_no_account_dies(self, monkeypatch):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: None)

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(account=None, to="x@y.com", subject="S", body="B",
                                 template=None, cc=None, bcc=None))

    def test_draft_no_subject_no_template_dies(self, monkeypatch):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body="hello",
                                 template=None, cc=None, bcc=None))

    def test_draft_no_body_no_template_dies(self, monkeypatch):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject="hello", body=None,
                                 template=None, cc=None, bcc=None))

    def test_draft_template_not_found_dies(self, monkeypatch, tmp_path):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        # Create a valid templates file without the requested template
        tpl_file = str(tmp_path / "templates.json")
        with open(tpl_file, "w") as f:
            json.dump({"other": {"subject": "S", "body": "B"}}, f)

        monkeypatch.setattr("my_cli.commands.mail.compose.TEMPLATES_FILE", tpl_file)

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body=None,
                                 template="missing", cc=None, bcc=None))

    def test_draft_corrupt_template_file_dies(self, monkeypatch, tmp_path):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")

        tpl_file = str(tmp_path / "templates.json")
        with open(tpl_file, "w") as f:
            f.write("{corrupt json")

        monkeypatch.setattr("my_cli.commands.mail.compose.TEMPLATES_FILE", tpl_file)

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body=None,
                                 template="any", cc=None, bcc=None))

    def test_draft_no_templates_file_dies(self, monkeypatch, tmp_path):
        from my_cli.commands.mail.compose import cmd_draft

        monkeypatch.setattr("my_cli.commands.mail.compose.resolve_account", lambda _: "iCloud")
        monkeypatch.setattr("my_cli.commands.mail.compose.TEMPLATES_FILE",
                            str(tmp_path / "nonexistent.json"))

        with pytest.raises(SystemExit):
            cmd_draft(_make_args(to="x@y.com", subject=None, body=None,
                                 template="any", cc=None, bcc=None))


# ---------------------------------------------------------------------------
# batch.py: dry-run effective_count edge cases
# ---------------------------------------------------------------------------

class TestBatchMoveEffectiveCount:
    def test_dry_run_with_limit_caps_count(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="50")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="test@x.com", to_mailbox="Archive",
                          dry_run=True, limit=10)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "10" in out  # effective_count = min(50, 10) = 10

    def test_dry_run_without_limit_uses_total(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_move

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="25")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="test@x.com", to_mailbox="Archive",
                          dry_run=True, limit=None)
        cmd_batch_move(args)

        out = capsys.readouterr().out
        assert "25" in out  # effective_count = total = 25


class TestBatchDeleteEffectiveCount:
    def test_dry_run_with_limit_caps_count(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_delete

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="100")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="spam@x.com", older_than=None,
                          dry_run=True, limit=20, force=False)
        cmd_batch_delete(args)

        out = capsys.readouterr().out
        assert "20" in out  # effective_count = min(100, 20) = 20

    def test_dry_run_without_limit_uses_total(self, monkeypatch, capsys):
        from my_cli.commands.mail.batch import cmd_batch_delete

        monkeypatch.setattr("my_cli.commands.mail.batch.resolve_account", lambda _: "iCloud")
        mock_run = Mock(return_value="42")
        monkeypatch.setattr("my_cli.commands.mail.batch.run", mock_run)

        args = _make_args(from_sender="spam@x.com", older_than=None,
                          dry_run=True, limit=None, force=False)
        cmd_batch_delete(args)

        out = capsys.readouterr().out
        assert "42" in out  # effective_count = total = 42
