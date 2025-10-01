import ipaddress
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import aiohttp
from loguru import logger
from telethon.tl.functions.contacts import DeleteContactsRequest, ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from src.client.connection import get_connected_client
from src.config.server_config import ServerMode, get_config
from src.tools.links import generate_telegram_links
from src.utils.entity import build_entity_dict, get_entity_by_id
from src.utils.error_handling import log_and_build_error
from src.utils.logging_utils import log_operation_start, log_operation_success
from src.utils.message_format import build_message_result, build_send_edit_result


def _validate_url_security(url: str) -> tuple[bool, str]:
    """
    Validate URL for security risks to prevent SSRF attacks.

    Returns:
        (is_safe, error_message): True if safe, False with error message if unsafe
    """
    try:
        # Handle empty or invalid URLs
        if not url or not url.strip():
            return False, "Empty URL not allowed"

        parsed = urlparse(url)
        config = get_config()

        # Check if HTTP is allowed (only for development)
        if parsed.scheme == "http" and not config.allow_http_urls:
            return (
                False,
                "HTTP URLs not allowed (use HTTPS or enable allow_http_urls for development)",
            )

        # Only allow HTTP/HTTPS
        if parsed.scheme not in ["http", "https"]:
            return False, f"Only HTTP/HTTPS URLs allowed, got: {parsed.scheme}"

        # Extract hostname/IP
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: no hostname"

        # Block localhost variants
        localhost_variants = {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "127.1",
            "127.0.1",
        }
        if hostname.lower() in localhost_variants:
            return False, f"Localhost access blocked: {hostname}"

        # Handle IPv6 localhost
        if hostname.startswith("[") and hostname.endswith("]"):
            # IPv6 address in brackets
            ipv6_addr = hostname[1:-1]
            if ipv6_addr.lower() in ["::1", "0:0:0:0:0:0:0:1"]:
                return False, f"Localhost access blocked: {hostname}"

        # Block suspicious domains and metadata endpoints first
        suspicious_domains = {
            "169.254.169.254",  # AWS metadata
            "metadata.google.internal",  # GCP metadata
        }

        for suspicious in suspicious_domains:
            if hostname == suspicious or hostname.startswith(suspicious):
                return False, f"Suspicious domain blocked: {hostname}"

        # Block private IP ranges if enabled
        if config.block_private_ips:
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False, f"Private IP access blocked: {hostname}"
            except ValueError:
                # Not an IP address, check if it's a valid domain
                pass

        return True, ""

    except Exception as e:
        return False, f"URL validation error: {e}"


async def _download_single_file(
    http_client: aiohttp.ClientSession, url: str
) -> bytes | str:
    """Download a single file from URL with security validation."""

    # Validate URL security
    is_safe, error_msg = _validate_url_security(url)
    if not is_safe:
        raise ValueError(f"Unsafe URL blocked: {error_msg}")

    if url.startswith(("http://", "https://")):
        logger.debug(f"Downloading file from {url}")
        try:
            async with http_client.get(url) as response:
                # Check response size limit
                content_length = response.headers.get("content-length")
                config = get_config()
                max_size_bytes = config.max_file_size_mb * 1024 * 1024

                if content_length and int(content_length) > max_size_bytes:
                    raise ValueError(
                        f"File too large: {content_length} bytes (max: {max_size_bytes} bytes)"
                    )

                response.raise_for_status()
                content = await response.read()

                # Verify actual content size
                if len(content) > max_size_bytes:
                    raise ValueError(
                        f"Downloaded file too large: {len(content)} bytes (max: {max_size_bytes} bytes)"
                    )

                return content

        except Exception as e:
            # Add URL context to error message
            raise ValueError(f"Failed to download {url}: {e!s}") from e

    # Local file - keep as string path
    return url


