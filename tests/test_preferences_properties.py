"""Property-based tests for PreferencesManager.

# Feature: model-agent-preferences, Property 7: Malformed preferences file produces defaults
"""

import json
import os
import tempfile

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.preferences_manager import Preferences, PreferencesManager

# Strategy for generating arbitrary text that is NOT valid JSON dicts
arbitrary_text = st.text(min_size=0, max_size=200)

# Strategy for generating valid JSON values that are NOT dicts
# (lists, numbers, strings, booleans, null)
non_dict_json_values = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=50),
    st.lists(st.one_of(st.integers(), st.text(max_size=20), st.booleans(), st.none()), max_size=10),
)


# **Validates: Requirements 3.7**
@settings(max_examples=100)
@given(content=arbitrary_text)
def test_malformed_non_json_produces_defaults(content):
    """Property 7: Malformed preferences file produces defaults (non-JSON variant).

    For any string that is not a valid JSON dict, loading preferences
    SHALL return the default Preferences (model_id="auto", mode_id="")
    without raising an exception.

    # Feature: model-agent-preferences, Property 7: Malformed preferences file produces defaults
    """
    # Filter out strings that happen to be valid JSON dicts
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            assume(False)
    except (json.JSONDecodeError, ValueError):
        pass  # Not valid JSON at all — good, keep this input

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(content)
        file_path = f.name

    try:
        manager = PreferencesManager(file_path)
        prefs = manager.load()

        assert isinstance(prefs, Preferences)
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""
    finally:
        os.unlink(file_path)


# **Validates: Requirements 3.7**
@settings(max_examples=100)
@given(value=non_dict_json_values)
def test_valid_json_non_dict_produces_defaults(value):
    """Property 7: Malformed preferences file produces defaults (valid JSON non-dict variant).

    For any valid JSON value that is NOT a dict (e.g., lists, numbers,
    strings, booleans, null), loading preferences SHALL return the default
    Preferences (model_id="auto", mode_id="") without raising an exception.

    # Feature: model-agent-preferences, Property 7: Malformed preferences file produces defaults
    """
    # Ensure the value is not a dict
    assume(not isinstance(value, dict))

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(value))
        file_path = f.name

    try:
        manager = PreferencesManager(file_path)
        prefs = manager.load()

        assert isinstance(prefs, Preferences)
        assert prefs.model_id == "auto"
        assert prefs.mode_id == ""
    finally:
        os.unlink(file_path)
