"""Unit tests for ChatController._stream_response() method."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kiro_acp_chat_client.controller import ChatController
from kiro_acp_chat_client.preferences_manager import Preferences
from kiro_acp_chat_client.process_manager import ProcessTerminatedError


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
    ui.ask_permission = MagicMock(return_value="option-1")
    return ui


@pytest.fixture
def mock_acp_client():
    """Create a mock ACPClient."""
    client = AsyncMock()
    client.initialize = AsyncMock(return_value={"result": {}})
    client.create_session = AsyncMock(return_value={"sessionId": "session-123"})
    client.send_prompt = AsyncMock()
    client.read_update = AsyncMock()
    client.respond_to_request = AsyncMock()
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


class TestStreamResponse:
    """Tests for ChatController._stream_response()."""

    async def test_accumulates_multiple_text_chunks(self, controller, mock_acp_client):
        """_stream_response joins multiple text chunks into a single string."""
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
                        "content": {"type": "text", "text": "world"},
                    }
                },
            },
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "!"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        result = await controller._stream_response()

        assert result == "Hello world!"

    async def test_returns_empty_string_when_no_text_chunks(self, controller, mock_acp_client):
        """_stream_response returns empty string when no text chunks are received."""
        mock_acp_client.read_update.side_effect = [
            {"id": 2, "result": {}},
        ]

        result = await controller._stream_response()

        assert result == ""

    async def test_handles_permission_request(self, controller, mock_acp_client, mock_ui):
        """_stream_response handles session/request_permission via _handle_permission_request."""
        mock_acp_client.read_update.side_effect = [
            {
                "id": 5,
                "method": "session/request_permission",
                "params": {
                    "toolCall": {"title": "Read file", "content": []},
                    "options": [
                        {"id": "option-1", "label": "Allow"},
                        {"id": "option-2", "label": "Deny"},
                    ],
                },
            },
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "Done after permission"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        result = await controller._stream_response()

        # Permission dialog was shown
        mock_ui.ask_permission.assert_called_once()
        # Response was sent back to agent
        mock_acp_client.respond_to_request.assert_called_once_with(
            5, {"outcome": {"outcome": "selected", "optionId": "option-1"}}
        )
        # Text after permission was still accumulated
        assert result == "Done after permission"

    async def test_error_from_read_update_propagates(self, controller, mock_acp_client):
        """_stream_response propagates exceptions from read_update()."""
        mock_acp_client.read_update.side_effect = ProcessTerminatedError(
            "Connection to Kiro lost. Please restart the application."
        )

        with pytest.raises(ProcessTerminatedError, match="Connection to Kiro lost"):
            await controller._stream_response()

    async def test_error_after_partial_chunks_propagates(self, controller, mock_acp_client):
        """_stream_response propagates errors even after receiving some chunks."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "partial"},
                    }
                },
            },
            ProcessTerminatedError("Connection lost"),
        ]

        with pytest.raises(ProcessTerminatedError, match="Connection lost"):
            await controller._stream_response()

    async def test_ignores_non_text_content_types(self, controller, mock_acp_client):
        """_stream_response ignores content with non-text type."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "image", "data": "base64data"},
                    }
                },
            },
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "only text"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        result = await controller._stream_response()

        assert result == "only text"

    async def test_ignores_tool_call_updates(self, controller, mock_acp_client):
        """_stream_response ignores tool_call session updates."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "title": "read_file",
                    }
                },
            },
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

        result = await controller._stream_response()

        assert result == "response"

    async def test_ignores_unknown_agent_requests(self, controller, mock_acp_client):
        """_stream_response skips unknown request methods from the agent."""
        mock_acp_client.read_update.side_effect = [
            {
                "id": 10,
                "method": "session/unknown_method",
                "params": {},
            },
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "after unknown"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        result = await controller._stream_response()

        assert result == "after unknown"

    async def test_single_chunk_returns_correctly(self, controller, mock_acp_client):
        """_stream_response returns a single chunk without extra joining artifacts."""
        mock_acp_client.read_update.side_effect = [
            {
                "method": "session/update",
                "params": {
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "single response"},
                    }
                },
            },
            {"id": 2, "result": {}},
        ]

        result = await controller._stream_response()

        assert result == "single response"
