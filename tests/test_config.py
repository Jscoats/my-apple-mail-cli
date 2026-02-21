"""Tests for config module."""

import json

from my_cli.config import resolve_account, validate_limit


class TestValidateLimit:
    """Test limit validation."""

    def test_normal_value(self):
        assert validate_limit(25) == 25

    def test_zero_clamped_to_one(self):
        assert validate_limit(0) == 1

    def test_negative_clamped_to_one(self):
        assert validate_limit(-5) == 1

    def test_over_max_clamped(self):
        assert validate_limit(999) == 100

    def test_max_value(self):
        assert validate_limit(100) == 100


class TestResolveAccount:
    """Test account resolution."""

    def test_explicit_arg(self, tmp_path, monkeypatch):
        # Mock config dir
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        result = resolve_account("ExplicitAccount")
        assert result == "ExplicitAccount"

        # Verify state was saved (namespaced under "mail")
        state_file = config_dir / "state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["mail"]["last_account"] == "ExplicitAccount"

    def test_config_fallback(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        # Set config default (namespaced under "mail")
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps({"mail": {"default_account": "ConfigDefault"}})
        )

        result = resolve_account(None)
        assert result == "ConfigDefault"

    def test_state_fallback(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        # Set state last-used (namespaced under "mail")
        state_file = config_dir / "state.json"
        state_file.write_text(json.dumps({"mail": {"last_account": "StateAccount"}}))

        result = resolve_account(None)
        assert result == "StateAccount"

    def test_none_when_nothing_set(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("my_cli.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(
            "my_cli.config.CONFIG_FILE", str(config_dir / "config.json")
        )
        monkeypatch.setattr("my_cli.config.STATE_FILE", str(config_dir / "state.json"))

        result = resolve_account(None)
        assert result is None
