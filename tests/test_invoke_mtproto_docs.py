"""Documentation contract for invoke_mtproto (issue #155).

`messages.GetHistory` cannot address a forum topic — no `thread_id`, no
`top_msg_id` in its schema, and `channels.GetHistory` does not exist — so the
remedy is a pointer to the route that works, not a code fix. A pointer only
helps if it reaches the caller, and the caller reads the REGISTERED tool
description, not the source tree.

These tests pin that: the guidance must be present in the registered schema,
and the reference doc must carry the same route. Without them the description
can silently drop the pointer in a refactor and the next caller rediscovers
the limitation by stack trace, which is the defect this issue is about.
"""

import asyncio

from fastmcp import Client, FastMCP

from src.server_components.tools_register import register_tools

DOCS_PATH = "docs/Tools-Reference.md"


def _make_server() -> FastMCP:
    """A temp server carrying the real tool registration."""
    temp_mcp = FastMCP("invoke_mtproto description test")
    register_tools(temp_mcp)
    return temp_mcp


async def _invoke_mtproto_description() -> str:
    async with Client(_make_server()) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "invoke_mtproto")
        return tool.description or ""


def test_registered_description_documents_the_topic_route():
    """The registered description must name messages.Search + top_msg_id."""
    description = asyncio.run(_invoke_mtproto_description())

    assert "top_msg_id" in description, (
        "invoke_mtproto description lost the forum-topic route; a caller reading "
        "only the schema cannot discover that messages.GetHistory cannot address "
        "a topic"
    )
    assert "messages.Search" in description
    # The high-level alternative is named too, so the caller need not drop to raw.
    assert "reply_to_id" in description


def test_registered_description_documents_the_bare_id_refusal():
    """The refusal is a behaviour change; the description must announce it."""
    description = asyncio.run(_invoke_mtproto_description())

    assert "channels.GetMessages" in description
    assert "messages.GetHistory" in description


def test_registered_description_documents_include_sensitive():
    """The PII opt-in must be discoverable from the schema."""
    description = asyncio.run(_invoke_mtproto_description())

    assert "include_sensitive" in description
    assert "phone" in description


def test_reference_doc_carries_the_topic_route():
    """The reference doc must carry the same route as the schema.

    Guards against the two surfaces drifting: a caller who reads only the doc
    should reach the same call shape as one who reads only the schema.
    """
    with open(DOCS_PATH) as fh:
        docs = fh.read()

    assert "top_msg_id" in docs
    assert "InputMessagesFilterEmpty" in docs
    # The doc's delete example must not advertise a call the guard now refuses.
    assert '"messages.DeleteMessages"' not in docs, (
        "docs still show messages.DeleteMessages with a bare id, which the "
        "unbound-id guard refuses; point at channels.DeleteMessages instead"
    )
