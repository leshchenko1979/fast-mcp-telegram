"""Regression tests for the REGISTERED get_chat_info signature (issue #150).

The defect: the registered ``get_chat_info`` tool omitted ``common_chats_limit``
while the tool description advertised it and ``get_chat_info_impl`` accepted it.
Any client that filled the documented default (10) therefore failed Pydantic
validation with ``Unexpected keyword argument`` before the handler ever ran.

``tests/test_common_chats.py`` cannot catch this class of bug: it calls
``get_chat_info_impl`` directly (lines 46, 86, 112) and never passes through the
registered tool, so a gap between the impl signature and the registered
signature is invisible to it.

These tests exercise the REGISTERED tool over the real FastMCP registration +
Client path. The explicit-non-default test is the load-bearing one: if the
parameter is missing from the registered signature, or if the client silently
drops an unknown argument, the impl receives the default (10) instead of the
value the caller asked for.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client, FastMCP

from src.server_components.tools_register import register_tools

IMPL_PATCH_TARGET = "src.server_components.tools_register.get_chat_info_impl"


def _make_server() -> FastMCP:
    """A temp server carrying the real tool registration."""
    temp_mcp = FastMCP("get_chat_info signature test")
    register_tools(temp_mcp)
    return temp_mcp


async def _get_chat_info_schema() -> dict:
    async with Client(_make_server()) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_chat_info")
        return tool.inputSchema


def test_registered_schema_advertises_common_chats_limit():
    """The registered signature must expose common_chats_limit, defaulting to 10."""
    schema = asyncio.run(_get_chat_info_schema())

    assert schema["type"] == "object"
    properties = schema["properties"]
    assert "common_chats_limit" in properties, (
        "get_chat_info registered signature omits common_chats_limit: a client "
        "filling the documented default would fail validation (issue #150)"
    )
    assert properties["common_chats_limit"]["default"] == 10


@pytest.mark.asyncio
async def test_registered_tool_accepts_documented_default():
    """Calling the REGISTERED tool with the documented default (10) must succeed."""
    impl = AsyncMock(return_value={"id": 1001, "type": "private"})

    with patch(IMPL_PATCH_TARGET, new=impl):
        async with Client(_make_server()) as client:
            result = await client.call_tool(
                "get_chat_info", {"chat_id": "1001", "common_chats_limit": 10}
            )

    # The registered tool declares -> ChatInfoResult, so FastMCP coerces the
    # impl's dict into that model; structured_content carries the raw payload.
    assert result.structured_content == {"id": 1001, "type": "private"}
    assert impl.await_args.kwargs["common_chats_limit"] == 10
    assert impl.await_args.kwargs["topics_limit"] == 20


@pytest.mark.asyncio
async def test_registered_tool_forwards_explicit_non_default_value():
    """An explicit non-default value must survive the registration boundary.

    If the registered signature omitted the parameter, the impl would receive
    the signature default (10) rather than the 3 the caller asked for.
    """
    impl = AsyncMock(return_value={"id": 1001, "type": "private"})

    with patch(IMPL_PATCH_TARGET, new=impl):
        async with Client(_make_server()) as client:
            await client.call_tool(
                "get_chat_info", {"chat_id": "1001", "common_chats_limit": 3}
            )

    assert impl.await_args.kwargs["common_chats_limit"] == 3
