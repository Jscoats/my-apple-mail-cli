"""Tests for email templates CRUD operations."""

import json
import os
from argparse import Namespace

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**kwargs):
    defaults = {"json": False}
    defaults.update(kwargs)
    return Namespace(**defaults)


# ---------------------------------------------------------------------------
# _load_templates / _save_templates
# ---------------------------------------------------------------------------


class TestLoadSaveTemplates:
    def test_load_empty_when_no_file(self, monkeypatch, tmp_path):
        from mxctl.commands.mail.templates import _load_templates

        missing = str(tmp_path / "nonexistent.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", missing)
        assert _load_templates() == {}

    def test_save_and_load_round_trip(self, monkeypatch, tmp_path):
        from mxctl.commands.mail.templates import _load_templates, _save_templates

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        data = {"greeting": {"subject": "Hello", "body": "Hi there"}}
        _save_templates(data)

        assert os.path.isfile(tpl_file)
        loaded = _load_templates()
        assert loaded == data

    def test_load_corrupt_json_returns_empty(self, monkeypatch, tmp_path):
        from mxctl.commands.mail.templates import _load_templates

        tpl_file = str(tmp_path / "templates.json")
        with open(tpl_file, "w") as f:
            f.write("{not valid json")

        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        assert _load_templates() == {}


# ---------------------------------------------------------------------------
# cmd_templates_list
# ---------------------------------------------------------------------------


class TestTemplatesList:
    def test_list_empty(self, monkeypatch, capsys, tmp_path):
        from mxctl.commands.mail.templates import cmd_templates_list

        missing = str(tmp_path / "nonexistent.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", missing)

        cmd_templates_list(_make_args())
        out = capsys.readouterr().out
        assert "No templates saved" in out

    def test_list_with_templates(self, monkeypatch, capsys, tmp_path):
        from mxctl.commands.mail.templates import _save_templates, cmd_templates_list

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        _save_templates({"follow-up": {"subject": "Following up", "body": "Just checking in."}})

        cmd_templates_list(_make_args())
        out = capsys.readouterr().out
        assert "follow-up" in out
        assert "Following up" in out

    def test_list_json_output(self, monkeypatch, capsys, tmp_path):
        from mxctl.commands.mail.templates import _save_templates, cmd_templates_list

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        _save_templates({"test": {"subject": "S", "body": "B"}})

        cmd_templates_list(_make_args(json=True))
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "test"


# ---------------------------------------------------------------------------
# cmd_templates_create
# ---------------------------------------------------------------------------


class TestTemplatesCreate:
    def test_create_with_flags(self, monkeypatch, capsys, tmp_path):
        from mxctl.commands.mail.templates import _load_templates, cmd_templates_create

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        args = _make_args(name="reply", subject="Re: {original_subject}", body="Thanks!")
        cmd_templates_create(args)

        out = capsys.readouterr().out
        assert "reply" in out
        assert "saved" in out.lower()

        loaded = _load_templates()
        assert "reply" in loaded
        assert loaded["reply"]["subject"] == "Re: {original_subject}"


# ---------------------------------------------------------------------------
# cmd_templates_show
# ---------------------------------------------------------------------------


class TestTemplatesShow:
    def test_show_existing(self, monkeypatch, capsys, tmp_path):
        from mxctl.commands.mail.templates import _save_templates, cmd_templates_show

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        _save_templates({"greet": {"subject": "Hello", "body": "World"}})

        cmd_templates_show(_make_args(name="greet"))
        out = capsys.readouterr().out
        assert "Hello" in out
        assert "World" in out

    def test_show_nonexistent_dies(self, monkeypatch, tmp_path):
        from mxctl.commands.mail.templates import _save_templates, cmd_templates_show

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        _save_templates({})

        with pytest.raises(SystemExit):
            cmd_templates_show(_make_args(name="nope"))


# ---------------------------------------------------------------------------
# cmd_templates_delete
# ---------------------------------------------------------------------------


class TestTemplatesDelete:
    def test_delete_existing(self, monkeypatch, capsys, tmp_path):
        from mxctl.commands.mail.templates import _load_templates, _save_templates, cmd_templates_delete

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        _save_templates({"old": {"subject": "S", "body": "B"}})

        cmd_templates_delete(_make_args(name="old"))
        out = capsys.readouterr().out
        assert "deleted" in out.lower()

        loaded = _load_templates()
        assert "old" not in loaded

    def test_delete_nonexistent_dies(self, monkeypatch, tmp_path):
        from mxctl.commands.mail.templates import _save_templates, cmd_templates_delete

        tpl_file = str(tmp_path / "templates.json")
        monkeypatch.setattr("mxctl.commands.mail.templates.TEMPLATES_FILE", tpl_file)
        monkeypatch.setattr("mxctl.commands.mail.templates.CONFIG_DIR", str(tmp_path))

        _save_templates({})

        with pytest.raises(SystemExit):
            cmd_templates_delete(_make_args(name="nope"))
