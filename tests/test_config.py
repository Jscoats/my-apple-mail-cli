"""Tests for config module."""

import json
import os

import pytest

from mxctl.config import resolve_account, validate_limit


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
        monkeypatch.setattr("mxctl.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr("mxctl.config.CONFIG_FILE", str(config_dir / "config.json"))
        monkeypatch.setattr("mxctl.config.STATE_FILE", str(config_dir / "state.json"))

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
        monkeypatch.setattr("mxctl.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr("mxctl.config.CONFIG_FILE", str(config_dir / "config.json"))
        monkeypatch.setattr("mxctl.config.STATE_FILE", str(config_dir / "state.json"))

        # Set config default (namespaced under "mail")
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({"mail": {"default_account": "ConfigDefault"}}))

        result = resolve_account(None)
        assert result == "ConfigDefault"

    def test_state_fallback(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("mxctl.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr("mxctl.config.CONFIG_FILE", str(config_dir / "config.json"))
        monkeypatch.setattr("mxctl.config.STATE_FILE", str(config_dir / "state.json"))

        # Set state last-used (namespaced under "mail")
        state_file = config_dir / "state.json"
        state_file.write_text(json.dumps({"mail": {"last_account": "StateAccount"}}))

        result = resolve_account(None)
        assert result == "StateAccount"

    def test_none_when_nothing_set(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("mxctl.config.CONFIG_DIR", str(config_dir))
        monkeypatch.setattr("mxctl.config.CONFIG_FILE", str(config_dir / "config.json"))
        monkeypatch.setattr("mxctl.config.STATE_FILE", str(config_dir / "state.json"))

        result = resolve_account(None)
        assert result is None


# ===========================================================================
# _migrate_legacy_config
# ===========================================================================


class TestMigrateLegacyConfig:
    """Test legacy config migration from ~/.config/my/ to ~/.config/mxctl/."""

    def test_migration_copies_tree(self, tmp_path, monkeypatch):
        """Legacy dir exists, new dir does not — copytree migrates."""
        import mxctl.config as cfg_mod

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "config.json").write_text('{"old": true}')

        new_dir = tmp_path / "new"
        # new_dir does NOT exist yet

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(new_dir))
        monkeypatch.setattr(cfg_mod, "_LEGACY_CONFIG_DIR", str(legacy_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", False)

        cfg_mod._migrate_legacy_config()

        assert os.path.isdir(str(new_dir))
        assert (new_dir / "config.json").read_text() == '{"old": true}'

    def test_migration_skips_if_new_dir_exists(self, tmp_path, monkeypatch):
        """If CONFIG_DIR already exists, migration is skipped."""
        import mxctl.config as cfg_mod

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "config.json").write_text('{"old": true}')

        new_dir = tmp_path / "new"
        new_dir.mkdir()

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(new_dir))
        monkeypatch.setattr(cfg_mod, "_LEGACY_CONFIG_DIR", str(legacy_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", False)

        cfg_mod._migrate_legacy_config()

        # config.json should NOT have been copied (new dir already existed)
        assert not (new_dir / "config.json").exists()

    def test_migration_skips_if_no_legacy(self, tmp_path, monkeypatch):
        """No legacy dir and no new dir — migration does nothing."""
        import mxctl.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path / "new"))
        monkeypatch.setattr(cfg_mod, "_LEGACY_CONFIG_DIR", str(tmp_path / "nonexistent"))
        monkeypatch.setattr(cfg_mod, "_migrated", False)

        cfg_mod._migrate_legacy_config()

        assert not os.path.isdir(str(tmp_path / "new"))

    def test_migration_only_runs_once(self, tmp_path, monkeypatch):
        """Second call to _migrate_legacy_config() is a no-op."""
        import mxctl.config as cfg_mod

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "config.json").write_text('{"old": true}')

        new_dir = tmp_path / "new"

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(new_dir))
        monkeypatch.setattr(cfg_mod, "_LEGACY_CONFIG_DIR", str(legacy_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", False)

        cfg_mod._migrate_legacy_config()
        assert os.path.isdir(str(new_dir))

        # Remove the new dir so we can tell if second call runs
        import shutil

        shutil.rmtree(str(new_dir))

        cfg_mod._migrate_legacy_config()
        # Should NOT have re-created new_dir because _migrated is True
        assert not os.path.isdir(str(new_dir))


# ===========================================================================
# file_lock retry and timeout
# ===========================================================================


class TestFileLock:
    """Test file_lock retry/timeout paths."""

    def test_file_lock_success(self, tmp_path):
        """Normal lock acquire/release cycle."""
        from mxctl.config import file_lock

        lock_target = str(tmp_path / "test.json")
        with file_lock(lock_target) as lf:
            assert lf is not None

    def test_file_lock_retry_then_succeed(self, tmp_path, monkeypatch):
        """Lock fails first attempt then succeeds — exercises retry."""
        import fcntl

        from mxctl.config import file_lock

        lock_target = str(tmp_path / "test.json")
        original_flock = fcntl.flock
        call_count = 0

        def patched_flock(fd, operation):
            nonlocal call_count
            # Only intercept LOCK_EX|LOCK_NB (acquire), not LOCK_UN (release)
            if operation == (fcntl.LOCK_EX | fcntl.LOCK_NB):
                call_count += 1
                if call_count == 1:
                    raise BlockingIOError("locked")
            return original_flock(fd, operation)

        monkeypatch.setattr("fcntl.flock", patched_flock)
        monkeypatch.setattr("mxctl.config.time.sleep", lambda _: None)

        with file_lock(lock_target) as lf:
            assert lf is not None
        assert call_count >= 2

    def test_file_lock_unlink_oserror_ignored(self, tmp_path, monkeypatch):
        """OSError during lock file unlink is silently ignored."""
        from mxctl.config import file_lock

        lock_target = str(tmp_path / "test.json")
        original_unlink = os.unlink

        def fail_unlink(path):
            if path.endswith(".lock"):
                raise OSError("permission denied")
            return original_unlink(path)

        monkeypatch.setattr("os.unlink", fail_unlink)

        # Should not raise despite unlink failure
        with file_lock(lock_target) as lf:
            assert lf is not None

    def test_file_lock_all_retries_fail(self, tmp_path, monkeypatch):
        """All retries fail — die() is called."""
        import fcntl

        from mxctl.config import file_lock

        lock_target = str(tmp_path / "test.json")

        def always_fail(fd, operation):
            if operation == (fcntl.LOCK_EX | fcntl.LOCK_NB):
                raise BlockingIOError("locked")

        monkeypatch.setattr("fcntl.flock", always_fail)
        monkeypatch.setattr("mxctl.config.time.sleep", lambda _: None)

        with pytest.raises(SystemExit) as exc_info, file_lock(lock_target):
            pass
        assert exc_info.value.code == 1


# ===========================================================================
# _load_json IOError and edge cases
# ===========================================================================


class TestLoadJson:
    """Test _load_json error handling."""

    def test_load_json_ioerror(self, tmp_path, monkeypatch):
        """IOError during file read returns empty dict."""
        import mxctl.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text('{"valid": true}')

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", True)

        # Make the open inside _load_json raise OSError after file_lock succeeds
        original_open = open

        def failing_open(path, *args, **kwargs):
            if str(path) == str(config_file) and not args and not kwargs:
                # This is the second open (for reading), not the lock file open
                raise OSError("disk error")
            return original_open(path, *args, **kwargs)

        # Easier: just mock file_lock to yield, then open to fail
        from contextlib import contextmanager

        @contextmanager
        def fake_lock(path):
            yield None

        monkeypatch.setattr(cfg_mod, "file_lock", fake_lock)

        real_open = open

        def fail_on_read(path, *a, **kw):
            if str(path) == str(config_file):
                raise OSError("disk error")
            return real_open(path, *a, **kw)

        monkeypatch.setattr("builtins.open", fail_on_read)

        result = cfg_mod._load_json(str(config_file))
        assert result == {}

    def test_load_json_invalid_json(self, tmp_path, monkeypatch, capsys):
        """Invalid JSON returns empty dict and prints warning."""
        import mxctl.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text("not valid json {{{")

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", True)

        result = cfg_mod._load_json(str(config_file))
        assert result == {}

        captured = capsys.readouterr()
        assert "invalid JSON" in captured.err

    def test_load_json_empty_file(self, tmp_path, monkeypatch):
        """Empty file returns empty dict."""
        import mxctl.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.json"
        config_file.write_text("")

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", True)

        result = cfg_mod._load_json(str(config_file))
        assert result == {}

    def test_load_json_nonexistent_file(self, tmp_path, monkeypatch):
        """Nonexistent file returns empty dict."""
        import mxctl.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_migrated", True)
        result = cfg_mod._load_json(str(tmp_path / "nope.json"))
        assert result == {}


# ===========================================================================
# get_config: migration trigger, required=True, warn paths
# ===========================================================================


class TestGetConfig:
    """Test get_config edge cases."""

    def test_get_config_required_no_file(self, tmp_path, monkeypatch):
        """required=True with no config file calls die()."""
        import mxctl.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(tmp_path / "config.json"))
        monkeypatch.setattr(cfg_mod, "_migrated", True)

        with pytest.raises(SystemExit) as exc_info:
            cfg_mod.get_config(required=True)
        assert exc_info.value.code == 1

    def test_get_config_warn_once(self, tmp_path, monkeypatch, capsys):
        """First call warns, second does not (warn-once behavior)."""
        import mxctl.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(tmp_path / "config.json"))
        monkeypatch.setattr(cfg_mod, "_migrated", True)
        monkeypatch.setattr(cfg_mod, "_config_warned", False)

        cfg_mod.get_config(required=False, warn=True)
        captured = capsys.readouterr()
        assert "No config found" in captured.err

        cfg_mod.get_config(required=False, warn=True)
        captured2 = capsys.readouterr()
        assert captured2.err == ""

    def test_get_config_warn_false(self, tmp_path, monkeypatch, capsys):
        """warn=False suppresses the warning."""
        import mxctl.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(tmp_path / "config.json"))
        monkeypatch.setattr(cfg_mod, "_migrated", True)
        monkeypatch.setattr(cfg_mod, "_config_warned", False)

        cfg_mod.get_config(required=False, warn=False)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_get_config_triggers_migration(self, tmp_path, monkeypatch):
        """get_config calls _migrate_legacy_config when no config file."""
        import mxctl.config as cfg_mod

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        legacy_config = legacy_dir / "config.json"
        legacy_config.write_text('{"migrated_key": true}')

        new_dir = tmp_path / "new"

        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(new_dir))
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(new_dir / "config.json"))
        monkeypatch.setattr(cfg_mod, "_LEGACY_CONFIG_DIR", str(legacy_dir))
        monkeypatch.setattr(cfg_mod, "_migrated", False)
        monkeypatch.setattr(cfg_mod, "_config_warned", False)

        result = cfg_mod.get_config(required=False, warn=False)
        assert result.get("migrated_key") is True


