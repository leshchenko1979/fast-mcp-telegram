"""
Test module for message editing functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.tools.messages import edit_message


class TestEditMessage:
    """Test cases for edit_message function."""

    @pytest.mark.asyncio
    async def test_edit_message_success(self):
        """Test successful message editing."""
        # Mock client and chat entity
        mock_client = AsyncMock()
        mock_chat = MagicMock()
        mock_chat.id = 123456789
        
        # Mock edited message
        mock_edited_message = MagicMock()
        mock_edited_message.id = 12345
        mock_edited_message.date = datetime(2025, 1, 27, 12, 0, 0)
        mock_edited_message.edit_date = datetime(2025, 1, 27, 12, 5, 0)
        mock_edited_message.text = "Updated message content"
        mock_edited_message.sender = None
        
        mock_client.edit_message.return_value = mock_edited_message
        
        # Mock get_client and get_entity_by_id
        with pytest.MonkeyPatch().context() as m:
            m.setattr("src.tools.messages.get_client", AsyncMock(return_value=mock_client))
            m.setattr("src.tools.messages.get_entity_by_id", AsyncMock(return_value=mock_chat))
            m.setattr("src.tools.messages.build_entity_dict", lambda x: {"id": x.id, "type": "chat"} if x else {})
            
            # Test the function
            result = await edit_message(
                chat_id="123456789",
                message_id=12345,
                new_text="Updated message content",
                parse_mode="markdown"
            )
            
            # Verify the result
            assert result["message_id"] == 12345
            assert result["text"] == "Updated message content"
            assert result["status"] == "edited"
            assert result["edit_date"] == "2025-01-27T12:05:00"
            assert result["chat"]["id"] == 123456789
            
            # Verify the client was called correctly
            mock_client.edit_message.assert_called_once_with(
                entity=mock_chat,
                message=12345,
                text="Updated message content",
                parse_mode="markdown"
            )

    @pytest.mark.asyncio
    async def test_edit_message_chat_not_found(self):
        """Test editing message when chat is not found."""
        with pytest.MonkeyPatch().context() as m:
            m.setattr("src.tools.messages.get_client", AsyncMock())
            m.setattr("src.tools.messages.get_entity_by_id", AsyncMock(return_value=None))
            
            # Test that it raises ValueError
            with pytest.raises(ValueError, match="Cannot find any entity corresponding to"):
                await edit_message(
                    chat_id="nonexistent_chat",
                    message_id=12345,
                    new_text="Updated content"
                )

    @pytest.mark.asyncio
    async def test_edit_message_client_error(self):
        """Test editing message when client raises an error."""
        mock_client = AsyncMock()
        mock_client.edit_message.side_effect = Exception("Telegram API error")
        
        mock_chat = MagicMock()
        mock_chat.id = 123456789
        
        with pytest.MonkeyPatch().context() as m:
            m.setattr("src.tools.messages.get_client", AsyncMock(return_value=mock_client))
            m.setattr("src.tools.messages.get_entity_by_id", AsyncMock(return_value=mock_chat))
            
            # Test that it raises the exception
            with pytest.raises(Exception, match="Telegram API error"):
                await edit_message(
                    chat_id="123456789",
                    message_id=12345,
                    new_text="Updated content"
                )


if __name__ == "__main__":
    pytest.main([__file__])
