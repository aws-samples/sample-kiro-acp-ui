"""Property-based tests for preference save completeness.

**Property 4: Preference saves always include log_message_content**

For any model or mode change that triggers a preference save, the saved
Preferences object SHALL contain the current in-memory value of
log_message_content, preserving it unchanged from the value loaded at
startup or last modified.

**Validates: Requirements 5.1, 5.2**
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.controller import ChatController
from kiro_acp_chat_client.preferences_manager import Preferences

# Strategy for generating model/mode ID strings
id_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


def _create_controller_with_log_preference(log_message_content: bool):
    """Create a ChatController with mocked dependencies and a specific log_message_content value."""
    ui = MagicMock()
    ui.append_user_message = MagicMock()
    ui.append_assistant_message = MagicMock()
    ui.append_error = MagicMock()
    ui.show_typing_indicator = MagicMock()
    ui.hide_typing_indicator = MagicMock()
    ui.clear_input = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.set_selectors_enabled = MagicMock()
    ui.set_selected_model = MagicMock()
    ui.set_selected_mode = MagicMock()

    acp_client = AsyncMock()
    acp_client.set_model = AsyncMock(return_value={"result": {}})
    acp_client.set_mode = AsyncMock(return_value={"result": {}})

    process_manager = AsyncMock()

    preferences_manager = MagicMock()
    preferences_manager.load = MagicMock(return_value=Preferences())
    preferences_manager.save = MagicMock()

    controller = ChatController(ui, acp_client, process_manager, preferences_manager)
    controller._conversation.session_id = "test-session"
    controller._log_message_content = log_message_content

    return controller, ui, acp_client, preferences_manager


# **Validates: Requirements 5.1, 5.2**
@settings(max_examples=100, deadline=None)
@given(
    model_id=id_strings,
    current_mode_id=id_strings,
    log_message_content=st.booleans(),
)
@pytest.mark.asyncio
async def test_on_model_changed_saves_log_message_content(
    model_id, current_mode_id, log_message_content
):
    """Property 4: on_model_changed saves log_message_content.

    For any model change that triggers a preference save, the saved Preferences
    object SHALL contain the current in-memory value of log_message_content,
    preserving it unchanged.

    **Validates: Requirements 5.1, 5.2**
    """
    controller, _, _, preferences_manager = _create_controller_with_log_preference(
        log_message_content
    )
    controller._current_mode_id = current_mode_id

    await controller.on_model_changed(model_id)

    # Assert: save was called exactly once
    preferences_manager.save.assert_called_once()

    # Extract the saved Preferences object
    saved_prefs = preferences_manager.save.call_args[0][0]

    # Assert: log_message_content is present and matches the in-memory value
    assert isinstance(saved_prefs, Preferences)
    assert saved_prefs.log_message_content == log_message_content, (
        f"Expected log_message_content={log_message_content} in saved preferences, "
        f"but got {saved_prefs.log_message_content}"
    )
    # Also verify model_id and mode_id are correct
    assert saved_prefs.model_id == model_id
    assert saved_prefs.mode_id == current_mode_id


# **Validates: Requirements 5.1, 5.2**
@settings(max_examples=100, deadline=None)
@given(
    mode_id=id_strings,
    current_model_id=id_strings,
    log_message_content=st.booleans(),
)
@pytest.mark.asyncio
async def test_on_mode_changed_saves_log_message_content(
    mode_id, current_model_id, log_message_content
):
    """Property 4: on_mode_changed saves log_message_content.

    For any mode change that triggers a preference save, the saved Preferences
    object SHALL contain the current in-memory value of log_message_content,
    preserving it unchanged.

    **Validates: Requirements 5.1, 5.2**
    """
    controller, _, _, preferences_manager = _create_controller_with_log_preference(
        log_message_content
    )
    controller._current_model_id = current_model_id

    await controller.on_mode_changed(mode_id)

    # Assert: save was called exactly once
    preferences_manager.save.assert_called_once()

    # Extract the saved Preferences object
    saved_prefs = preferences_manager.save.call_args[0][0]

    # Assert: log_message_content is present and matches the in-memory value
    assert isinstance(saved_prefs, Preferences)
    assert saved_prefs.log_message_content == log_message_content, (
        f"Expected log_message_content={log_message_content} in saved preferences, "
        f"but got {saved_prefs.log_message_content}"
    )
    # Also verify model_id and mode_id are correct
    assert saved_prefs.model_id == current_model_id
    assert saved_prefs.mode_id == mode_id
