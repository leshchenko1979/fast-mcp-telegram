import asyncio
import pytest
from fastmcp import Client
import json

@pytest.mark.asyncio
async def test_generate_private_chat_links_via_server():
    chat_id = 'NF_GROUP_Industrial'  # username вместо chat_id для публичного чата
    message_ids = [1, 42, 100]
    async with Client("http://localhost:8000/sse") as client:
        result = await client.call_tool("generate_links", {"chat_id": chat_id, "message_ids": message_ids})
        assert isinstance(result, list)
        assert len(result) > 0
        data = result[0]
        if hasattr(data, 'text'):
            data = json.loads(data.text)
        if 'public_chat_link' in data:
            assert data['public_chat_link'].startswith('https://t.me/')
            assert 'message_links' in data
            assert len(data['message_links']) == len(message_ids)
            for idx, msg_id in enumerate(message_ids):
                assert data['message_links'][idx].startswith('https://t.me/')
        elif 'private_chat_link' in data:
            assert data['private_chat_link'].startswith('https://t.me/c/')
            assert 'message_links' in data
            assert len(data['message_links']) == len(message_ids)
            for idx, msg_id in enumerate(message_ids):
                assert data['message_links'][idx].startswith('https://t.me/c/')
        else:
            assert 'note' in data
            assert 'private chat links' in data['note'].lower()

@pytest.mark.asyncio
async def test_generate_private_chat_links_without_messages_via_server():
    chat_id = 'NF_GROUP_Industrial'  # username вместо chat_id для публичного чата
    async with Client("http://localhost:8000/sse") as client:
        result = await client.call_tool("generate_links", {"chat_id": chat_id, "message_ids": []})
        assert isinstance(result, list)
        assert len(result) > 0
        data = result[0]
        if hasattr(data, 'text'):
            data = json.loads(data.text)
        if 'public_chat_link' in data:
            assert data['public_chat_link'].startswith('https://t.me/')
            assert 'message_links' not in data or not data['message_links']
        elif 'private_chat_link' in data:
            assert data['private_chat_link'].startswith('https://t.me/c/')
            assert 'message_links' not in data or not data['message_links']
        else:
            assert 'note' in data
            assert 'private chat links' in data['note'].lower()
