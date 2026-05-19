"""ACP protocol client for communicating with kiro-cli acp."""

import logging

from kiro_acp_chat_client.process_manager import ProcessManager

logger = logging.getLogger(__name__)


class ACPClient:
    """ACP protocol client for communicating with kiro-cli acp.

    Implements the Agent Client Protocol on top of the ProcessManager,
    handling initialization, session management, prompt sending, and
    response reading via JSON-RPC 2.0 messages.
    """

    def __init__(self, process_manager: ProcessManager) -> None:
        self._pm = process_manager
        self._request_id = 0

    def _next_id(self) -> int:
        """Return the next sequential request ID."""
        current = self._request_id
        self._request_id += 1
        return current

    async def _read_response(self, request_id: int) -> dict:
        """Read messages until we get the response matching request_id.

        Skips over notifications (messages without an 'id' field or with
        a different id). This handles the fact that kiro-cli sends many
        notifications between a request and its response.
        """
        while True:
            message = await self._pm.read_message()
            # A response has an 'id' field matching our request
            if "id" in message and message["id"] == request_id:
                return message
            # Skip notifications and unrelated messages
            method = message.get("method", "")
            logger.debug("Skipping notification during handshake: %s", method)

    async def initialize(self) -> dict:
        """Send initialize request and return agent capabilities.

        Sends a JSON-RPC initialize request with client capabilities
        and client info. Returns the agent's capability response result.
        """
        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
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
        await self._pm.write_message(request)
        return await self._read_response(req_id)

    async def create_session(self, cwd: str) -> dict:
        """Create a new ACP session.

        Args:
            cwd: The current working directory for the session.

        Returns:
            The full result dict from the session/new response,
            containing sessionId, models, and modes.
        """
        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "session/new",
            "params": {
                "cwd": cwd,
                "mcpServers": [],
            },
        }
        await self._pm.write_message(request)
        response = await self._read_response(req_id)
        result = response.get("result") or {}
        session_id = result.get("sessionId", "")
        logger.info("Session created: %s", session_id)
        return result

    async def set_model(self, session_id: str, model_id: str) -> dict:
        """Send session/set_model request.

        Args:
            session_id: The active session ID.
            model_id: The model ID to set (e.g., "auto" or a specific model ID).

        Returns:
            The JSON-RPC response dict. Caller checks for 'error' key.
        """
        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "session/set_model",
            "params": {
                "sessionId": session_id,
                "modelId": model_id,
            },
        }
        await self._pm.write_message(request)
        return await self._read_response(req_id)

    async def set_mode(self, session_id: str, mode_id: str) -> dict:
        """Send session/set_mode request.

        Args:
            session_id: The active session ID.
            mode_id: The mode ID to set.

        Returns:
            The JSON-RPC response dict. Caller checks for 'error' key.
        """
        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "session/set_mode",
            "params": {
                "sessionId": session_id,
                "modeId": mode_id,
            },
        }
        await self._pm.write_message(request)
        return await self._read_response(req_id)

    async def send_prompt(self, session_id: str, text: str) -> None:
        """Send a user prompt to the agent.

        This is a request that will receive streaming session/update
        notifications followed by a final session/prompt response.

        Args:
            session_id: The active session ID.
            text: The user's message text.
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "session/prompt",
            "params": {
                "sessionId": session_id,
                "prompt": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            },
        }
        await self._pm.write_message(request)

    async def read_update(self) -> dict:
        """Read the next message from the agent.

        Returns either a session/update notification or the
        session/prompt response (indicating turn complete).
        """
        return await self._pm.read_message()

    async def cancel(self, session_id: str) -> None:
        """Send session/cancel notification to interrupt processing.

        This is a notification (no id field), so no response is expected.

        Args:
            session_id: The session to cancel.
        """
        notification = {
            "jsonrpc": "2.0",
            "method": "session/cancel",
            "params": {
                "sessionId": session_id,
            },
        }
        await self._pm.write_message(notification)

    async def respond_to_request(self, request_id: int, result: dict) -> None:
        """Send a JSON-RPC response to a request from the agent.

        Used for responding to session/request_permission and similar requests.

        Args:
            request_id: The id from the agent's request.
            result: The result payload to send back.
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
        await self._pm.write_message(response)