# ===========================================================================
# save_message_aliases + resolve_alias
# ===========================================================================


class TestMessageAliases:
    """Test save_message_aliases and resolve_alias."""

    def test_save_and_resolve_aliases(self, tmp_path, monkeypatch):
        """Save aliases then resolve them by number."""
        import mxctl.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(config_dir / "config.json"))
        monkeypatch.setattr(cfg_mod, "STATE_FILE", str(config_dir / "state.json"))
        monkeypatch.setattr(cfg_mod, "_migrated", True)

        cfg_mod.save_message_aliases([100, 200, 300])

        assert cfg_mod.resolve_alias(1) == 100
        assert cfg_mod.resolve_alias(2) == 200
        assert cfg_mod.resolve_alias(3) == 300

    def test_resolve_alias_not_found(self, tmp_path, monkeypatch):
        """Alias number not in state returns None."""
        import mxctl.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(config_dir))
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(config_dir / "config.json"))
        monkeypatch.setattr(cfg_mod, "STATE_FILE", str(config_dir / "state.json"))
        monkeypatch.setattr(cfg_mod, "_migrated", True)

        assert cfg_mod.resolve_alias(999) is None

    def test_resolve_alias_non_numeric(self):
        """Non-numeric value returns None."""
        from mxctl.config import resolve_alias

        assert resolve_alias("abc") is None
        assert resolve_alias(None) is None

    def test_resolve_alias_zero_or_negative(self):
        """Zero or negative returns None."""
        from mxctl.config import resolve_alias

        assert resolve_alias(0) is None
        assert resolve_alias(-1) is None
