"""Property-based tests for JSON-RPC message serialization.

# Feature: kiro-acp-chat-client, Property 1: JSON-RPC message serialization round-trip
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from kiro_acp_chat_client.models import (
    JsonRpcRequest,
    from_json_line,
    to_json_line,
)


# Strategy for generating JSON-serializable primitive values
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=50),
)

# Strategy for generating JSON-serializable values (with nesting)
json_values = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=5),
    ),
    max_leaves=10,
)

# Strategy for generating valid params dicts
json_params = st.dictionaries(
    st.text(min_size=1, max_size=30),
    json_values,
    max_size=5,
)

# Strategy for generating valid JSON-RPC method names
json_rpc_methods = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        whitelist_characters="/._-",
    ),
    min_size=1,
    max_size=50,
)

# Strategy for generating valid JSON-RPC request IDs
json_rpc_ids = st.integers(min_value=0, max_value=2**31 - 1)


# **Validates: Requirements 4.2, 2.1**
@settings(max_examples=200)
@given(
    method=json_rpc_methods,
    params=json_params,
    req_id=json_rpc_ids,
)
def test_jsonrpc_request_serialization_round_trip(method, params, req_id):
    """Property 1: JSON-RPC message serialization round-trip.

    For any valid JSON-RPC request (with method, params, and id),
    serializing it to a newline-delimited JSON string and then parsing
    that string back produces an equivalent message object with identical
    method, params, and id values.

    # Feature: kiro-acp-chat-client, Property 1: JSON-RPC message serialization round-trip
    """
    original = JsonRpcRequest(id=req_id, method=method, params=params)

    serialized = to_json_line(original)

    # Verify newline-delimited format: exactly one trailing newline, no embedded newlines
    assert serialized.endswith("\n")
    assert "\n" not in serialized[:-1]

    restored = from_json_line(serialized)

    # Verify round-trip produces equivalent message
    assert isinstance(restored, JsonRpcRequest)
    assert restored.id == original.id
    assert restored.method == original.method
    assert restored.params == original.params
    assert restored.jsonrpc == "2.0"
