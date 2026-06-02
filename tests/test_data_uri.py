"""Tests for data: URI parsing and validation in file handling."""

import base64
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest

from src.config.server_config import ServerMode, get_config
from src.tools.messages.file_handling import (
    _parse_data_uri,
    force_document_for_file_list,
    prepare_files_for_send,
)
from src.tools.messages.security import _validate_file_paths

# ---------------------------------------------------------------------------
# _parse_data_uri unit tests
# ---------------------------------------------------------------------------


class TestParseDataUri:
    """Tests for the _parse_data_uri utility function."""

    def test_simple_text_plain(self) -> None:
        uri = "data:text/plain;base64,SGVsbG8gV29ybGQ="
        mime, data, filename = _parse_data_uri(uri)
        assert mime == "text/plain"
        assert data == b"Hello World"
        assert filename is not None  # auto-generated

    def test_image_png(self) -> None:
        png_bytes = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
        uri = f"data:image/png;base64,{png_bytes}"
        mime, data, filename = _parse_data_uri(uri)
        assert mime == "image/png"
        assert data.startswith(b"\x89PNG")
        assert filename is not None

    def test_application_octet_stream(self) -> None:
        raw = base64.b64encode(b"\x00\x01\x02\x03").decode()
        uri = f"data:application/octet-stream;base64,{raw}"
        mime, data, _filename = _parse_data_uri(uri)
        assert mime == "application/octet-stream"
        assert data == b"\x00\x01\x02\x03"

    def test_no_mime_defaults_to_octet_stream(self) -> None:
        raw = base64.b64encode(b"some data").decode()
        uri = f"data:;base64,{raw}"
        mime, data, _filename = _parse_data_uri(uri)
        assert mime == "application/octet-stream"
        assert data == b"some data"

    def test_without_base64_encoding_raises(self) -> None:
        """data: URIs without ;base64 are not supported."""
        uri = "data:text/plain,Hello%20World"
        with pytest.raises(ValueError, match="base64"):
            _parse_data_uri(uri)

    def test_invalid_base64_raises(self) -> None:
        uri = "data:text/plain;base64,!!!invalid!!!"
        with pytest.raises(ValueError, match="base64"):
            _parse_data_uri(uri)

    def test_empty_data_raises(self) -> None:
        uri = "data:text/plain;base64,"
        with pytest.raises(ValueError, match="empty"):
            _parse_data_uri(uri)

    def test_non_data_uri_raises(self) -> None:
        with pytest.raises(ValueError, match="data:"):
            _parse_data_uri("https://example.com/file.png")

    def test_filename_inferred_from_image_mime(self) -> None:
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10).decode()
        uri = f"data:image/png;base64,{raw}"
        _mime, _data, filename = _parse_data_uri(uri)
        assert filename is not None
        assert filename.endswith(".png")

    def test_filename_generic_for_binary(self) -> None:
        raw = base64.b64encode(b"\x00\x01\x02").decode()
        uri = f"data:application/pdf;base64,{raw}"
        _mime, _data, filename = _parse_data_uri(uri)
        assert filename is not None
        assert filename.endswith(".pdf")

    def test_filename_inferred_from_docx_mime(self) -> None:
        """DOCX MIME type maps to .docx extension."""
        raw = base64.b64encode(b"PK\x03\x04" + b"\x00" * 10).decode()
        uri = f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{raw}"
        _mime, _data, filename = _parse_data_uri(uri)
        assert filename is not None
        assert filename.endswith(".docx")

    def test_explicit_filename_preserved(self) -> None:
        """filename= param in data: URI header overrides auto-generated name."""
        from urllib.parse import quote

        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10).decode()
        fname = quote("report_final.png")
        uri = f"data:image/png;filename={fname};base64,{raw}"
        _mime, _data, filename = _parse_data_uri(uri)
        assert filename == "report_final.png"

    def test_explicit_filename_with_special_chars(self) -> None:
        """URL-encoded filenames with spaces and unicode are decoded."""
        from urllib.parse import quote

        raw = base64.b64encode(b"hello").decode()
        fname = quote("мой файл.txt")
        uri = f"data:text/plain;filename={fname};base64,{raw}"
        _mime, _data, filename = _parse_data_uri(uri)
        assert filename == "мой файл.txt"

    def test_no_filename_param_falls_back_to_mime_ext(self) -> None:
        """Without filename=, auto-generate upload.ext from MIME type."""
        raw = base64.b64encode(b"hello").decode()
        uri = f"data:text/plain;base64,{raw}"
        _mime, _data, filename = _parse_data_uri(uri)
        assert filename == "upload.txt"


