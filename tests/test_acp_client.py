"""Unit tests for the ACPClient class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from kiro_acp_chat_client.acp_client import ACPClient
from kiro_acp_chat_client.process_manager import ProcessManager


@pytest.fixture
def mock_pm():
    """Create a mock ProcessManager with async methods."""
    pm = MagicMock(spec=ProcessManager)
    pm.write_message = AsyncMock()
    pm.read_message = AsyncMock()
    return pm


@pytest.fixture
def client(mock_pm):
    """Create an ACPClient with a mocked ProcessManager."""
    return ACPClient(mock_pm)


class TestInitialize:
    async def test_sends_correct_initialize_request(self, client, mock_pm):
        """Test that initialize sends the correct JSON-RPC structure."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {"agentCapabilities": {"streaming": True}},
        }

        await client.initialize()

        mock_pm.write_message.assert_called_once_with(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": 1,
                    "clientCapabilities": {},
                    "clientInfo": {
                        "name": "kiro-acp-chat-client",
                        "title": "Kiro ACP Chat",
                        "version": "0.1.0",
                    },
                },
            }
        )

    async def test_returns_agent_response(self, client, mock_pm):
        """Test that initialize returns the full response from the agent."""
        expected_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {"agentCapabilities": {"streaming": True}},
        }
        mock_pm.read_message.return_value = expected_response

        result = await client.initialize()

        assert result == expected_response


