"""File download and handling utilities."""

from __future__ import annotations

import asyncio
import logging
import os
from io import BytesIO

import httpx

from src.config.server_config import get_config
from src.tools.messages.security import _validate_url_security

logger = logging.getLogger(__name__)

# Filename suffixes Telethon can reliably treat as photos when force_document=False.
_IMAGE_SUFFIXES = frozenset(
    (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")
)


def _basename_from_url_or_path(url_or_path: str) -> str:
    """
    Basename of a URL or filesystem path, without a query string.

    Uses os.path.basename so POSIX and Windows path separators both work.
    """
    path_without_query = url_or_path.split("?", 1)[0]
    return os.path.basename(path_without_query)


def _is_likely_image_filename(url_or_path: str) -> bool:
    """Whether the path/URL basename looks like a raster image (for send_file hint)."""
    base = _basename_from_url_or_path(url_or_path)
    if not base:
        return False
    lower = base.lower()
    return any(lower.endswith(s) for s in _IMAGE_SUFFIXES)


def force_document_for_file_list(file_list: list[str]) -> bool:
    """
    If False, Telethon may upload as photo(s). If True, send as generic file/document.

    Use True unless every entry looks like an image filename — avoids MediaInvalidError
    when a URL returns HTML or non-photo bytes but Telethon tries photo upload.
    """
    if not file_list:
        return True
    return not all(_is_likely_image_filename(f) for f in file_list)


async def prepare_files_for_send(file_list: list[str]) -> list[BytesIO | str]:
    """
    Resolve http(s) URLs to BytesIO with a .name for type detection; keep local paths as-is.

    Single-URL sends previously passed the raw URL string to Telethon, which could trigger
    MediaInvalidError for non-images; downloading here matches multi-URL behavior.
    """
    if not any(f.startswith(("http://", "https://")) for f in file_list):
        return file_list

    url_entries = [f for f in file_list if f.startswith(("http://", "https://"))]
    downloaded = await _download_urls_to_bytes(url_entries)
    url_to_content: dict[str, bytes | str] = dict(
        zip(url_entries, downloaded, strict=True)
    )
    out: list[BytesIO | str] = []
    for f in file_list:
        if not f.startswith(("http://", "https://")):
            out.append(f)
            continue
        content = url_to_content[f]
        if isinstance(content, bytes):
            filename = _basename_from_url_or_path(f) or "file"
            file_obj = BytesIO(content)
            file_obj.name = filename
            out.append(file_obj)
        else:
            out.append(content)
    return out


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
            filename = _basename_from_url_or_path(file_list[i]) or "file"
            file_obj = BytesIO(content)
            file_obj.name = filename
            file_objects.append(file_obj)
        else:
            file_objects.append(content)
    return file_objects
