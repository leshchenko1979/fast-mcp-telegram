"""File download and handling utilities."""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO

import httpx

from src.config.server_config import get_config
from src.tools.messages.security import _validate_url_security

logger = logging.getLogger(__name__)


async def _download_single_file(
    http_client: httpx.AsyncClient, url: str
) -> bytes | str:
    """Download a single file from URL with security validation."""

    is_safe, error_msg = _validate_url_security(url)
    if not is_safe:
        raise ValueError(f"Unsafe URL blocked: {error_msg}")

    if url.startswith(("http://", "https://")):
        logger.debug(f"Downloading file from {url}")
        try:
            response = await http_client.get(url, follow_redirects=False)
            content_length = response.headers.get("content-length")
            config = get_config()
            max_size_bytes = config.max_file_size_mb * 1024 * 1024

            if content_length and int(content_length) > max_size_bytes:
                raise ValueError(
                    f"File too large: {content_length} bytes (max: {max_size_bytes} bytes)"
                )

            response.raise_for_status()
            content = response.content

            if len(content) > max_size_bytes:
                raise ValueError(
                    f"Downloaded file too large: {len(content)} bytes (max: {max_size_bytes} bytes)"
                )

            return content

        except Exception as e:
            raise ValueError(f"Failed to download {url}: {e!s}") from e

    return url


async def _download_urls_to_bytes(file_list: list[str]) -> list[bytes | str]:
    """
    Download files from URLs as bytes in parallel with enhanced security.

    Returns list of file contents as bytes or local paths.
    Raises ValueError with specific URL if download fails.
    """
    timeout = httpx.Timeout(30.0, connect=10.0)
    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=2,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
        headers={
            "User-Agent": "fast-mcp-telegram/1.0",
            "Accept": "*/*",
        },
    ) as http_client:
        tasks = [_download_single_file(http_client, url) for url in file_list]
        return await asyncio.gather(*tasks)


def _calculate_file_count(files: str | list[str] | None) -> int:
    """Calculate the number of files in the files parameter."""
    if not files:
        return 0
    return len(files) if isinstance(files, list) else 1


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
            filename = file_list[i].split("/")[-1].split("?")[0]
            file_obj = BytesIO(content)
            file_obj.name = filename
            file_objects.append(file_obj)
        else:
            file_objects.append(content)
    return file_objects
