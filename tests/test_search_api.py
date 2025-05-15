import asyncio
import pytest
from fastmcp import Client
import json

@pytest.mark.asyncio
async def test_search_messages_api_returns_valid_json():
    query = "склады"
    limit = 3
    async with Client("http://localhost:8000/sse") as client:
        result = await client.call_tool("search_messages", {"query": query, "limit": limit})
        # Проверяем, что результат — список
        assert isinstance(result, list), f"Result is not a list: {type(result)}"
        # Проверяем, что каждый элемент — словарь с нужными ключами и сериализуем в JSON
        for msg in result:
            assert isinstance(msg, dict), f"Message is not a dict: {type(msg)}"
            # Проверяем сериализацию
            try:
                json_str = json.dumps(msg, ensure_ascii=False)
            except Exception as e:
                pytest.fail(f"Message is not JSON serializable: {e}\n{msg}")
            # Проверяем ключи
            for key in ["id", "date", "chat_id", "chat_name", "text"]:
                assert key in msg, f"Key '{key}' missing in message: {msg}"
            # Проверяем, что date — строка
            assert isinstance(msg["date"], str), f"date is not a string: {msg['date']}"
            # Проверяем, что text — строка или None
            assert msg["text"] is None or isinstance(msg["text"], str), f"text is not a string or None: {msg['text']}"
