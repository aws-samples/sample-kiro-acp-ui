"""Integration tests for application lifecycle.

Tests the full flow through the controller with mocked dependencies,
verifying startup, send/receive cycles, shutdown, and crash handling.

Validates: Requirements 4.1, 4.3, 4.4, 4.5
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from kiro_acp_chat_client.acp_client import ACPClient
from kiro_acp_chat_client.controller import ChatController
from kiro_acp_chat_client.preferences_manager import PreferencesManager
from kiro_acp_chat_client.process_manager import (
    ProcessManager,
    ProcessTerminatedError,
)


@pytest.fixture
def mock_process_manager():
    """Create a mock ProcessManager simulating a running kiro-cli process."""
    pm = AsyncMock(spec=ProcessManager)
    pm.is_running = True
    pm.start = AsyncMock()
    pm.shutdown = AsyncMock()
    pm.write_message = AsyncMock()
    pm.read_message = AsyncMock()
    return pm


@pytest.fixture
def mock_ui():
    """Create a mock ChatUI for verifying UI interactions."""
    ui = MagicMock()
    ui.append_user_message = MagicMock()
    ui.append_assistant_message = MagicMock()
    ui.append_error = MagicMock()
    ui.show_typing_indicator = MagicMock()
    ui.hide_typing_indicator = MagicMock()
    ui.clear_input = MagicMock()
    ui.set_input_enabled = MagicMock()
    ui.get_input_text = MagicMock(return_value="")
    return ui


@pytest.fixture
def acp_client(mock_process_manager):
    """Create a real ACPClient wired to the mock ProcessManager."""
    return ACPClient(mock_process_manager)


@pytest.fixture
def controller(mock_ui, acp_client, mock_process_manager):
    """Create a ChatController with mock UI and real ACP client over mock process."""
    mock_preferences_manager = MagicMock()
    mock_preferences_manager.load = MagicMock()
    mock_preferences_manager.save = MagicMock()
    return ChatController(mock_ui, acp_client, mock_process_manager, mock_preferences_manager)


class TestApplicationStartup:
    """Test application startup with mock kiro-cli process (initialize + session creation)."""

    async def test_startup_initializes_and_creates_session(
        self, controller, mock_process_manager, mock_ui
    ):
        """Startup sends initialize request, receives capabilities, creates session."""
        # Mock process responses: first for initialize, second for session/new
        mock_process_manager.read_message.side_effect = [
            # Initialize response
            {
                "jsonrpc": "2.0",
                "id": 0,
                "result": {
                    "protocolVersion": 1,
                    "agentCapabilities": {},
                    "agentInfo": {"name": "kiro-cli", "version": "1.0.0"},
                },
            },
            # Session/new response
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "sessionId": "sess-integration-test-001",
                },
            },
        ]

        await controller.start()

        # Verify initialize request was sent
        first_write = mock_process_manager.write_message.call_args_list[0]
        init_msg = first_write[0][0]
        assert init_msg["method"] == "initialize"
        assert init_msg["jsonrpc"] == "2.0"
        assert init_msg["id"] == 0

        # Verify session/new request was sent
        second_write = mock_process_manager.write_message.call_args_list[1]
        session_msg = second_write[0][0]
        assert session_msg["method"] == "session/new"
        assert session_msg["id"] == 1

        # Verify session ID is stored
        assert controller._conversation.session_id == "sess-integration-test-001"

        # Verify no errors were shown
        mock_ui.append_error.assert_not_called()
        # Input should be disabled at start, then re-enabled on success
        calls = mock_ui.set_input_enabled.call_args_list
        assert calls[0].args[0] is False  # disabled during startup
        assert calls[-1].args[0] is True  # enabled after session ready

    async def test_startup_failure_disables_input_and_shows_error(
        self, controller, mock_process_manager, mock_ui
    ):
        """If initialize fails (process terminated), input is disabled and error shown."""
        mock_process_manager.read_message.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        await controller.start()

        mock_ui.set_input_enabled.assert_called_with(False)
        mock_ui.append_error.assert_called_once_with(
            "Connection to Kiro lost. Please restart the application."
        )


class TestFullSendReceiveCycle:
    """Test full send/receive cycle with mock process."""

    async def test_send_receive_with_streaming_chunks(
        self, controller, mock_process_manager, mock_ui
    ):
        """After startup, sending a message streams chunks and displays full response."""
        # Setup: complete startup first
        mock_process_manager.read_message.side_effect = [
            # Initialize response
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            # Session/new response
            {"jsonrpc": "2.0", "id": 1, "result": {"sessionId": "sess-001"}},
        ]
        await controller.start()

        # Now set up the streaming response for send_message
        mock_process_manager.read_message.side_effect = [
            # Streaming chunk 1
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "sess-001",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "Hello, "},
                    },
                },
            },
            # Streaming chunk 2
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "sess-001",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "how can I help?"},
                    },
                },
            },
            # Final response (turn complete)
            {"jsonrpc": "2.0", "id": 2, "result": {}},
        ]

        await controller.send_message("Hi there")

        # Verify user message displayed
        mock_ui.append_user_message.assert_called_once_with("Hi there")

        # Verify typing indicator shown then hidden
        mock_ui.show_typing_indicator.assert_called_once()
        mock_ui.hide_typing_indicator.assert_called_once()

        # Verify full assistant response displayed
        mock_ui.append_assistant_message.assert_called_once_with("Hello, how can I help?")

        # Verify input was cleared and re-enabled
        mock_ui.clear_input.assert_called_once()
        calls = mock_ui.set_input_enabled.call_args_list
        assert calls[-1].args[0] is True

    async def test_send_receive_prompt_request_format(
        self, controller, mock_process_manager, mock_ui
    ):
        """The prompt request sent to the process has correct ACP format."""
        # Setup: complete startup
        mock_process_manager.read_message.side_effect = [
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            {"jsonrpc": "2.0", "id": 1, "result": {"sessionId": "sess-002"}},
        ]
        await controller.start()

        # Setup streaming response
        mock_process_manager.read_message.side_effect = [
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "OK"},
                    },
                },
            },
            {"jsonrpc": "2.0", "id": 2, "result": {}},
        ]

        await controller.send_message("What is Python?")

        # Find the prompt write call (third write after init + session)
        prompt_write = mock_process_manager.write_message.call_args_list[2]
        prompt_msg = prompt_write[0][0]
        assert prompt_msg["method"] == "session/prompt"
        assert prompt_msg["params"]["sessionId"] == "sess-002"
        assert prompt_msg["params"]["prompt"][0]["text"] == "What is Python?"


class TestGracefulShutdown:
    """Test graceful shutdown sequence."""

    async def test_shutdown_calls_process_manager_shutdown(self, controller, mock_process_manager):
        """controller.shutdown() delegates to process_manager.shutdown()."""
        await controller.shutdown()

        mock_process_manager.shutdown.assert_called_once()

    async def test_shutdown_after_active_session(self, controller, mock_process_manager, mock_ui):
        """Shutdown works correctly after an active session was established."""
        # Setup: complete startup
        mock_process_manager.read_message.side_effect = [
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            {"jsonrpc": "2.0", "id": 1, "result": {"sessionId": "sess-003"}},
        ]
        await controller.start()

        # Now shutdown
        await controller.shutdown()

        mock_process_manager.shutdown.assert_called_once()


class TestProcessCrash:
    """Test process crash triggers error display and input disable."""

    async def test_crash_during_streaming_shows_error(
        self, controller, mock_process_manager, mock_ui
    ):
        """If process terminates during streaming, error is shown and input disabled."""
        # Setup: complete startup
        mock_process_manager.read_message.side_effect = [
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            {"jsonrpc": "2.0", "id": 1, "result": {"sessionId": "sess-004"}},
        ]
        await controller.start()

        # Simulate crash during read_update (streaming phase)
        mock_process_manager.read_message.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        await controller.send_message("Hello")

        # Verify error is displayed
        mock_ui.append_error.assert_called_once_with(
            "Connection to Kiro lost. Please restart the application."
        )

        # Verify typing indicator is hidden
        mock_ui.hide_typing_indicator.assert_called_once()

        # Verify input is re-enabled (controller re-enables on error)
        calls = mock_ui.set_input_enabled.call_args_list
        assert calls[-1].args[0] is True

    async def test_crash_during_send_prompt_shows_error(
        self, controller, mock_process_manager, mock_ui
    ):
        """If process terminates during send_prompt, error is shown."""
        # Setup: complete startup
        mock_process_manager.read_message.side_effect = [
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            {"jsonrpc": "2.0", "id": 1, "result": {"sessionId": "sess-005"}},
        ]
        await controller.start()

        # Simulate crash during write (send_prompt)
        mock_process_manager.write_message.side_effect = ProcessTerminatedError(
            "Cannot write: process is not running."
        )

        await controller.send_message("Hello")

        # Verify error is displayed
        mock_ui.append_error.assert_called_once_with("Cannot write: process is not running.")

        # Verify typing indicator is hidden
        mock_ui.hide_typing_indicator.assert_called_once()


class TestPreferenceFlowIntegration:
    """Integration tests for the full model/mode preference flow.

    Uses the full ChatController with mocked ACPClient and ProcessManager,
    but a real PreferencesManager with a temp file.

    Validates: Requirements 1.1, 2.1, 3.3, 4.1, 4.2, 4.3, 4.4
    """

    @pytest.fixture
    def temp_prefs_file(self, tmp_path):
        """Create a temporary preferences file path."""
        return str(tmp_path / "preferences.json")

    @pytest.fixture
    def real_preferences_manager(self, temp_prefs_file):
        """Create a real PreferencesManager with a temp file."""
        return PreferencesManager(temp_prefs_file)

    @pytest.fixture
    def pref_mock_ui(self):
        """Create a mock ChatUI with all preference-related methods."""
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
    def pref_mock_process_manager(self):
        """Create a mock ProcessManager for preference tests."""
        pm = AsyncMock(spec=ProcessManager)
        pm.is_running = True
        pm.start = AsyncMock()
        pm.shutdown = AsyncMock()
        pm.write_message = AsyncMock()
        pm.read_message = AsyncMock()
        return pm

    @pytest.fixture
    def pref_controller(self, pref_mock_ui, pref_mock_process_manager, real_preferences_manager):
        """Create a ChatController with real PreferencesManager."""
        acp = ACPClient(pref_mock_process_manager)
        return ChatController(
            pref_mock_ui, acp, pref_mock_process_manager, real_preferences_manager
        )

    async def test_startup_with_models_and_modes_in_session_response(
        self, pref_controller, pref_mock_process_manager, pref_mock_ui
    ):
        """Startup with models/modes in session response populates UI and enables selectors.

        Validates: Requirements 1.1, 2.1, 5.1, 5.2
        """
        available_models = [
            {"modelId": "anthropic.claude-sonnet-4-20250514", "name": "Claude Sonnet"},
            {"modelId": "anthropic.claude-opus-4-20250514", "name": "Claude Opus"},
        ]
        available_modes = [
            {"id": "Developer", "name": "Developer"},
            {"id": "kiro_default", "name": "Kiro Default"},
        ]

        pref_mock_process_manager.read_message.side_effect = [
            # Initialize response
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            # Session/new response with models and modes
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "sessionId": "sess-pref-001",
                    "models": {
                        "currentModelId": "auto",
                        "availableModels": available_models,
                    },
                    "modes": {
                        "currentModeId": "Developer",
                        "availableModes": available_modes,
                    },
                },
            },
        ]

        await pref_controller.start()

        # Verify UI populate_models and populate_modes are called with correct data
        pref_mock_ui.populate_models.assert_called_once_with(available_models)
        pref_mock_ui.populate_modes.assert_called_once_with(available_modes)

        # Verify selectors are enabled after successful startup
        enable_calls = pref_mock_ui.set_selectors_enabled.call_args_list
        # First call disables (at start), last call enables (on success)
        assert enable_calls[0].args[0] is False
        assert enable_calls[-1].args[0] is True

        # Verify no errors shown
        pref_mock_ui.append_error.assert_not_called()

    async def test_model_selection_change_success_saves_preference(
        self, pref_controller, pref_mock_process_manager, pref_mock_ui, temp_prefs_file
    ):
        """Selection change → ACP request → success → preference saved.

        Validates: Requirements 4.1, 3.1
        """
        # Setup: complete startup first
        pref_mock_process_manager.read_message.side_effect = [
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "sessionId": "sess-pref-002",
                    "models": {
                        "currentModelId": "auto",
                        "availableModels": [
                            {
                                "modelId": "anthropic.claude-sonnet-4-20250514",
                                "name": "Claude Sonnet",
                            },
                        ],
                    },
                    "modes": {
                        "currentModeId": "Developer",
                        "availableModes": [
                            {"id": "Developer", "name": "Developer"},
                        ],
                    },
                },
            },
        ]
        await pref_controller.start()

        # Now simulate model change with success response
        new_model_id = "anthropic.claude-sonnet-4-20250514"
        pref_mock_process_manager.read_message.side_effect = [
            # set_model success response
            {"jsonrpc": "2.0", "id": 2, "result": {}},
        ]

        await pref_controller.on_model_changed(new_model_id)

        # Verify preferences file is updated with new model_id
        with open(temp_prefs_file) as f:
            saved_prefs = json.load(f)
        assert saved_prefs["model_id"] == new_model_id

        # Verify no error shown
        pref_mock_ui.append_error.assert_not_called()

    async def test_model_selection_change_error_reverts_selector(
        self, pref_controller, pref_mock_process_manager, pref_mock_ui, temp_prefs_file
    ):
        """Selection change → ACP request → error → selector reverted.

        Validates: Requirements 4.4
        """
        # Setup: complete startup first
        pref_mock_process_manager.read_message.side_effect = [
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "sessionId": "sess-pref-003",
                    "models": {
                        "currentModelId": "auto",
                        "availableModels": [
                            {
                                "modelId": "anthropic.claude-sonnet-4-20250514",
                                "name": "Claude Sonnet",
                            },
                        ],
                    },
                    "modes": {
                        "currentModeId": "Developer",
                        "availableModes": [
                            {"id": "Developer", "name": "Developer"},
                        ],
                    },
                },
            },
        ]
        await pref_controller.start()

        # Clear mock call history from startup
        pref_mock_ui.set_selected_model.reset_mock()
        pref_mock_ui.append_error.reset_mock()

        # Now simulate model change with error response
        pref_mock_process_manager.read_message.side_effect = [
            # set_model error response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": -32000, "message": "Model not available"},
            },
        ]

        await pref_controller.on_model_changed("anthropic.claude-sonnet-4-20250514")

        # Verify UI selector is reverted to previous value ("auto")
        pref_mock_ui.set_selected_model.assert_called_with("auto")

        # Verify error is shown
        pref_mock_ui.append_error.assert_called_once_with("Model not available")

    async def test_startup_with_existing_preferences_restores_selections(
        self, pref_mock_process_manager, pref_mock_ui, tmp_path
    ):
        """Startup with existing preferences.json → preferences restored and ACP requests sent.

        Validates: Requirements 3.3, 4.3
        """
        # Write a preferences.json file with specific model_id and mode_id
        prefs_file = str(tmp_path / "preferences.json")
        saved_prefs = {"model_id": "anthropic.claude-opus-4-20250514", "mode_id": "kiro_default"}
        with open(prefs_file, "w") as f:
            json.dump(saved_prefs, f)

        # Create controller with real PreferencesManager pointing to that file
        prefs_manager = PreferencesManager(prefs_file)
        acp = ACPClient(pref_mock_process_manager)
        controller = ChatController(pref_mock_ui, acp, pref_mock_process_manager, prefs_manager)

        # Mock create_session to return models/modes that include the saved IDs
        available_models = [
            {"modelId": "anthropic.claude-sonnet-4-20250514", "name": "Claude Sonnet"},
            {"modelId": "anthropic.claude-opus-4-20250514", "name": "Claude Opus"},
        ]
        available_modes = [
            {"id": "Developer", "name": "Developer"},
            {"id": "kiro_default", "name": "Kiro Default"},
        ]

        pref_mock_process_manager.read_message.side_effect = [
            # Initialize response
            {"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": 1}},
            # Session/new response
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "sessionId": "sess-pref-004",
                    "models": {
                        "currentModelId": "auto",
                        "availableModels": available_models,
                    },
                    "modes": {
                        "currentModeId": "Developer",
                        "availableModes": available_modes,
                    },
                },
            },
            # set_model response (for restored non-default model)
            {"jsonrpc": "2.0", "id": 2, "result": {}},
            # set_mode response (for restored non-default mode)
            {"jsonrpc": "2.0", "id": 3, "result": {}},
        ]

        await controller.start()

        # Verify set_model ACP request was sent with the saved model_id
        write_calls = pref_mock_process_manager.write_message.call_args_list
        # Find the set_model request (should be after init + session/new)
        set_model_msg = write_calls[2][0][0]
        assert set_model_msg["method"] == "session/set_model"
        assert set_model_msg["params"]["modelId"] == "anthropic.claude-opus-4-20250514"
        assert set_model_msg["params"]["sessionId"] == "sess-pref-004"

        # Find the set_mode request
        set_mode_msg = write_calls[3][0][0]
        assert set_mode_msg["method"] == "session/set_mode"
        assert set_mode_msg["params"]["modeId"] == "kiro_default"
        assert set_mode_msg["params"]["sessionId"] == "sess-pref-004"

        # Verify UI selectors are set to the saved values
        pref_mock_ui.set_selected_model.assert_called_with("anthropic.claude-opus-4-20250514")
        pref_mock_ui.set_selected_mode.assert_called_with("kiro_default")

        # Verify no errors shown
        pref_mock_ui.append_error.assert_not_called()