class TestCreateSession:
    async def test_sends_correct_session_new_request(self, client, mock_pm):
        """Test that create_session sends the correct JSON-RPC structure."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"sessionId": "sess_abc123"},
        }

        # Call initialize first to consume id=0
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {},
        }
        await client.initialize()
        mock_pm.write_message.reset_mock()

        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"sessionId": "sess_abc123"},
        }

        await client.create_session("/home/user/project")

        mock_pm.write_message.assert_called_once_with(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "session/new",
                "params": {
                    "cwd": "/home/user/project",
                    "mcpServers": [],
                },
            }
        )

    async def test_returns_full_result_dict(self, client, mock_pm):
        """Test that create_session returns the full result dict from the response."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {
                "sessionId": "sess_xyz789",
                "models": {
                    "currentModelId": "auto",
                    "availableModels": [{"modelId": "model-1", "name": "Model One"}],
                },
                "modes": {
                    "currentModeId": "kiro_default",
                    "availableModes": [{"id": "Developer", "name": "Developer"}],
                },
            },
        }

        result = await client.create_session("/tmp")

        assert result == {
            "sessionId": "sess_xyz789",
            "models": {
                "currentModelId": "auto",
                "availableModels": [{"modelId": "model-1", "name": "Model One"}],
            },
            "modes": {
                "currentModeId": "kiro_default",
                "availableModes": [{"id": "Developer", "name": "Developer"}],
            },
        }

    async def test_returns_empty_dict_on_missing_session_id(self, client, mock_pm):
        """Test graceful handling when response lacks sessionId."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {},
        }

        result = await client.create_session("/tmp")

        assert result == {}


class TestSetModel:
    async def test_sends_correct_set_model_request(self, client, mock_pm):
        """Test that set_model sends the correct JSON-RPC structure."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {"sessionId": "sess_abc123"},
        }

        await client.set_model("sess_abc123", "anthropic.claude-sonnet-4-20250514")

        mock_pm.write_message.assert_called_once_with(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "session/set_model",
                "params": {
                    "sessionId": "sess_abc123",
                    "modelId": "anthropic.claude-sonnet-4-20250514",
                },
            }
        )

    async def test_returns_full_response_dict(self, client, mock_pm):
        """Test that set_model returns the full JSON-RPC response dict."""
        expected_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {"sessionId": "sess_abc123"},
        }
        mock_pm.read_message.return_value = expected_response

        result = await client.set_model("sess_abc123", "model-1")

        assert result == expected_response

    async def test_returns_error_response(self, client, mock_pm):
        """Test that set_model returns error response when server returns error."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "error": {"code": -32602, "message": "Invalid model ID"},
        }
        mock_pm.read_message.return_value = error_response

        result = await client.set_model("sess_abc123", "invalid-model")

        assert result == error_response
        assert "error" in result
        assert result["error"]["message"] == "Invalid model ID"


class TestSetMode:
    async def test_sends_correct_set_mode_request(self, client, mock_pm):
        """Test that set_mode sends the correct JSON-RPC structure."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {"sessionId": "sess_abc123"},
        }

        await client.set_mode("sess_abc123", "Developer")

        mock_pm.write_message.assert_called_once_with(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "session/set_mode",
                "params": {
                    "sessionId": "sess_abc123",
                    "modeId": "Developer",
                },
            }
        )

    async def test_returns_full_response_dict(self, client, mock_pm):
        """Test that set_mode returns the full JSON-RPC response dict."""
        expected_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {"sessionId": "sess_abc123"},
        }
        mock_pm.read_message.return_value = expected_response

        result = await client.set_mode("sess_abc123", "Developer")

        assert result == expected_response

    async def test_returns_error_response(self, client, mock_pm):
        """Test that set_mode returns error response when server returns error."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "error": {"code": -32602, "message": "Invalid mode ID"},
        }
        mock_pm.read_message.return_value = error_response

        result = await client.set_mode("sess_abc123", "invalid-mode")

        assert result == error_response
        assert "error" in result
        assert result["error"]["message"] == "Invalid mode ID"


class TestSendPrompt:
    async def test_sends_correct_prompt_request(self, client, mock_pm):
        """Test that send_prompt constructs the correct message format."""
        await client.send_prompt("sess_abc123", "Hello, how are you?")

        mock_pm.write_message.assert_called_once_with(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "session/prompt",
                "params": {
                    "sessionId": "sess_abc123",
                    "prompt": [
                        {
                            "type": "text",
                            "text": "Hello, how are you?",
                        }
                    ],
                },
            }
        )

    async def test_does_not_read_response(self, client, mock_pm):
        """Test that send_prompt does not wait for a response (streaming)."""
        await client.send_prompt("sess_abc", "test")

        mock_pm.read_message.assert_not_called()


class TestReadUpdate:
    async def test_returns_session_update_notification(self, client, mock_pm):
        """Test that read_update returns session/update notifications."""
        notification = {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_abc123",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "Hello!"},
                },
            },
        }
        mock_pm.read_message.return_value = notification

        result = await client.read_update()

        assert result == notification

    async def test_returns_session_prompt_response(self, client, mock_pm):
        """Test that read_update returns the final session/prompt response."""
        response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"sessionId": "sess_abc123"},
        }
        mock_pm.read_message.return_value = response

        result = await client.read_update()

        assert result == response


class TestCancel:
    async def test_sends_cancel_notification_without_id(self, client, mock_pm):
        """Test that cancel sends a notification (no id field)."""
        await client.cancel("sess_abc123")

        mock_pm.write_message.assert_called_once_with(
            {
                "jsonrpc": "2.0",
                "method": "session/cancel",
                "params": {
                    "sessionId": "sess_abc123",
                },
            }
        )

    async def test_cancel_does_not_read_response(self, client, mock_pm):
        """Test that cancel does not wait for a response (it's a notification)."""
        await client.cancel("sess_abc")

        mock_pm.read_message.assert_not_called()


class TestErrorHandlingMalformedResponses:
    async def test_initialize_with_missing_result_key(self, client, mock_pm):
        """Test initialize handles response missing 'result' key."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
        }

        result = await client.initialize()

        # initialize returns the raw response dict; caller handles missing keys
        assert result == {"jsonrpc": "2.0", "id": 0}

    async def test_initialize_with_error_response(self, client, mock_pm):
        """Test initialize handles a JSON-RPC error response."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 0,
            "error": {"code": -32600, "message": "Invalid Request"},
        }
        mock_pm.read_message.return_value = error_response

        result = await client.initialize()

        assert result == error_response
        assert "error" in result

    async def test_create_session_with_missing_result(self, client, mock_pm):
        """Test create_session returns empty dict when result is missing."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
        }

        result = await client.create_session("/tmp")

        assert result == {}

    async def test_create_session_with_null_result(self, client, mock_pm):
        """Test create_session returns empty dict when result is None."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": None,
        }

        result = await client.create_session("/tmp")

        assert result == {}

    async def test_create_session_with_error_response(self, client, mock_pm):
        """Test create_session returns empty dict on error response."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "error": {"code": -32601, "message": "Method not found"},
        }

        result = await client.create_session("/tmp")

        assert result == {}

    async def test_read_update_with_empty_dict(self, client, mock_pm):
        """Test read_update handles an empty dict response."""
        mock_pm.read_message.return_value = {}

        result = await client.read_update()

        assert result == {}

    async def test_read_update_with_unexpected_method(self, client, mock_pm):
        """Test read_update returns messages with unexpected methods."""
        unexpected = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "params": {"data": "something"},
        }
        mock_pm.read_message.return_value = unexpected

        result = await client.read_update()

        assert result == unexpected

    async def test_read_update_propagates_process_terminated_error(self, client, mock_pm):
        """Test read_update propagates ProcessTerminatedError from ProcessManager."""
        from kiro_acp_chat_client.process_manager import ProcessTerminatedError

        mock_pm.read_message.side_effect = ProcessTerminatedError("Process exited")

        with pytest.raises(ProcessTerminatedError):
            await client.read_update()

    async def test_send_prompt_propagates_write_error(self, client, mock_pm):
        """Test send_prompt propagates errors from write_message."""
        mock_pm.write_message.side_effect = OSError("Broken pipe")

        with pytest.raises(OSError, match="Broken pipe"):
            await client.send_prompt("sess_abc", "hello")


class TestRequestIdCounter:
    async def test_ids_increment_sequentially(self, client, mock_pm):
        """Test that request IDs increment with each request."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {},
        }

        # First request: id=0
        await client.initialize()
        first_call = mock_pm.write_message.call_args_list[0][0][0]
        assert first_call["id"] == 0

        # Second request: id=1
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"sessionId": "sess_1"},
        }
        await client.create_session("/tmp")
        second_call = mock_pm.write_message.call_args_list[1][0][0]
        assert second_call["id"] == 1

        # Third request: id=2
        await client.send_prompt("sess_1", "hi")
        third_call = mock_pm.write_message.call_args_list[2][0][0]
        assert third_call["id"] == 2

    async def test_cancel_does_not_consume_id(self, client, mock_pm):
        """Test that cancel (notification) does not increment the request ID."""
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 0,
            "result": {},
        }

        # First request: id=0
        await client.initialize()

        # Cancel is a notification - no id consumed
        await client.cancel("sess_1")
        cancel_msg = mock_pm.write_message.call_args_list[1][0][0]
        assert "id" not in cancel_msg

        # Next request should be id=1
        mock_pm.read_message.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"sessionId": "sess_1"},
        }
        await client.create_session("/tmp")
        next_call = mock_pm.write_message.call_args_list[2][0][0]
        assert next_call["id"] == 1
