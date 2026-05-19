"""Unit tests for PreferencesManager and Preferences."""

import json
import os
import tempfile

import pytest

from kiro_acp_chat_client.preferences_manager import Preferences, PreferencesManager


class TestPreferences:
    """Tests for the Preferences dataclass."""

    def test_defaults(self):
        prefs = Preferences()
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""

    def test_to_dict(self):
        prefs = Preferences(model_id="claude-sonnet", mode_id="Developer")
        assert prefs.to_dict() == {"model_id": "claude-sonnet", "mode_id": "Developer", "log_message_content": False}

    def test_from_dict_valid(self):
        data = {"model_id": "claude-opus", "mode_id": "Kiro Default"}
        prefs = Preferences.from_dict(data)
        assert prefs.model_id == "claude-opus"
        assert prefs.mode_id == "Kiro Default"

    def test_from_dict_missing_keys(self):
        prefs = Preferences.from_dict({})
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""

    def test_from_dict_non_string_model_id(self):
        prefs = Preferences.from_dict({"model_id": 123, "mode_id": "Dev"})
        assert prefs.model_id == "auto"
        assert prefs.mode_id == "Dev"

    def test_from_dict_non_string_mode_id(self):
        prefs = Preferences.from_dict({"model_id": "claude", "mode_id": None})
        assert prefs.model_id == "claude"
        assert prefs.mode_id == ""


class TestPreferencesManager:
    """Tests for the PreferencesManager class."""

    def test_load_missing_file(self, tmp_path):
        manager = PreferencesManager(str(tmp_path / "nonexistent.json"))
        prefs = manager.load()
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""

    def test_load_valid_file(self, tmp_path):
        file_path = tmp_path / "preferences.json"
        file_path.write_text(json.dumps({"model_id": "opus", "mode_id": "Dev"}))
        manager = PreferencesManager(str(file_path))
        prefs = manager.load()
        assert prefs.model_id == "opus"
        assert prefs.mode_id == "Dev"

    def test_load_malformed_json(self, tmp_path):
        file_path = tmp_path / "preferences.json"
        file_path.write_text("not valid json {{{")
        manager = PreferencesManager(str(file_path))
        prefs = manager.load()
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""

    def test_load_valid_json_not_dict(self, tmp_path):
        file_path = tmp_path / "preferences.json"
        file_path.write_text(json.dumps([1, 2, 3]))
        manager = PreferencesManager(str(file_path))
        prefs = manager.load()
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""

    def test_load_valid_json_missing_keys(self, tmp_path):
        file_path = tmp_path / "preferences.json"
        file_path.write_text(json.dumps({"model_id": "sonnet"}))
        manager = PreferencesManager(str(file_path))
        prefs = manager.load()
        assert prefs.model_id == "sonnet"
        assert prefs.mode_id == ""

    def test_save_creates_file(self, tmp_path):
        file_path = tmp_path / "preferences.json"
        manager = PreferencesManager(str(file_path))
        manager.save(Preferences(model_id="opus", mode_id="Developer"))
        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert data == {"model_id": "opus", "mode_id": "Developer", "log_message_content": False}

    def test_save_overwrites_existing(self, tmp_path):
        file_path = tmp_path / "preferences.json"
        file_path.write_text(json.dumps({"model_id": "old", "mode_id": "old"}))
        manager = PreferencesManager(str(file_path))
        manager.save(Preferences(model_id="new", mode_id="new"))
        data = json.loads(file_path.read_text())
        assert data == {"model_id": "new", "mode_id": "new", "log_message_content": False}