async def _download_urls_to_bytes(file_list: list[str]) -> list[bytes | str]:
    """
    Download files from URLs as bytes in parallel with enhanced security.

    Returns list of file contents as bytes or local paths.
    Raises ValueError with specific URL if download fails.
    """
    import asyncio

    # Enhanced security configuration
    timeout = aiohttp.ClientTimeout(total=30.0, connect=10.0)
    connector = aiohttp.TCPConnector(
        limit=10,  # Limit concurrent connections
        limit_per_host=2,  # Limit per host
        ttl_dns_cache=300,  # DNS cache TTL
        use_dns_cache=True,
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        # Disable redirects to prevent SSRF
        allow_redirects=False,
        # Add security headers
        headers={
            "User-Agent": "fast-mcp-telegram/1.0",
            "Accept": "*/*",
        },
    ) as http_client:
        # Download all files in parallel
        tasks = [_download_single_file(http_client, url) for url in file_list]
        return await asyncio.gather(*tasks)


def _validate_file_paths(
    files: str | list[str], operation: str, params: dict[str, Any]
) -> tuple[list[str] | None, dict[str, Any] | None]:
    """
    Normalize and validate file paths with security checks.

    Returns:
        (file_list, error): file_list if valid, error dict if validation fails
    """
    # Normalize to list
    file_list = [files] if isinstance(files, str) else files
    config = get_config()

    for file in file_list:
        # Validate local paths are only used in stdio mode
        if (
            not file.startswith(("http://", "https://"))
            and config.server_mode != ServerMode.STDIO
        ):
            return None, log_and_build_error(
                operation=operation,
                error_message="Local file paths only supported in stdio mode",
                params=params,
                exception=ValueError("Local file paths require stdio mode"),
            )

        # Validate URL security for HTTP/HTTPS URLs
        if file.startswith(("http://", "https://")):
            is_safe, error_msg = _validate_url_security(file)
            if not is_safe:
                return None, log_and_build_error(
                    operation=operation,
                    error_message=f"Unsafe URL blocked: {error_msg}",
                    params=params,
                    exception=ValueError(
                        f"URL security validation failed: {error_msg}"
                    ),
                )

    return file_list, None


def _calculate_file_count(files: str | list[str] | None) -> int:
    """Calculate the number of files in the files parameter."""
    if not files:
        return 0
    return len(files) if isinstance(files, list) else 1


def _extract_first_message(result):
    """Extract first message from result (handles both single message and album)."""
    return result[0] if isinstance(result, list) else result


def _wrap_bytes_in_file_objects(
    file_list: list[str], downloaded_files: list[bytes | str]
) -> list:
    """
    Wrap downloaded bytes in BytesIO objects with proper filenames.

    Extracts original filenames from URLs for proper file type detection.
    """
    file_objects = []
    for i, content in enumerate(downloaded_files):
        if isinstance(content, bytes):
            # Extract filename from original URL (remove query params)
            filename = file_list[i].split("/")[-1].split("?")[0]
            file_obj = BytesIO(content)
            file_obj.name = filename
            file_objects.append(file_obj)
        else:
            # Local file path
            file_objects.append(content)
    return file_objects


async def _send_files_to_entity(
    client,
    entity,
    file_list: list[str],
    message: str,
    reply_to_msg_id: int | None,
    parse_mode: str | None,
):
    """
    Send files to an entity, handling both single and multiple files.

    For multiple URLs, downloads them and wraps in BytesIO with .name for proper photo detection.
    Returns a single message (or first message of album).
    """
    # For multiple URLs, download and wrap in BytesIO with proper extensions
    if len(file_list) > 1 and any(
        f.startswith(("http://", "https://")) for f in file_list
    ):
        logger.debug("Multiple URLs detected, downloading files for album")
        downloaded_files = await _download_urls_to_bytes(file_list)
        file_objects = _wrap_bytes_in_file_objects(file_list, downloaded_files)

        result = await client.send_file(
            entity=entity,
            file=file_objects,
            caption=message if message else None,
            reply_to=reply_to_msg_id,
            parse_mode=parse_mode,
            force_document=False,  # Send as photos, not documents
        )
        return _extract_first_message(result)

    # Single file or all local files - use direct approach
    result = await client.send_file(
        entity=entity,
        file=file_list,
        caption=message if message else None,
        reply_to=reply_to_msg_id,
        parse_mode=parse_mode,
    )
    return _extract_first_message(result)


