"""Messages module - split into multiple submodules for better organization.

Submodules:
- core: Formatting detection utilities
- security: URL and file validation
- file_handling: File download and processing
- sending: Message sending functionality
- editing: Message editing functionality
- reading: Message reading functionality
- phone: Phone number message sending
"""

from src.client.connection import get_connected_client
from src.tools.messages.core import _normalize_parse_mode, detect_message_formatting
from src.tools.messages.editing import edit_message_impl
from src.tools.messages.file_handling import _calculate_file_count
from src.tools.messages.phone import send_message_to_phone_impl
from src.tools.messages.reading import read_messages_by_ids
from src.tools.messages.security import _validate_file_paths
from src.tools.messages.sending import (
    _extract_send_message_params,
    _send_files_to_entity,
    _send_message_or_files,
    send_message_impl,
)
from src.utils.discussion import get_post_discussion_info
from src.utils.entity import get_entity_by_id

__all__ = [
    # Internal functions used by tests
    "_extract_send_message_params",
    "_normalize_parse_mode",
    "_send_files_to_entity",
    "_send_message_or_files",
    "_validate_file_paths",
    "detect_message_formatting",
    # Public API
    "edit_message_impl",
    # Functions commonly patched in tests
    "get_connected_client",
    "get_entity_by_id",
    "get_post_discussion_info",
    "read_messages_by_ids",
    "send_message_impl",
    "send_message_to_phone_impl",
]