# ---------------------------------------------------------------------------
# _validate_file_paths with data: URIs
# ---------------------------------------------------------------------------


class TestValidateFilePathsDataUri:
    """Tests for _validate_file_paths accepting data: URIs."""

    def test_data_uri_accepted_in_http_mode(self) -> None:
        """data: URIs must work in all transport modes, not just stdio."""
        raw = base64.b64encode(b"hi").decode()
        uri = f"data:text/plain;base64,{raw}"
        with patch.object(get_config(), "server_mode", ServerMode.HTTP_AUTH):
            file_list, error = _validate_file_paths(uri, "send_message", {})
        assert error is None
        assert file_list == [uri]

    def test_data_uri_accepted_in_stdio_mode(self) -> None:
        raw = base64.b64encode(b"hi").decode()
        uri = f"data:text/plain;base64,{raw}"
        with patch.object(get_config(), "server_mode", ServerMode.STDIO):
            file_list, error = _validate_file_paths(uri, "send_message", {})
        assert error is None
        assert file_list == [uri]

    def test_mixed_data_uri_and_url(self) -> None:
        raw = base64.b64encode(b"hi").decode()
        uri = f"data:text/plain;base64,{raw}"
        url = "https://example.com/file.png"
        with patch.object(get_config(), "server_mode", ServerMode.HTTP_AUTH):
            file_list, error = _validate_file_paths(
                [uri, url], "send_message", {}
            )
        assert error is None
        assert len(file_list) == 2


# ---------------------------------------------------------------------------
# prepare_files_for_send with data: URIs
# ---------------------------------------------------------------------------


class TestPrepareFilesForSendDataUri:
    """Tests for prepare_files_for_send handling data: URIs."""

    @pytest.mark.asyncio
    async def test_data_uri_decoded_to_bytesio(self) -> None:
        raw = base64.b64encode(b"file content").decode()
        uri = f"data:application/pdf;base64,{raw}"
        out = await prepare_files_for_send([uri])
        assert len(out) == 1
        assert isinstance(out[0], BytesIO)
        assert out[0].getvalue() == b"file content"
        assert out[0].name.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_data_uri_image_not_sent_as_document(self) -> None:
        """force_document_for_file_list should return False for image data URIs."""
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        raw = base64.b64encode(png_data).decode()
        uri = f"data:image/png;base64,{raw}"
        assert force_document_for_file_list([uri]) is False

    def test_data_uri_image_with_filename_not_sent_as_document(self) -> None:
        """Image data URIs with filename= param must still be detected as images."""
        from urllib.parse import quote

        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        raw = base64.b64encode(png_data).decode()
        fname = quote("my_photo.png")
        uri = f"data:image/png;filename={fname};base64,{raw}"
        assert force_document_for_file_list([uri]) is False

    @pytest.mark.asyncio
    async def test_data_uri_pdf_sent_as_document(self) -> None:
        raw = base64.b64encode(b"%PDF-1.4").decode()
        uri = f"data:application/pdf;base64,{raw}"
        assert force_document_for_file_list([uri]) is True

    @pytest.mark.asyncio
    async def test_mixed_data_uri_and_url(self) -> None:
        raw = base64.b64encode(b"inline data").decode()
        uri = f"data:text/plain;base64,{raw}"
        url_data = b"remote data"
        with patch(
            "src.tools.messages.file_handling._download_urls_to_bytes",
            new_callable=AsyncMock,
            return_value=[url_data],
        ) as dl:
            out = await prepare_files_for_send(
                [uri, "https://example.com/file.bin"]
            )
        # Only the URL should be downloaded; data: URI should be decoded inline
        dl.assert_awaited_once_with(["https://example.com/file.bin"])
        assert len(out) == 2
        assert isinstance(out[0], BytesIO)
        assert out[0].getvalue() == b"inline data"
        assert isinstance(out[1], BytesIO)
        assert out[1].getvalue() == url_data

    @pytest.mark.asyncio
    async def test_data_uri_oversized_raises(self) -> None:
        """data: URIs exceeding max_file_size_mb should be rejected."""
        with patch.object(get_config(), "max_file_size_mb", 0.001):  # 1 KB limit
            big = base64.b64encode(b"x" * 2000).decode()
            uri = f"data:application/octet-stream;base64,{big}"
            with pytest.raises(ValueError, match="too large"):
                await prepare_files_for_send([uri])