async def _send_message_or_files(
    client,
    entity,
    message: str,
    files: str | list[str] | None,
    reply_to_msg_id: int | None,
    parse_mode: str | None,
    operation: str,
    params: dict[str, Any],
):
    """
    Send message with or without files to an entity.

    Handles validation and routing to appropriate send method.
    """
    if files:
        # Validate and normalize files
        file_list, validation_error = _validate_file_paths(files, operation, params)
        if validation_error:
            return validation_error, None

        # Send file(s) with caption
        sent_message = await _send_files_to_entity(
            client, entity, file_list, message, reply_to_msg_id, parse_mode
        )
        return None, sent_message

    # Send regular text message
    sent_message = await client.send_message(
        entity=entity,
        message=message,
        reply_to=reply_to_msg_id,
        parse_mode=parse_mode,
    )
    return None, sent_message


async def send_message_impl(
    chat_id: str,
    message: str,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
) -> dict[str, Any]:
    """
    Send a message to a Telegram chat, optionally with files.

    Args:
        chat_id: The ID of the chat to send the message to
        message: The text message to send (becomes caption when files are provided)
        reply_to_msg_id: ID of the message to reply to
        parse_mode: Parse mode ('markdown' or 'html')
        files: Single file or list of files (URLs or local paths)
            - URLs work in all modes (http:// or https://)
            - Local file paths only work in stdio mode
            - Supports images, videos, documents, audio, etc.
    """
    params = {
        "chat_id": chat_id,
        "message": message,
        "message_length": len(message),
        "reply_to_msg_id": reply_to_msg_id,
        "parse_mode": parse_mode,
        "has_reply": reply_to_msg_id is not None,
        "has_files": bool(files),
        "file_count": _calculate_file_count(files),
    }
    log_operation_start("Sending message to chat", params)

    client = await get_connected_client()
    try:
        chat = await get_entity_by_id(chat_id)
        if not chat:
            return log_and_build_error(
                operation="send_message",
                error_message=f"Cannot find chat with ID '{chat_id}'",
                params=params,
                exception=ValueError(
                    f"Cannot find any entity corresponding to '{chat_id}'"
                ),
            )

        # Send message with or without files
        error, sent_message = await _send_message_or_files(
            client,
            chat,
            message,
            files,
            reply_to_msg_id,
            parse_mode,
            "send_message",
            params,
        )
        if error:
            return error

        result = build_send_edit_result(sent_message, chat, "sent")
        log_operation_success("Message sent", chat_id)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="send_message",
            error_message=f"Failed to send message: {e!s}",
            params=params,
            exception=e,
        )


async def edit_message_impl(
    chat_id: str, message_id: int, new_text: str, parse_mode: str | None = None
) -> dict[str, Any]:
    """
    Edit an existing message in a Telegram chat.

    Args:
        chat_id: The ID of the chat containing the message
        message_id: ID of the message to edit
        new_text: The new text content for the message
        parse_mode: Parse mode ('markdown' or 'html')
    """
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "new_text": new_text,
        "new_text_length": len(new_text),
        "parse_mode": parse_mode,
    }
    log_operation_start("Editing message in chat", params)

    client = await get_connected_client()
    try:
        chat = await get_entity_by_id(chat_id)
        if not chat:
            return log_and_build_error(
                operation="edit_message",
                error_message=f"Cannot find chat with ID '{chat_id}'",
                params=params,
                exception=ValueError(
                    f"Cannot find any entity corresponding to '{chat_id}'"
                ),
            )

        # Edit message
        edited_message = await client.edit_message(
            entity=chat, message=message_id, text=new_text, parse_mode=parse_mode
        )

        result = build_send_edit_result(edited_message, chat, "edited")
        log_operation_success("Message edited", chat_id)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="edit_message",
            error_message=f"Failed to edit message: {e!s}",
            params=params,
            exception=e,
        )


