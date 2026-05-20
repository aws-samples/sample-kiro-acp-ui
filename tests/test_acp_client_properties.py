"""Property-based tests for ACPClient.

# Feature: model-agent-preferences, Property 3: Selection sends correct ACP request
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kiro_acp_chat_client.acp_client import ACPClient
from kiro_acp_chat_client.process_manager import ProcessManager

# Strategy for generating non-empty string IDs (session IDs, model IDs, mode IDs)
id_strings = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
)


def _create_client_with_mock():
    """Create an ACPClient with a mocked ProcessManager that returns valid responses."""
    pm = MagicMock(spec=ProcessManager)
    pm.write_message = AsyncMock()
    pm.read_message = AsyncMock()
    client = ACPClient(pm)
    return client, pm


# **Validates: Requirements 1.3, 2.3, 4.1, 4.2**
@settings(max_examples=100)
@given(session_id=id_strings, model_id=id_strings)
@pytest.mark.asyncio
async def test_set_model_sends_correct_jsonrpc_request(session_id, model_id):
    """Property 3: Selection sends correct ACP request (set_model variant).

    For any session_id and model_id strings, calling set_model SHALL produce
    a JSON-RPC request with:
    - "jsonrpc": "2.0"
    - "method": "session/set_model"
    - "params": {"sessionId": <session_id>, "modelId": <model_id>}

    # Feature: model-agent-preferences, Property 3: Selection sends correct ACP request
    """
    client, pm = _create_client_with_mock()

    # Mock read_message to return a valid response matching the request id
    pm.read_message.return_value = {
        "jsonrpc": "2.0",
        "id": 0,
        "result": {},
    }

    await client.set_model(session_id, model_id)

    # Verify write_message was called exactly once
    pm.write_message.assert_called_once()
    request = pm.write_message.call_args[0][0]

    # Verify JSON-RPC structure
    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "session/set_model"
    assert "id" in request
    assert isinstance(request["id"], int)
    assert request["params"] == {
        "sessionId": session_id,
        "modelId": model_id,
    }


# **Validates: Requirements 1.3, 2.3, 4.1, 4.2**
@settings(max_examples=100)
@given(session_id=id_strings, mode_id=id_strings)
@pytest.mark.asyncio
async def test_set_mode_sends_correct_jsonrpc_request(session_id, mode_id):
    """Property 3: Selection sends correct ACP request (set_mode variant).

    For any session_id and mode_id strings, calling set_mode SHALL produce
    a JSON-RPC request with:
    - "jsonrpc": "2.0"
    - "method": "session/set_mode"
    - "params": {"sessionId": <session_id>, "modeId": <mode_id>}

    # Feature: model-agent-preferences, Property 3: Selection sends correct ACP request
    """
    client, pm = _create_client_with_mock()

    # Mock read_message to return a valid response matching the request id
    pm.read_message.return_value = {
        "jsonrpc": "2.0",
        "id": 0,
        "result": {},
    }

    await client.set_mode(session_id, mode_id)

    # Verify write_message was called exactly once
    pm.write_message.assert_called_once()
    request = pm.write_message.call_args[0][0]

    # Verify JSON-RPC structure
    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "session/set_mode"
    assert "id" in request
    assert isinstance(request["id"], int)
    assert request["params"] == {
        "sessionId": session_id,
        "modeId": mode_id,
    }
