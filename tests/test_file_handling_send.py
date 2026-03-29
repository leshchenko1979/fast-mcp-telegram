"""Tests for file preparation and force_document hints for send_file."""

from unittest.mock import AsyncMock, patch

import pytest

from src.tools.messages.file_handling import (
    force_document_for_file_list,
    prepare_files_for_send,
)


def test_force_document_true_for_non_image_suffix() -> None:
    assert force_document_for_file_list(["https://x/a/session.export"]) is True
    assert force_document_for_file_list(["https://x/a/file.html"]) is True
    assert force_document_for_file_list(["https://x/a/file"]) is True


def test_force_document_false_only_when_all_image_suffixes() -> None:
    assert force_document_for_file_list(["https://x/a/photo.jpg"]) is False
    assert force_document_for_file_list(["https://x/a/1.png", "https://y/b/2.webp"]) is False


def test_force_document_mixed_list() -> None:
    assert force_document_for_file_list(["https://x/a/1.jpg", "https://y/b/doc.pdf"]) is True


@pytest.mark.asyncio
async def test_prepare_files_for_send_downloads_http_url() -> None:
    mock_bytes = b"fake-content"
    with patch(
        "src.tools.messages.file_handling._download_urls_to_bytes",
        new_callable=AsyncMock,
        return_value=[mock_bytes],
    ) as dl:
        out = await prepare_files_for_send(["https://example.com/export/session.bin"])
    dl.assert_awaited_once_with(["https://example.com/export/session.bin"])
    assert len(out) == 1
    f = out[0]
    assert f.name == "session.bin"
    assert f.getvalue() == mock_bytes


@pytest.mark.asyncio
async def test_prepare_files_for_send_keeps_local_path() -> None:
    with patch(
        "src.tools.messages.file_handling._download_urls_to_bytes",
        new_callable=AsyncMock,
    ) as dl:
        out = await prepare_files_for_send(["/tmp/local.pdf"])
    dl.assert_not_called()
    assert out == ["/tmp/local.pdf"]