async def _build_message_link_mapping(
    chat_id: str, message_ids: list[int]
) -> dict[int, str]:
    """
    Build mapping of message IDs to their Telegram links.

    Returns empty dict if link generation fails.
    """
    try:
        links_info = await generate_telegram_links(chat_id, message_ids)
        message_links = links_info.get("message_links", []) or []
        return {
            mid: message_links[idx]
            for idx, mid in enumerate(message_ids)
            if idx < len(message_links)
        }
    except Exception:
        return {}


def _find_message_by_id(messages: list, requested_id: int, idx: int):
    """Find message by ID in fetched messages list."""
    # Try index-based match first (most common case)
    if idx < len(messages):
        candidate = messages[idx]
        if candidate is not None and getattr(candidate, "id", None) == requested_id:
            return candidate

    # Fallback: search through all messages
    for m in messages:
        if m is not None and getattr(m, "id", None) == requested_id:
            return m

    return None


async def _build_message_results(
    client,
    messages: list,
    message_ids: list[int],
    entity,
    id_to_link: dict,
    chat_dict: dict,
) -> list[dict[str, Any]]:
    """Build result dictionaries for all requested messages."""
    results: list[dict[str, Any]] = []

    for idx, requested_id in enumerate(message_ids):
        msg = _find_message_by_id(messages, requested_id, idx)

        if not msg:
            results.append(
                {
                    "id": requested_id,
                    "chat": chat_dict,
                    "error": "Message not found or inaccessible",
                }
            )
            continue

        link = id_to_link.get(getattr(msg, "id", requested_id))
        built = await build_message_result(client, msg, entity, link)
        results.append(built)

    return results


async def read_messages_by_ids(
    chat_id: str, message_ids: list[int]
) -> list[dict[str, Any]]:
    """
    Read specific messages by their IDs from a given chat.

    Args:
        chat_id: Target chat identifier (username like '@channel', numeric ID, or '-100...' form)
        message_ids: List of message IDs to fetch

    Returns:
        List of message dictionaries consistent with search results format
    """
    params = {
        "chat_id": chat_id,
        "message_ids": message_ids,
        "message_count": len(message_ids) if message_ids else 0,
    }
    log_operation_start("Reading messages by IDs", params)

    if not message_ids or not isinstance(message_ids, list):
        return [
            log_and_build_error(
                operation="read_messages",
                error_message="message_ids must be a non-empty list of integers",
                params=params,
                exception=ValueError(
                    "message_ids must be a non-empty list of integers"
                ),
            )
        ]

    client = await get_connected_client()
    try:
        entity = await get_entity_by_id(chat_id)
        if not entity:
            return [
                log_and_build_error(
                    operation="read_messages",
                    error_message=f"Cannot find any entity corresponding to '{chat_id}'",
                    params=params,
                    exception=ValueError(
                        f"Cannot find any entity corresponding to '{chat_id}'"
                    ),
                )
            ]

        # Fetch messages
        messages = await client.get_messages(entity, ids=message_ids)
        if not isinstance(messages, list):
            messages = [messages]

        # Build link mapping and chat dict
        id_to_link = await _build_message_link_mapping(chat_id, message_ids)
        chat_dict = build_entity_dict(entity)

        # Build results for all messages
        results = await _build_message_results(
            client, messages, message_ids, entity, id_to_link, chat_dict
        )

        successful_count = len([r for r in results if "error" not in r])
        log_operation_success(
            f"Retrieved {successful_count} messages out of {len(message_ids)} requested",
        )
        return results

    except Exception as e:
        error_response = log_and_build_error(
            operation="read_messages",
            error_message=f"Failed to read messages: {e!s}",
            params=params,
            exception=e,
        )
        return [error_response]


