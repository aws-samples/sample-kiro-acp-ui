"""Unit tests for the ChatController class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kiro_acp_chat_client.controller import ChatController
from kiro_acp_chat_client.preferences_manager import Preferences
from kiro_acp_chat_client.process_manager import (
    ProcessStartError,
    ProcessTerminatedError,
)


@pytest.fixture
def mock_ui():
    """Create a mock ChatUI."""
    ui = MagicMock()
    ui.append_user_message = MagicMock()
    ui.append_assistant_message = MagicMock()
    ui.append_error = MagicMock()
    ui.show_typing_indicator = MagicMock()
    ui.hide_typing_indicator = MagicMock()
    ui.clear_input = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.get_input_text = MagicMock(return_value="")
    ui.populate_models = MagicMock()
    ui.populate_modes = MagicMock()
    ui.set_selected_model = MagicMock()
    ui.set_selected_mode = MagicMock()
    ui.set_selectors_enabled = MagicMock()
    ui.show_ready = MagicMock()
    return ui


@pytest.fixture
def mock_acp_client():
    """Create a mock ACPClient."""
    client = AsyncMock()
    client.initialize = AsyncMock(return_value={"result": {}})
    client.create_session = AsyncMock(
        return_value={
            "sessionId": "session-123",
            "models": {
                "currentModelId": "auto",
                "availableModels": [
                    {"modelId": "model-a", "name": "Model A"},
                    {"modelId": "model-b", "name": "Model B"},
                ],
            },
            "modes": {
                "currentModeId": "mode-1",
                "availableModes": [
                    {"id": "mode-1", "name": "Mode One"},
                    {"id": "mode-2", "name": "Mode Two"},
                ],
            },
        }
    )
    client.send_prompt = AsyncMock()
    client.read_update = AsyncMock()
    client.set_model = AsyncMock(return_value={"id": 3, "result": {}})
    client.set_mode = AsyncMock(return_value={"id": 4, "result": {}})
    return client


@pytest.fixture
def mock_process_manager():
    """Create a mock ProcessManager."""
    pm = AsyncMock()
    pm.shutdown = AsyncMock()
    pm.is_running = True
    return pm


@pytest.fixture
def mock_preferences_manager():
    """Create a mock PreferencesManager."""
    pm = MagicMock()
    pm.load = MagicMock(return_value=Preferences())
    pm.save = MagicMock()
    return pm


@pytest.fixture
def controller(mock_ui, mock_acp_client, mock_process_manager, mock_preferences_manager):
    """Create a ChatController with mocked dependencies."""
    return ChatController(mock_ui, mock_acp_client, mock_process_manager, mock_preferences_manager)


class TestStart:
    """Tests for ChatController.start()."""

    async def test_start_initializes_and_creates_session(self, controller, mock_acp_client):
        """start() calls initialize and create_session."""
        await controller.start()

        mock_acp_client.initialize.assert_called_once()
        mock_acp_client.create_session.assert_called_once()

    async def test_start_stores_session_id(self, controller, mock_acp_client):
        """start() stores the session ID in conversation."""
        mock_acp_client.create_session.return_value = {
            "sessionId": "sess-abc",
            "models": {"availableModels": []},
            "modes": {"availableModes": []},
        }
        await controller.start()

        assert controller._conversation.session_id == "sess-abc"

    async def test_start_uses_cwd(
        self, mock_ui, mock_acp_client, mock_process_manager, mock_preferences_manager
    ):
        """start() passes cwd to create_session."""
        controller = ChatController(
            mock_ui,
            mock_acp_client,
            mock_process_manager,
            mock_preferences_manager,
            cwd="/test/dir",
        )
        await controller.start()

        mock_acp_client.create_session.assert_called_once_with("/test/dir")

    async def test_start_populates_models_and_modes(self, controller, mock_acp_client, mock_ui):
        """start() populates model and mode dropdowns from session response."""
        await controller.start()

        mock_ui.populate_models.assert_called_once_with(
            [
                {"modelId": "model-a", "name": "Model A"},
                {"modelId": "model-b", "name": "Model B"},
            ]
        )
        mock_ui.populate_modes.assert_called_once_with(
            [
                {"id": "mode-1", "name": "Mode One"},
                {"id": "mode-2", "name": "Mode Two"},
            ]
        )

    async def test_start_restores_default_preferences(
        self, controller, mock_acp_client, mock_ui, mock_preferences_manager
    ):
        """start() sets default selections when no prior preferences exist."""
        mock_preferences_manager.load.return_value = Preferences()
        await controller.start()

        # Default model is "auto", default mode is first available ("mode-1")
        mock_ui.set_selected_model.assert_called_once_with("auto")
        mock_ui.set_selected_mode.assert_called_once_with("mode-1")

    async def test_start_restores_saved_preferences(
        self, controller, mock_acp_client, mock_ui, mock_preferences_manager
    ):
        """start() restores saved preferences when they exist in available options."""
        mock_preferences_manager.load.return_value = Preferences(
            model_id="model-b", mode_id="mode-2"
        )
        await controller.start()

        mock_ui.set_selected_model.assert_called_once_with("model-b")
        mock_ui.set_selected_mode.assert_called_once_with("mode-2")

    async def test_start_sends_acp_requests_for_non_default_prefs(
        self, controller, mock_acp_client, mock_preferences_manager
    ):
        """start() sends set_model/set_mode for non-default restored preferences."""
        mock_preferences_manager.load.return_value = Preferences(
            model_id="model-b", mode_id="mode-2"
        )
        await controller.start()

        mock_acp_client.set_model.assert_called_once_with("session-123", "model-b")
        mock_acp_client.set_mode.assert_called_once_with("session-123", "mode-2")

    async def test_start_does_not_send_acp_for_default_prefs(
        self, controller, mock_acp_client, mock_preferences_manager
    ):
        """start() does not send set_model/set_mode for default preferences."""
        mock_preferences_manager.load.return_value = Preferences()
        await controller.start()

        mock_acp_client.set_model.assert_not_called()
        mock_acp_client.set_mode.assert_not_called()

    async def test_start_saves_resolved_preferences(self, controller, mock_preferences_manager):
        """start() saves resolved preferences after startup."""
        mock_preferences_manager.load.return_value = Preferences()
        await controller.start()

        mock_preferences_manager.save.assert_called_once_with(
            Preferences(model_id="auto", mode_id="mode-1")
        )

    async def test_start_enables_selectors_on_success(self, controller, mock_ui):
        """start() enables selectors on successful startup."""
        await controller.start()

        # Last call to set_selectors_enabled should be True
        calls = mock_ui.set_selectors_enabled.call_args_list
        assert calls[-1].args[0] is True

    async def test_start_error_disables_input(self, controller, mock_acp_client, mock_ui):
        """start() disables input on error."""
        mock_acp_client.initialize.side_effect = ProcessStartError("Not found")
        await controller.start()

        mock_ui.set_input_enabled.assert_called_with(False)

    async def test_start_error_disables_selectors(self, controller, mock_acp_client, mock_ui):
        """start() disables selectors on error."""
        mock_acp_client.initialize.side_effect = ProcessStartError("Not found")
        await controller.start()

        # Last call to set_selectors_enabled should be False
        calls = mock_ui.set_selectors_enabled.call_args_list
        assert calls[-1].args[0] is False

    async def test_start_error_shows_error_message(self, controller, mock_acp_client, mock_ui):
        """start() shows error in UI on failure."""
        mock_acp_client.initialize.side_effect = ProcessStartError("Could not find kiro-cli.")
        await controller.start()

        mock_ui.append_error.assert_called_once_with("Could not find kiro-cli.")

    async def test_start_session_creation_error(self, controller, mock_acp_client, mock_ui):
        """start() handles session creation failure."""
        mock_acp_client.create_session.side_effect = ProcessTerminatedError("Connection lost")
        await controller.start()

        mock_ui.set_input_enabled.assert_called_with(False)
        mock_ui.append_error.assert_called_once_with("Connection lost")

    async def test_start_missing_models_field(self, controller, mock_acp_client, mock_ui):
        """start() handles missing models field gracefully."""
        mock_acp_client.create_session.return_value = {
            "sessionId": "sess-1",
            "modes": {"availableModes": [{"id": "m1", "name": "M1"}]},
        }
        await controller.start()

        mock_ui.populate_models.assert_called_once_with([])

    async def test_start_missing_modes_field(self, controller, mock_acp_client, mock_ui):
        """start() handles missing modes field gracefully."""
        mock_acp_client.create_session.return_value = {
            "sessionId": "sess-1",
            "models": {"availableModels": [{"modelId": "x", "name": "X"}]},
        }
        await controller.start()

        mock_ui.populate_modes.assert_called_once_with([])

    async def test_start_fallback_when_saved_model_unavailable(
        self, controller, mock_acp_client, mock_ui, mock_preferences_manager
    ):
        """start() falls back to 'auto' when saved model is not in available list."""
        mock_preferences_manager.load.return_value = Preferences(
            model_id="nonexistent-model", mode_id="mode-1"
        )
        await controller.start()

        mock_ui.set_selected_model.assert_called_once_with("auto")

    async def test_start_fallback_when_saved_mode_unavailable(
        self, controller, mock_acp_client, mock_ui, mock_preferences_manager
    ):
        """start() falls back to first mode when saved mode is not in available list."""
        mock_preferences_manager.load.return_value = Preferences(
            model_id="auto", mode_id="nonexistent-mode"
        )
        await controller.start()

        mock_ui.set_selected_mode.assert_called_once_with("mode-1")


class TestSendMessage:
    """Tests for ChatController.send_message()."""

    async def test_send_empty_string_does_nothing(self, controller, mock_ui):
        """send_message with empty string is a no-op."""
        await controller.send_message("")

        mock_ui.append_user_message.assert_not_called()
        mock_ui.clear_input.assert_not_called()

    async def test_send_whitespace_only_does_nothing(self, controller, mock_ui):
        """send_message with whitespace-only string is a no-op."""
        await controller.send_message("   \t\n  ")

        mock_ui.append_user_message.assert_not_called()
        mock_ui.clear_input.assert_not_called()

    async def test_send_over_2000_chars_does_nothing(self, controller, mock_ui):
        """send_message with >2000 chars is a no-op."""
        await controller.send_message("a" * 2001)

        mock_ui.append_user_message.assert_not_called()
        mock_ui.clear_input.assert_not_called()

    async def test_send_exactly_2000_chars_succeeds(self, controller, mock_ui, mock_acp_client):
        """send_message with exactly 2000 chars is valid."""
        # Set up streaming response
        mock_acp_client.read_update.side_effect = [
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

        await controller.send_message("a" * 2000)

        mock_ui.append_user_message.assert_called_once_with("a" * 2000)

    async def test_send_displays_user_message(self, controller, mock_ui, mock_acp_client):
        """send_message displays the user message in UI."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "Hi!"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        mock_ui.append_user_message.assert_called_once_with("Hello")

    async def test_send_clears_input(self, controller, mock_ui, mock_acp_client):
        """send_message clears the input field."""
        mock_acp_client.read_update.side_effect = [
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

        await controller.send_message("Hello")

        mock_ui.clear_input.assert_called_once()

    async def test_send_shows_typing_indicator(self, controller, mock_ui, mock_acp_client):
        """send_message shows typing indicator."""
        mock_acp_client.read_update.side_effect = [
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        mock_ui.show_typing_indicator.assert_called_once()

    async def test_send_disables_input_during_response(self, controller, mock_ui, mock_acp_client):
        """send_message disables input while waiting for response."""
        mock_acp_client.read_update.side_effect = [
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        # Input should be disabled then re-enabled
        mock_ui.set_input_enabled.assert_any_call(False)
        mock_ui.set_input_enabled.assert_any_call(True)

    async def test_send_streams_response_chunks(self, controller, mock_ui, mock_acp_client):
        """send_message accumulates streaming chunks and displays full response."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "Hello "},
                    }
                },
            },
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "world!"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hi")

        mock_ui.append_assistant_message.assert_called_once_with("Hello world!")

    async def test_send_hides_typing_on_complete(self, controller, mock_ui, mock_acp_client):
        """send_message hides typing indicator when response is complete."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "Done"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        mock_ui.hide_typing_indicator.assert_called_once()

    async def test_send_reenables_input_on_complete(self, controller, mock_ui, mock_acp_client):
        """send_message re-enables input when response is complete."""
        mock_acp_client.read_update.side_effect = [
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        # Last call to set_input_enabled should be True
        calls = mock_ui.set_input_enabled.call_args_list
        assert calls[-1].args[0] is True

    async def test_send_error_shows_error_and_retains_input(
        self, controller, mock_ui, mock_acp_client
    ):
        """send_message shows error and retains input on failure."""
        mock_acp_client.send_prompt.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        await controller.send_message("Hello")

        mock_ui.hide_typing_indicator.assert_called_once()
        mock_ui.append_error.assert_called_once_with(
            "Connection to Kiro lost. Please restart the application."
        )
        # Input should be re-enabled
        calls = mock_ui.set_input_enabled.call_args_list
        assert calls[-1].args[0] is True

    async def test_send_error_during_streaming(self, controller, mock_ui, mock_acp_client):
        """send_message handles error during streaming."""
        mock_acp_client.read_update.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        await controller.send_message("Hello")

        mock_ui.hide_typing_indicator.assert_called_once()
        mock_ui.append_error.assert_called_once()
        calls = mock_ui.set_input_enabled.call_args_list
        assert calls[-1].args[0] is True

    async def test_send_empty_response_shows_error(self, controller, mock_ui, mock_acp_client):
        """send_message shows error when agent returns empty response."""
        mock_acp_client.read_update.side_effect = [
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        mock_ui.append_error.assert_called_once_with(
            "Kiro could not generate a response. Please try again."
        )

    async def test_send_adds_to_conversation(self, controller, mock_acp_client):
        """send_message adds user message to conversation model."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "reply"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        await controller.send_message("Hello")

        assert len(controller._conversation.messages) == 2
        assert controller._conversation.messages[0].role == "user"
        assert controller._conversation.messages[0].content == "Hello"
        assert controller._conversation.messages[1].role == "assistant"
        assert controller._conversation.messages[1].content == "reply"


class TestShutdown:
    """Tests for ChatController.shutdown()."""

    async def test_shutdown_calls_process_manager(self, controller, mock_process_manager):
        """shutdown() calls process_manager.shutdown()."""
        await controller.shutdown()

        mock_process_manager.shutdown.assert_called_once()


class TestResolveModelPreference:
    """Tests for ChatController._resolve_model_preference()."""

    def test_returns_auto_when_saved_is_auto(self, controller):
        """_resolve_model_preference returns 'auto' when saved_id is 'auto'."""
        available = [{"modelId": "model-1", "name": "Model 1"}]
        result = controller._resolve_model_preference("auto", available)
        assert result == "auto"

    def test_returns_saved_id_when_in_available(self, controller):
        """_resolve_model_preference returns saved_id when it exists in available."""
        available = [
            {"modelId": "model-1", "name": "Model 1"},
            {"modelId": "model-2", "name": "Model 2"},
        ]
        result = controller._resolve_model_preference("model-2", available)
        assert result == "model-2"

    def test_returns_auto_when_saved_not_in_available(self, controller):
        """_resolve_model_preference returns 'auto' when saved_id is not in available."""
        available = [
            {"modelId": "model-1", "name": "Model 1"},
            {"modelId": "model-2", "name": "Model 2"},
        ]
        result = controller._resolve_model_preference("model-gone", available)
        assert result == "auto"

    def test_returns_auto_when_available_is_empty(self, controller):
        """_resolve_model_preference returns 'auto' when available list is empty."""
        result = controller._resolve_model_preference("model-1", [])
        assert result == "auto"

    def test_returns_auto_when_available_has_no_modelId_key(self, controller):
        """_resolve_model_preference returns 'auto' when dicts lack 'modelId' key."""
        available = [{"name": "Model 1"}, {"name": "Model 2"}]
        result = controller._resolve_model_preference("model-1", available)
        assert result == "auto"


class TestResolveModePreference:
    """Tests for ChatController._resolve_mode_preference()."""

    def test_returns_saved_id_when_in_available(self, controller):
        """_resolve_mode_preference returns saved_id when it exists in available."""
        available = [
            {"id": "mode-1", "name": "Mode 1"},
            {"id": "mode-2", "name": "Mode 2"},
        ]
        result = controller._resolve_mode_preference("mode-2", available)
        assert result == "mode-2"

    def test_returns_first_mode_id_when_saved_not_in_available(self, controller):
        """_resolve_mode_preference returns first mode's id when saved_id is not found."""
        available = [
            {"id": "mode-1", "name": "Mode 1"},
            {"id": "mode-2", "name": "Mode 2"},
        ]
        result = controller._resolve_mode_preference("mode-gone", available)
        assert result == "mode-1"

    def test_returns_empty_string_when_available_is_empty(self, controller):
        """_resolve_mode_preference returns '' when available list is empty."""
        result = controller._resolve_mode_preference("mode-1", [])
        assert result == ""

    def test_returns_first_mode_id_when_saved_is_empty_string(self, controller):
        """_resolve_mode_preference returns first mode's id when saved_id is empty."""
        available = [
            {"id": "default-mode", "name": "Default"},
            {"id": "mode-2", "name": "Mode 2"},
        ]
        result = controller._resolve_mode_preference("", available)
        assert result == "default-mode"

    def test_returns_empty_when_first_mode_has_no_id_key(self, controller):
        """_resolve_mode_preference returns '' when first mode dict lacks 'id' key."""
        available = [{"name": "Mode 1"}]
        result = controller._resolve_mode_preference("missing", available)
        assert result == ""


class TestOnModelChanged:
    """Tests for ChatController.on_model_changed()."""

    async def test_on_model_changed_success_saves_preferences(
        self, controller, mock_acp_client, mock_preferences_manager, mock_ui
    ):
        """on_model_changed saves preferences on successful ACP response."""
        # Set up initial state
        controller._current_model_id = "model-a"
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_model.return_value = {"id": 3, "result": {}}

        await controller.on_model_changed("model-b")

        mock_acp_client.set_model.assert_called_once_with("session-123", "model-b")
        mock_preferences_manager.save.assert_called_once_with(
            Preferences(model_id="model-b", mode_id="mode-1")
        )
        assert controller._current_model_id == "model-b"

    async def test_on_model_changed_error_response_reverts_selector(
        self, controller, mock_acp_client, mock_preferences_manager, mock_ui
    ):
        """on_model_changed reverts selector and shows error on error response."""
        controller._current_model_id = "model-a"
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_model.return_value = {
            "id": 3,
            "error": {"code": -1, "message": "Model not available"},
        }

        await controller.on_model_changed("model-b")

        mock_ui.set_selected_model.assert_called_once_with("model-a")
        mock_ui.append_error.assert_called_once_with("Model not available")
        mock_preferences_manager.save.assert_not_called()
        assert controller._current_model_id == "model-a"

    async def test_on_model_changed_error_response_default_message(
        self, controller, mock_acp_client, mock_ui
    ):
        """on_model_changed uses default error message when error has no message field."""
        controller._current_model_id = "model-a"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_model.return_value = {
            "id": 3,
            "error": {"code": -1},
        }

        await controller.on_model_changed("model-b")

        mock_ui.append_error.assert_called_once_with("Failed to set model")

    async def test_on_model_changed_exception_reverts_selector(
        self, controller, mock_acp_client, mock_preferences_manager, mock_ui
    ):
        """on_model_changed reverts selector and shows error on exception."""
        controller._current_model_id = "model-a"
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_model.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        await controller.on_model_changed("model-b")

        mock_ui.set_selected_model.assert_called_once_with("model-a")
        mock_ui.append_error.assert_called_once_with(
            "Connection to Kiro lost. Please restart the application."
        )
        mock_preferences_manager.save.assert_not_called()
        assert controller._current_model_id == "model-a"


class TestOnModeChanged:
    """Tests for ChatController.on_mode_changed()."""

    async def test_on_mode_changed_success_saves_preferences(
        self, controller, mock_acp_client, mock_preferences_manager, mock_ui
    ):
        """on_mode_changed saves preferences on successful ACP response."""
        controller._current_model_id = "model-a"
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_mode.return_value = {"id": 4, "result": {}}

        await controller.on_mode_changed("mode-2")

        mock_acp_client.set_mode.assert_called_once_with("session-123", "mode-2")
        mock_preferences_manager.save.assert_called_once_with(
            Preferences(model_id="model-a", mode_id="mode-2")
        )
        assert controller._current_mode_id == "mode-2"

    async def test_on_mode_changed_error_response_reverts_selector(
        self, controller, mock_acp_client, mock_preferences_manager, mock_ui
    ):
        """on_mode_changed reverts selector and shows error on error response."""
        controller._current_model_id = "model-a"
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_mode.return_value = {
            "id": 4,
            "error": {"code": -1, "message": "Mode not supported"},
        }

        await controller.on_mode_changed("mode-2")

        mock_ui.set_selected_mode.assert_called_once_with("mode-1")
        mock_ui.append_error.assert_called_once_with("Mode not supported")
        mock_preferences_manager.save.assert_not_called()
        assert controller._current_mode_id == "mode-1"

    async def test_on_mode_changed_error_response_default_message(
        self, controller, mock_acp_client, mock_ui
    ):
        """on_mode_changed uses default error message when error has no message field."""
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_mode.return_value = {
            "id": 4,
            "error": {"code": -1},
        }

        await controller.on_mode_changed("mode-2")

        mock_ui.append_error.assert_called_once_with("Failed to set mode")

    async def test_on_mode_changed_exception_reverts_selector(
        self, controller, mock_acp_client, mock_preferences_manager, mock_ui
    ):
        """on_mode_changed reverts selector and shows error on exception."""
        controller._current_model_id = "model-a"
        controller._current_mode_id = "mode-1"
        controller._conversation.session_id = "session-123"
        mock_acp_client.set_mode.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        await controller.on_mode_changed("mode-2")

        mock_ui.set_selected_mode.assert_called_once_with("mode-1")
        mock_ui.append_error.assert_called_once_with(
            "Connection to Kiro lost. Please restart the application."
        )
        mock_preferences_manager.save.assert_not_called()
        assert controller._current_mode_id == "mode-1"
