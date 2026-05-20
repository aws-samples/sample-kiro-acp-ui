"""Property-based tests for message length validation.

# Feature: github-issues-backlog, Property 5: Messages exceeding length limit
# are rejected with formatted error
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.controller import ChatController


def _create_controller():
    """Create a ChatController with mocked dependencies."""
    ui = MagicMock()
    ui.append_user_message = MagicMock()
    ui.append_assistant_message = MagicMock()
    ui.append_error = MagicMock()
    ui.show_typing_indicator = MagicMock()
    ui.hide_typing_indicator = MagicMock()
    ui.clear_input = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.get_input_text = MagicMock(return_value="")

    acp_client = AsyncMock()
    acp_client.initialize = AsyncMock(return_value={"result": {}})
    acp_client.create_session = AsyncMock(return_value="session-123")
    acp_client.send_prompt = AsyncMock()
    acp_client.read_update = AsyncMock()

    process_manager = AsyncMock()
    process_manager.shutdown = AsyncMock()
    process_manager.is_running = True

    preferences_manager = MagicMock()
    preferences_manager.load = MagicMock()
    preferences_manager.save = MagicMock()

    controller = ChatController(ui, acp_client, process_manager, preferences_manager)
    controller._conversation.session_id = "session-123"
    return controller, ui, acp_client, process_manager


# Strategy for generating strings that exceed the 2000 character limit.
# We generate text of length 2001 to 5000 to cover various oversized inputs.
oversized_message_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=2001,
    max_size=5000,
)


# **Validates: Requirements 6.1, 6.2, 6.3**
@settings(max_examples=100, deadline=None)
@given(message_text=oversized_message_strings)
@pytest.mark.asyncio
async def test_oversized_message_displays_error_with_length_and_limit(message_text):
    """Property 5: Messages exceeding length limit are rejected with formatted error.

    For any input string with length L > 2000, the controller SHALL:
    (a) display an error message containing the exact count L and the limit 2000,
    (b) not clear the input field, and
    (c) not invoke send_prompt on the ACP client.

    # Feature: github-issues-backlog, Property 5: Messages exceeding length
    # limit are rejected with formatted error

    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    controller, ui, acp_client, _ = _create_controller()

    await controller.send_message(message_text)

    # (a) append_error is called with a message containing the exact length and the limit 2000
    ui.append_error.assert_called_once()
    error_msg = ui.append_error.call_args[0][0]
    actual_length = len(message_text)
    assert str(actual_length) in error_msg, (
        f"Error message should contain the actual length {actual_length}, but got: '{error_msg}'"
    )
    assert "2000" in error_msg, (
        f"Error message should contain the limit '2000', but got: '{error_msg}'"
    )

    # (b) clear_input is NOT called (input field is retained)
    ui.clear_input.assert_not_called()

    # (c) send_prompt is NOT called on the ACP client
    acp_client.send_prompt.assert_not_called()
