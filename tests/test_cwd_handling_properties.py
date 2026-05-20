"""Property-based tests for --cwd handling.

**Property 7: Valid --cwd path is passed through unchanged to session creation**

For any existing directory path P provided via --cwd, the create_session() call
SHALL receive the resolved absolute path of P as its cwd argument.

**Property 8: Non-existent --cwd path causes immediate exit with error**

For any path string P where the path does not exist as a directory, the
application SHALL exit with a non-zero code and print an error message
containing P to stderr, without launching the GUI or creating an ACP session.

**Validates: Requirements 12.1, 12.3, 12.4**
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.controller import ChatController


def _create_controller(cwd: str | None = None) -> tuple:
    """Create a ChatController with mocked dependencies and optional cwd."""
    ui = MagicMock()
    ui.append_user_message = MagicMock()
    ui.append_assistant_message = MagicMock()
    ui.append_error = MagicMock()
    ui.show_typing_indicator = MagicMock()
    ui.hide_typing_indicator = MagicMock()
    ui.clear_input = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.set_selectors_enabled = MagicMock()
    ui.populate_models = MagicMock()
    ui.populate_modes = MagicMock()
    ui.set_selected_model = MagicMock()
    ui.set_selected_mode = MagicMock()
    ui.set_agent_name = MagicMock()
    ui.show_ready = MagicMock()

    acp_client = AsyncMock()
    acp_client.initialize = AsyncMock(return_value={"result": {}})
    acp_client.create_session = AsyncMock(
        return_value={"sessionId": "session-123", "models": {}, "modes": {}}
    )
    acp_client.send_prompt = AsyncMock()
    acp_client.read_update = AsyncMock()

    process_manager = AsyncMock()
    process_manager.start = AsyncMock()
    process_manager.shutdown = AsyncMock()
    process_manager.is_running = True

    preferences_manager = MagicMock()
    preferences_manager.load = MagicMock(
        return_value=MagicMock(model_id="auto", mode_id="", log_message_content=False)
    )
    preferences_manager.save = MagicMock()

    controller = ChatController(ui, acp_client, process_manager, preferences_manager, cwd=cwd)
    return controller, ui, acp_client, process_manager


# Strategy for generating subdirectory names that are valid on the filesystem.
# We use simple alphanumeric names to avoid OS-specific path issues.
_dir_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "" and s not in (".", ".."))

# Strategy for generating a list of nested subdirectory components
_subdir_path_strategy = st.lists(_dir_name_strategy, min_size=1, max_size=4)


# **Validates: Requirements 12.1, 12.4**
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(subdirs=_subdir_path_strategy)
@pytest.mark.asyncio
async def test_valid_cwd_path_passed_to_create_session(tmp_path: Path, subdirs: list[str]) -> None:
    """Property 7: Valid --cwd path is passed through unchanged to session creation.

    For any existing directory path P provided via --cwd, the create_session()
    call SHALL receive the resolved absolute path of P as its cwd argument.

    # Feature: github-issues-backlog, Property 7: Valid --cwd path is passed
    # through unchanged to session creation

    **Validates: Requirements 12.1, 12.4**
    """
    # Create a nested directory structure under tmp_path
    target_dir = tmp_path
    for subdir in subdirs:
        target_dir = target_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    # Use the path as cwd (could be relative or absolute - we pass the string)
    cwd_str = str(target_dir)

    # Create controller with the cwd
    controller, ui, acp_client, process_manager = _create_controller(cwd=cwd_str)

    # Start the controller which triggers create_session with the cwd
    await controller.start()

    # Verify create_session was called with the resolved absolute path
    acp_client.create_session.assert_called_once()
    actual_cwd = acp_client.create_session.call_args[0][0]

    # The cwd passed to create_session should be the resolved absolute path
    expected_cwd = str(Path(cwd_str).resolve())
    assert actual_cwd == expected_cwd, (
        f"create_session should receive the resolved absolute path.\n"
        f"Expected: {expected_cwd}\n"
        f"Actual:   {actual_cwd}"
    )


# Strategy for generating path strings that are unlikely to exist.
# We use random alphanumeric strings prefixed with a non-existent root.
_nonexistent_path_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=5,
    max_size=30,
).map(lambda s: f"/nonexistent_dir_xyz/{s}")


# **Validates: Requirements 12.3**
@settings(max_examples=50, deadline=None)
@given(bad_path=_nonexistent_path_strategy)
def test_nonexistent_cwd_path_causes_exit_with_error(bad_path: str) -> None:
    """Property 8: Non-existent --cwd path causes immediate exit with error.

    For any path string P where the path does not exist as a directory, the
    application SHALL exit with a non-zero code and print an error message
    containing P to stderr, without launching the GUI or creating an ACP session.

    # Feature: github-issues-backlog, Property 8: Non-existent --cwd path
    # causes immediate exit with error

    **Validates: Requirements 12.3**
    """
    import io

    from kiro_acp_chat_client.__main__ import run_app

    # Ensure the path does not exist
    assert not Path(bad_path).is_dir(), f"Precondition: path should not exist: {bad_path}"

    # Capture stderr and expect SystemExit
    captured_stderr = io.StringIO()

    with patch("sys.stderr", captured_stderr), pytest.raises(SystemExit) as exc_info:
        import asyncio

        asyncio.run(run_app(cwd=bad_path))

    # Verify non-zero exit code
    assert exc_info.value.code != 0, (
        f"Expected non-zero exit code for non-existent path '{bad_path}', "
        f"but got: {exc_info.value.code}"
    )

    # Verify error message contains the bad path
    stderr_output = captured_stderr.getvalue()
    assert bad_path in stderr_output, (
        f"Error message should contain the invalid path '{bad_path}'.\n"
        f"Actual stderr: '{stderr_output}'"
    )
