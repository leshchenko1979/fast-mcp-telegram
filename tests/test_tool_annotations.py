"""Every registered tool states readOnlyHint, destructiveHint and openWorldHint.

The MCP spec defaults an absent ``destructiveHint`` to ``true`` and an absent
``readOnlyHint`` to ``false``. Some clients and app directories (OpenAI's app
review among them) check each hint on its own, so a read-only tool that leaves
``destructiveHint`` unset looks destructive to them. These tests pin the
hints on the REGISTERED tools, over the real FastMCP registration + Client path.
"""

import asyncio

from fastmcp import Client, FastMCP

from src.server_components.tools_register import register_tools

READ_ONLY = {"search_messages_globally", "get_messages", "find_chats", "get_chat_info"}
WRITES = {"send_message", "edit_message", "send_message_to_phone", "invoke_mtproto"}


async def _list_tools():
    temp_mcp = FastMCP("tool annotations test")
    register_tools(temp_mcp)
    async with Client(temp_mcp) as client:
        return await client.list_tools()


def test_every_tool_sets_all_three_hints_explicitly():
    tools = asyncio.run(_list_tools())
    assert {t.name for t in tools} == READ_ONLY | WRITES
    for tool in tools:
        ann = tool.annotations
        assert ann is not None, tool.name
        assert ann.title, tool.name
        assert isinstance(ann.readOnlyHint, bool), tool.name
        assert isinstance(ann.destructiveHint, bool), tool.name
        assert ann.openWorldHint is True, tool.name


def test_hints_match_what_each_tool_does():
    tools = {t.name: t.annotations for t in asyncio.run(_list_tools())}
    for name in READ_ONLY:
        assert tools[name].readOnlyHint is True, name
        assert tools[name].destructiveHint is False, name
    for name in WRITES:
        assert tools[name].readOnlyHint is False, name
        assert tools[name].destructiveHint is True, name
