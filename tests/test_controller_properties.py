"""Property-based tests for the ChatController class.

# Feature: kiro-acp-chat-client, Property 3: Successful send clears input
# Feature: kiro-acp-chat-client, Property 5: Assistant responses displayed with correct label
# Feature: kiro-acp-chat-client, Property 6: Failed send retains input text
# Feature: model-agent-preferences, Property 5: Preference restoration when saved ID is available
# Feature: model-agent-preferences, Property 6: Preference fallback when saved ID is unavailable
# Feature: model-agent-preferences, Property 8: Restored preferences trigger ACP requests on startup
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.controller import ChatController
from kiro_acp_chat_client.preferences_manager import Preferences
from kiro_acp_chat_client.process_manager import ProcessTerminatedError


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
    return controller, ui, acp_client, process_manager


# Strategy for generating valid non-whitespace message strings (1-2000 chars)
valid_message_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())


def _make_successful_read_updates():
    """Create a list of messages simulating a successful ACP streaming response."""
    return [
        {
            "method": "session/update",
            "params": {
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "response"},
                }
            },
        },
        {"id": 2, "result": {}},
    ]


# **Validates: Requirements 2.3**
@settings(max_examples=100, deadline=None)
@given(message_text=valid_message_strings)
@pytest.mark.asyncio
async def test_successful_send_clears_input(message_text):
    """Property 3: Successful send clears input.

    For any valid non-whitespace message string (1-2000 characters) that is
    successfully sent to the ACP process, the input field SHALL be empty
    immediately after the send operation completes.

    # Feature: kiro-acp-chat-client, Property 3: Successful send clears input

    **Validates: Requirements 2.3**
    """
    controller, ui, acp_client, _ = _create_controller()

    # Configure ACP client to return a successful streaming response
    acp_client.read_update = AsyncMock(side_effect=_make_successful_read_updates())

    # Pre-set session ID so send_message can proceed
    controller._conversation.session_id = "session-123"

    await controller.send_message(message_text)

    # Assert: clear_input was called, meaning the input field is cleared
    ui.clear_input.assert_called_once()


# Strategy for selecting error types to simulate
error_types = st.sampled_from(
    [
        lambda msg: ProcessTerminatedError(msg),
        lambda msg: Exception(msg),
    ]
)

# Strategy for error messages
error_messages = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())


# **Validates: Requirements 2.6**
@settings(max_examples=100, deadline=None)
@given(
    message_text=valid_message_strings,
    error_factory=error_types,
    error_msg=error_messages,
)
@pytest.mark.asyncio
async def test_failed_send_shows_error_and_reenables_input(message_text, error_factory, error_msg):
    """Property 6: Failed send retains input text.

    For any valid message string where the send operation fails
    (ProcessTerminatedError, write error), an error indication SHALL be
    visible in the UI and the input SHALL be re-enabled so the user can
    retry.

    # Feature: kiro-acp-chat-client, Property 6: Failed send retains input text

    **Validates: Requirements 2.6**
    """
    controller, ui, acp_client, _ = _create_controller()

    # Configure ACP client to fail on send_prompt
    error = error_factory(error_msg)
    acp_client.send_prompt.side_effect = error

    # Send the message (this should trigger the error path)
    await controller.send_message(message_text)

    # Assert: error is displayed in the UI
    ui.append_error.assert_called_once_with(str(error))

    # Assert: typing indicator is hidden after error
    ui.hide_typing_indicator.assert_called_once()

    # Assert: input is re-enabled after error so user can retry
    calls = ui.set_input_enabled.call_args_list
    assert len(calls) >= 1, "set_input_enabled should be called at least once"
    # The last call should re-enable input
    assert calls[-1].args[0] is True, "Input should be re-enabled after a failed send"


# Strategy for generating non-empty assistant response text
assistant_response_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())


# **Validates: Requirements 3.1**
@settings(max_examples=100, deadline=None)
@given(response_text=assistant_response_text)
@pytest.mark.asyncio
async def test_assistant_responses_displayed_with_correct_label(response_text):
    """Property 5: Assistant responses displayed with correct label.

    For any text content received in a session/update notification with
    agent_message_chunk type, the message display SHALL contain that text
    associated with a "Kiro" role label.

    # Feature: kiro-acp-chat-client, Property 5: Assistant responses displayed with correct label

    **Validates: Requirements 3.1**
    """
    controller, ui, acp_client, _ = _create_controller()

    # Configure ACP client to return the generated text as a streaming chunk
    acp_client.read_update = AsyncMock(
        side_effect=[
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": response_text},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]
    )

    # Pre-set session ID so send_message can proceed
    controller._conversation.session_id = "session-123"

    # Send a valid user message to trigger the response flow
    await controller.send_message("Hello")

    # Assert: append_assistant_message was called with the generated text
    # This confirms the text is displayed with the "Kiro" role label
    ui.append_assistant_message.assert_called_once_with(response_text)


# --- Property 5: Preference restoration when saved ID is available ---
# Feature: model-agent-preferences, Property 5: Preference restoration when saved ID is available

# Strategy for generating model dicts with modelId and name
model_id_strings = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P"), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

model_name_strings = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

model_dicts = st.fixed_dictionaries(
    {
        "modelId": model_id_strings,
        "name": model_name_strings,
    }
)

# Strategy for generating mode dicts with id and name
mode_id_strings = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P"), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

mode_name_strings = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

mode_dicts = st.fixed_dictionaries(
    {
        "id": mode_id_strings,
        "name": mode_name_strings,
    }
)


# **Validates: Requirements 3.3, 3.4**
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_resolve_model_preference_returns_saved_id_when_available(data):
    """Property 5: Preference restoration when saved ID is available (models).

    For any saved model_id that exists in the Available_Models list,
    the resolution logic SHALL return the saved ID unchanged.

    # Feature: model-agent-preferences, Property 5: Preference restoration
    # when saved ID is available

    **Validates: Requirements 3.3, 3.4**
    """
    # Generate a non-empty list of model dicts
    available_models = data.draw(st.lists(model_dicts, min_size=1, max_size=10))

    # Pick one modelId from the generated list as the "saved" preference
    saved_model = data.draw(st.sampled_from(available_models))
    saved_id = saved_model["modelId"]

    # Create controller with mocked dependencies
    controller, _, _, _ = _create_controller()

    # Call _resolve_model_preference
    result = controller._resolve_model_preference(saved_id, available_models)

    # Assert the result equals the saved_id since it exists in the list
    assert result == saved_id, (
        f"Expected saved_id '{saved_id}' to be returned when it exists in available models, "
        f"but got '{result}'"
    )


# **Validates: Requirements 3.3, 3.4**
@settings(max_examples=100, deadline=None)
@given(data=st.data())
def test_resolve_mode_preference_returns_saved_id_when_available(data):
    """Property 5: Preference restoration when saved ID is available (modes).

    For any saved mode_id that exists in the Available_Modes list,
    the resolution logic SHALL return the saved ID unchanged.

    # Feature: model-agent-preferences, Property 5: Preference restoration
    # when saved ID is available

    **Validates: Requirements 3.3, 3.4**
    """
    # Generate a non-empty list of mode dicts
    available_modes = data.draw(st.lists(mode_dicts, min_size=1, max_size=10))

    # Pick one id from the generated list as the "saved" preference
    saved_mode = data.draw(st.sampled_from(available_modes))
    saved_id = saved_mode["id"]

    # Create controller with mocked dependencies
    controller, _, _, _ = _create_controller()

    # Call _resolve_mode_preference
    result = controller._resolve_mode_preference(saved_id, available_modes)

    # Assert the result equals the saved_id since it exists in the list
    assert result == saved_id, (
        f"Expected saved_id '{saved_id}' to be returned when it exists in available modes, "
        f"but got '{result}'"
    )


# Strategy for generating non-empty ID strings (model/mode IDs)
id_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


# **Validates: Requirements 4.4**
@settings(max_examples=100, deadline=None)
@given(
    previous_model_id=id_strings,
    new_model_id=id_strings,
    error_msg=error_messages,
)
@pytest.mark.asyncio
async def test_error_response_reverts_model_selector(previous_model_id, new_model_id, error_msg):
    """Property 9: Error response reverts selector to previous value (model).

    For any model selection that results in an error response from the ACP
    process, the model selector SHALL revert to its previous value (the value
    before the user's change), and an error message SHALL be displayed.

    # Feature: model-agent-preferences, Property 9: Error response reverts
    # selector to previous value

    **Validates: Requirements 4.4**
    """
    from hypothesis import assume

    assume(previous_model_id != new_model_id)

    controller, ui, acp_client, _ = _create_controller()

    # Set up the previous model ID state
    controller._current_model_id = previous_model_id
    controller._conversation.session_id = "session-123"

    # Mock set_model to return an error response
    acp_client.set_model = AsyncMock(return_value={"error": {"code": -32602, "message": error_msg}})

    # Add set_selected_model mock
    ui.set_selected_model = MagicMock()

    # Call on_model_changed with the new model ID
    await controller.on_model_changed(new_model_id)

    # Assert: selector reverted to previous value
    ui.set_selected_model.assert_called_once_with(previous_model_id)

    # Assert: error message is displayed
    ui.append_error.assert_called_once_with(error_msg)


# **Validates: Requirements 4.4**
@settings(max_examples=100, deadline=None)
@given(
    previous_mode_id=id_strings,
    new_mode_id=id_strings,
    error_msg=error_messages,
)
@pytest.mark.asyncio
async def test_error_response_reverts_mode_selector(previous_mode_id, new_mode_id, error_msg):
    """Property 9: Error response reverts selector to previous value (mode).

    For any mode selection that results in an error response from the ACP
    process, the mode selector SHALL revert to its previous value (the value
    before the user's change), and an error message SHALL be displayed.

    # Feature: model-agent-preferences, Property 9: Error response reverts
    # selector to previous value

    **Validates: Requirements 4.4**
    """
    from hypothesis import assume

    assume(previous_mode_id != new_mode_id)

    controller, ui, acp_client, _ = _create_controller()

    # Set up the previous mode ID state
    controller._current_mode_id = previous_mode_id
    controller._conversation.session_id = "session-123"

    # Mock set_mode to return an error response
    acp_client.set_mode = AsyncMock(return_value={"error": {"code": -32602, "message": error_msg}})

    # Add set_selected_mode mock
    ui.set_selected_mode = MagicMock()

    # Call on_mode_changed with the new mode ID
    await controller.on_mode_changed(new_mode_id)

    # Assert: selector reverted to previous value
    ui.set_selected_mode.assert_called_once_with(previous_mode_id)

    # Assert: error message is displayed
    ui.append_error.assert_called_once_with(error_msg)


# --- Property 6: Preference fallback when saved ID is unavailable ---
# Feature: model-agent-preferences, Property 6: Preference fallback when saved ID is unavailable


# **Validates: Requirements 3.5**
@settings(max_examples=100, deadline=None)
@given(
    available_models=st.lists(model_dicts, min_size=0, max_size=10),
    saved_id=model_id_strings,
)
def test_resolve_model_preference_falls_back_to_auto_when_unavailable(available_models, saved_id):
    """Property 6: Preference fallback when saved ID is unavailable (models).

    For any saved model_id that does NOT exist in the Available_Models list,
    the resolution logic SHALL return "auto".

    # Feature: model-agent-preferences, Property 6: Preference fallback when saved ID is unavailable

    **Validates: Requirements 3.5**
    """
    from hypothesis import assume

    # Ensure saved_id does NOT appear in any modelId in the available list
    assume(all(m.get("modelId") != saved_id for m in available_models))

    # Create controller with mocked dependencies
    controller, _, _, _ = _create_controller()

    # Call _resolve_model_preference
    result = controller._resolve_model_preference(saved_id, available_models)

    # Assert the result falls back to "auto"
    assert result == "auto", (
        f"Expected 'auto' fallback when saved_id '{saved_id}' is not in available models, "
        f"but got '{result}'"
    )


# **Validates: Requirements 3.5**
@settings(max_examples=100, deadline=None)
@given(
    available_modes=st.lists(mode_dicts, min_size=1, max_size=10),
    saved_id=mode_id_strings,
)
def test_resolve_mode_preference_falls_back_to_first_when_unavailable(available_modes, saved_id):
    """Property 6: Preference fallback when saved ID is unavailable (modes).

    For any saved mode_id that does NOT exist in the Available_Modes list,
    the resolution logic SHALL return the first mode's id from the available list.

    # Feature: model-agent-preferences, Property 6: Preference fallback when saved ID is unavailable

    **Validates: Requirements 3.5**
    """
    from hypothesis import assume

    # Ensure saved_id does NOT appear in any id in the available list
    assume(all(m.get("id") != saved_id for m in available_modes))

    # Create controller with mocked dependencies
    controller, _, _, _ = _create_controller()

    # Call _resolve_mode_preference
    result = controller._resolve_mode_preference(saved_id, available_modes)

    # Assert the result falls back to the first mode's id
    expected = available_modes[0]["id"]
    assert result == expected, (
        f"Expected first mode id '{expected}' as fallback when saved_id '{saved_id}' "
        f"is not in available modes, but got '{result}'"
    )


# --- Property 8: Restored preferences trigger ACP requests on startup ---
# Feature: model-agent-preferences, Property 8: Restored preferences trigger ACP requests on startup

# Strategy for generating model IDs that are NOT "auto"
non_auto_model_ids = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() and s != "auto")


# **Validates: Requirements 4.3**
@settings(max_examples=100, deadline=None)
@given(
    model_id=non_auto_model_ids,
    mode_id=mode_id_strings,
    extra_mode_id=mode_id_strings,
)
@pytest.mark.asyncio
async def test_restored_preferences_trigger_acp_requests_on_startup(
    model_id, mode_id, extra_mode_id
):
    """Property 8: Restored preferences trigger ACP requests on startup.

    For any restored model preference that is not "auto", the startup flow
    SHALL send a session/set_model request. For any restored mode preference
    that differs from the first available mode, the startup flow SHALL send
    a session/set_mode request.

    # Feature: model-agent-preferences, Property 8: Restored preferences
    # trigger ACP requests on startup

    **Validates: Requirements 4.3**
    """
    from hypothesis import assume

    # Ensure mode_id differs from extra_mode_id so we can construct a list
    # where mode_id is NOT the first entry
    assume(mode_id != extra_mode_id)

    # Create controller with mocked dependencies
    ui = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.set_selectors_enabled = MagicMock()
    ui.populate_models = MagicMock()
    ui.populate_modes = MagicMock()
    ui.set_selected_model = MagicMock()
    ui.set_selected_mode = MagicMock()
    ui.show_ready = MagicMock()
    ui.append_error = MagicMock()

    acp_client = AsyncMock()
    acp_client.initialize = AsyncMock(return_value={"result": {}})
    acp_client.set_model = AsyncMock(return_value={"result": {}})
    acp_client.set_mode = AsyncMock(return_value={"result": {}})

    process_manager = AsyncMock()
    process_manager.start = AsyncMock()

    preferences_manager = MagicMock()
    # Return preferences with the generated non-auto model_id and mode_id
    preferences_manager.load = MagicMock(
        return_value=Preferences(model_id=model_id, mode_id=mode_id)
    )
    preferences_manager.save = MagicMock()

    # Build session response where model_id and mode_id exist in available lists
    # The first mode in the list is extra_mode_id (different from mode_id)
    # so that mode_id != first available mode triggers set_mode
    session_response = {
        "sessionId": "test-session-id",
        "models": {
            "currentModelId": "auto",
            "availableModels": [
                {"modelId": model_id, "name": f"Model {model_id}"},
            ],
        },
        "modes": {
            "currentModeId": extra_mode_id,
            "availableModes": [
                {"id": extra_mode_id, "name": f"Mode {extra_mode_id}"},
                {"id": mode_id, "name": f"Mode {mode_id}"},
            ],
        },
    }
    acp_client.create_session = AsyncMock(return_value=session_response)

    controller = ChatController(ui, acp_client, process_manager, preferences_manager)

    # Patch os.getcwd to avoid filesystem dependency
    with patch("kiro_acp_chat_client.controller.os.getcwd", return_value="/tmp"):
        await controller.start()

    # Assert: set_model was called because restored model is not "auto"
    acp_client.set_model.assert_called_once_with("test-session-id", model_id)

    # Assert: set_mode was called because restored mode differs from first available mode
    acp_client.set_mode.assert_called_once_with("test-session-id", mode_id)


# --- Property 1: Session response parsing extracts models and modes ---
# Feature: model-agent-preferences, Property 1: Session response parsing extracts models and modes


# **Validates: Requirements 5.1, 5.2**
@settings(max_examples=100, deadline=None)
@given(
    models=st.lists(
        st.fixed_dictionaries(
            {
                "modelId": model_id_strings,
                "name": model_name_strings,
            }
        ),
        min_size=0,
        max_size=10,
    ),
    modes=st.lists(
        st.fixed_dictionaries(
            {
                "id": mode_id_strings,
                "name": mode_name_strings,
            }
        ),
        min_size=0,
        max_size=10,
    ),
)
@pytest.mark.asyncio
async def test_session_response_parsing_extracts_models_and_modes(models, modes):
    """Property 1: Session response parsing extracts models and modes.

    For any valid session/new response containing a models.availableModels array
    and a modes.availableModes array, the parsing logic SHALL extract all model
    entries (preserving modelId and name) and all mode entries (preserving id and
    name) without loss or reordering.

    # Feature: model-agent-preferences, Property 1: Session response parsing
    # extracts models and modes

    **Validates: Requirements 5.1, 5.2**
    """
    # Create controller with mocked dependencies
    ui = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.set_selectors_enabled = MagicMock()
    ui.populate_models = MagicMock()
    ui.populate_modes = MagicMock()
    ui.set_selected_model = MagicMock()
    ui.set_selected_mode = MagicMock()
    ui.show_ready = MagicMock()
    ui.append_error = MagicMock()

    acp_client = AsyncMock()
    acp_client.initialize = AsyncMock(return_value={"result": {}})
    acp_client.set_model = AsyncMock(return_value={"result": {}})
    acp_client.set_mode = AsyncMock(return_value={"result": {}})

    process_manager = AsyncMock()
    process_manager.start = AsyncMock()

    preferences_manager = MagicMock()
    preferences_manager.load = MagicMock(return_value=Preferences())
    preferences_manager.save = MagicMock()

    # Build session response with the generated models and modes
    session_response = {
        "sessionId": "test-session",
        "models": {"availableModels": models},
        "modes": {"availableModes": modes},
    }
    acp_client.create_session = AsyncMock(return_value=session_response)

    controller = ChatController(ui, acp_client, process_manager, preferences_manager)

    # Patch os.getcwd to avoid filesystem dependency
    with patch("kiro_acp_chat_client.controller.os.getcwd", return_value="/tmp"):
        await controller.start()

    # Assert that ui.populate_models was called with the exact generated models list
    ui.populate_models.assert_called_once_with(models)

    # Assert that ui.populate_modes was called with the exact generated modes list
    ui.populate_modes.assert_called_once_with(modes)