async def send_message_to_phone_impl(
    phone_number: str,
    message: str,
    first_name: str = "Contact",
    last_name: str = "Name",
    remove_if_new: bool = False,
    reply_to_msg_id: int | None = None,
    parse_mode: str | None = None,
    files: str | list[str] | None = None,
) -> dict[str, Any]:
    """
    Send a message to a phone number, handling both existing and new contacts safely.

    This function safely handles phone messaging by:
    1. Checking if the contact already exists
    2. Only creating a new contact if needed
    3. Sending the message (optionally with files)
    4. Only removing the contact if it was newly created and remove_if_new=True

    Args:
        phone_number: The target phone number (with country code, e.g., "+1234567890")
        message: The text message to send (becomes caption when files are provided)
        first_name: First name for the contact (used only if creating new contact)
        last_name: Last name for the contact (used only if creating new contact)
        remove_if_new: Whether to remove the contact if it was newly created (default: False)
        reply_to_msg_id: ID of the message to reply to (optional)
        parse_mode: Parse mode for message formatting (optional)
        files: Single file or list of files (URLs or local paths)
            - URLs work in all modes (http:// or https://)
            - Local file paths only work in stdio mode
            - Supports images, videos, documents, audio, etc.

    Returns:
        Dictionary with operation results consistent with send_message format, plus:
        - phone_number: The phone number that was messaged
        - contact_was_new: Whether a new contact was created during this operation
        - contact_removed: Whether the contact was removed (only if it was newly created)
    """
    params = {
        "phone_number": phone_number,
        "message": message,
        "message_length": len(message),
        "first_name": first_name,
        "last_name": last_name,
        "remove_if_new": remove_if_new,
        "reply_to_msg_id": reply_to_msg_id,
        "parse_mode": parse_mode,
        "has_reply": reply_to_msg_id is not None,
        "has_files": bool(files),
        "file_count": _calculate_file_count(files),
    }
    log_operation_start("Sending message to phone number", params)

    client = await get_connected_client()
    try:
        # Step 1: Check if contact already exists by trying to get entity
        contact_was_new = False
        user = None

        try:
            # Try to get existing contact by phone number
            user = await client.get_entity(phone_number)
            logger.debug(
                f"Contact {phone_number} already exists, using existing contact"
            )
        except Exception:
            # Contact doesn't exist, create new one
            logger.debug(f"Contact {phone_number} doesn't exist, creating new contact")
            contact = InputPhoneContact(
                client_id=0,
                phone=phone_number,
                first_name=first_name,
                last_name=last_name,
            )

            result = await client(ImportContactsRequest([contact]))

            if not result.users:
                error_msg = f"Failed to add contact. Phone number '{phone_number}' might not be registered on Telegram."
                return log_and_build_error(
                    operation="send_message_to_phone",
                    error_message=error_msg,
                    params=params,
                    exception=ValueError(error_msg),
                )

            user = result.users[0]
            contact_was_new = True
            logger.debug(f"Successfully created new contact for {phone_number}")

        # Step 2: Send the message (with files if provided)
        error, sent_message = await _send_message_or_files(
            client,
            user,
            message,
            files,
            reply_to_msg_id,
            parse_mode,
            "send_message_to_phone",
            params,
        )
        if error:
            return error

        # Step 3: Remove the contact only if it was newly created and remove_if_new=True
        contact_removed = False
        if remove_if_new and contact_was_new:
            try:
                await client(DeleteContactsRequest(id=[user.id]))
                contact_removed = True
                logger.debug(
                    f"Newly created contact {phone_number} removed after sending message"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to remove newly created contact {phone_number}: {e}"
                )
        elif remove_if_new and not contact_was_new:
            logger.debug(
                f"Contact {phone_number} was existing, not removing (remove_if_new=True but contact was not new)"
            )

        # Build result using existing pattern
        result = build_send_edit_result(sent_message, user, "sent")

        # Add phone-specific information
        result.update(
            {
                "phone_number": phone_number,
                "contact_was_new": contact_was_new,
                "contact_removed": contact_removed,
            }
        )

        log_operation_success("Message sent to phone number", phone_number)
        return result

    except Exception as e:
        return log_and_build_error(
            operation="send_message_to_phone",
            error_message=f"Failed to send message to phone number: {e!s}",
            params=params,
            exception=e,
        )
