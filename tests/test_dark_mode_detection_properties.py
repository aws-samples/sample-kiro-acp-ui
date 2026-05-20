"""Property-based tests for dark mode detection.

**Property 1: Dark mode detection returns boolean based on subprocess output**

For any output string from the `defaults read -g AppleInterfaceStyle` command,
`detect_dark_mode()` SHALL return `True` if and only if the stripped output
equals exactly `"Dark"`, and `False` for all other outputs including empty
strings, error outputs, and timeout conditions.

**Validates: Requirements 1.1, 1.4**
"""

import subprocess
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.theme import detect_dark_mode

# Strategy for arbitrary strings that are NOT "Dark" when stripped
non_dark_strings = st.text().filter(lambda s: s.strip() != "Dark")

# Strategy for strings that ARE "Dark" with optional surrounding whitespace
dark_strings = st.builds(
    lambda prefix, suffix: prefix + "Dark" + suffix,
    st.from_regex(r"^[\t\n\r ]*$", fullmatch=True),
    st.from_regex(r"^[\t\n\r ]*$", fullmatch=True),
)


# **Validates: Requirements 1.1, 1.4**
@settings(max_examples=200, deadline=None)
@given(output=dark_strings)
def test_detect_dark_mode_returns_true_for_dark_output(output):
    """Property 1: detect_dark_mode() returns True when stripped output == "Dark".

    For any string whose stripped value equals exactly "Dark",
    detect_dark_mode() SHALL return True on macOS.

    **Validates: Requirements 1.1, 1.4**
    """
    mock_result = MagicMock()
    mock_result.stdout = output

    with (
        patch("kiro_acp_chat_client.theme.sys.platform", "darwin"),
        patch("kiro_acp_chat_client.theme.subprocess.run", return_value=mock_result),
    ):
        result = detect_dark_mode()

    assert result is True, (
        f"Expected True for output {output!r} (stripped: {output.strip()!r}), got {result}"
    )


# **Validates: Requirements 1.1, 1.4**
@settings(max_examples=200, deadline=None)
@given(output=non_dark_strings)
def test_detect_dark_mode_returns_false_for_non_dark_output(output):
    """Property 1: detect_dark_mode() returns False for all non-"Dark" outputs.

    For any string whose stripped value does NOT equal "Dark" (including empty
    strings, "dark", "DARK", "Light", random strings), detect_dark_mode()
    SHALL return False on macOS.

    **Validates: Requirements 1.1, 1.4**
    """
    mock_result = MagicMock()
    mock_result.stdout = output

    with (
        patch("kiro_acp_chat_client.theme.sys.platform", "darwin"),
        patch("kiro_acp_chat_client.theme.subprocess.run", return_value=mock_result),
    ):
        result = detect_dark_mode()

    assert result is False, (
        f"Expected False for output {output!r} (stripped: {output.strip()!r}), got {result}"
    )


# **Validates: Requirements 1.1, 1.4**
@settings(max_examples=50, deadline=None)
@given(output=st.text())
def test_detect_dark_mode_returns_false_on_timeout(output):
    """Property 1: detect_dark_mode() returns False on subprocess timeout.

    For any scenario where the subprocess times out, detect_dark_mode()
    SHALL return False.

    **Validates: Requirements 1.1, 1.4**
    """
    with (
        patch("kiro_acp_chat_client.theme.sys.platform", "darwin"),
        patch(
            "kiro_acp_chat_client.theme.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="defaults", timeout=2),
        ),
    ):
        result = detect_dark_mode()

    assert result is False, f"Expected False on TimeoutExpired, got {result}"


# **Validates: Requirements 1.1, 1.4**
@settings(max_examples=50, deadline=None)
@given(output=st.text())
def test_detect_dark_mode_returns_false_on_oserror(output):
    """Property 1: detect_dark_mode() returns False on OSError.

    For any scenario where the subprocess raises OSError, detect_dark_mode()
    SHALL return False.

    **Validates: Requirements 1.1, 1.4**
    """
    with (
        patch("kiro_acp_chat_client.theme.sys.platform", "darwin"),
        patch(
            "kiro_acp_chat_client.theme.subprocess.run",
            side_effect=OSError("Command not found"),
        ),
    ):
        result = detect_dark_mode()

    assert result is False, f"Expected False on OSError, got {result}"


# **Validates: Requirements 1.1, 1.4**
@settings(max_examples=50, deadline=None)
@given(platform=st.sampled_from(["linux", "win32", "cygwin", "freebsd"]))
def test_detect_dark_mode_returns_false_on_non_macos(platform):
    """Property 1: detect_dark_mode() returns False on non-macOS platforms.

    For any non-macOS platform, detect_dark_mode() SHALL return False
    without attempting subprocess execution.

    **Validates: Requirements 1.1, 1.4**
    """
    with (
        patch("kiro_acp_chat_client.theme.sys.platform", platform),
        patch("kiro_acp_chat_client.theme.subprocess.run") as mock_run,
    ):
        result = detect_dark_mode()

    assert result is False, f"Expected False on platform {platform!r}, got {result}"
    mock_run.assert_not_called()
