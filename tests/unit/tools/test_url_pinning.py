"""Tests for DNS-rebinding-safe URL pinning (GHSA-5572-g2vw-qp6f).

The guard resolves a hostname and validates the answer; these tests pin the two
properties that make that check meaningful:

1. ``pin_url_to_ip`` rewrites the URL to the validated address while keeping the
   original ``Host`` header and SNI hostname.
2. The download path performs exactly ONE DNS lookup — the one inside the guard —
   so the address that was checked is the address that gets dialled.
"""

import socket
from unittest.mock import patch

import httpx
import pytest

from src.config.server_config import ServerConfig, reset_cfg_for_tests, set_config
from src.tools.messages.file_handling import _download_single_file, _get_pinned
from src.tools.messages.security import (
    _resolve_and_validate_url,
    _validate_url_security,
    pin_url_to_ip,
)

PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def _reset_cfg():
    """Reset config to defaults before each test."""
    reset_cfg_for_tests()
    yield


def _enable_http() -> None:
    """Helper: set allow_http_urls=True in config."""
    config = ServerConfig()
    config.allow_http_urls = True
    set_config(config)


# ── pin_url_to_ip: URL rewriting ──


def test_pin_https_default_port_keeps_host_header() -> None:
    pinned, headers = pin_url_to_ip("https://example.com/a/b.png?x=1", PUBLIC_IP)
    assert pinned == f"https://{PUBLIC_IP}/a/b.png?x=1"
    assert headers == {"Host": "example.com"}


def test_pin_keeps_non_default_port_in_both_places() -> None:
    pinned, headers = pin_url_to_ip("https://example.com:8443/file", PUBLIC_IP)
    assert pinned == f"https://{PUBLIC_IP}:8443/file"
    assert headers == {"Host": "example.com:8443"}


def test_pin_http_default_port_omits_port() -> None:
    pinned, headers = pin_url_to_ip("http://example.com/file", PUBLIC_IP)
    assert pinned == f"http://{PUBLIC_IP}/file"
    assert headers == {"Host": "example.com"}


def test_pin_ipv6_address_uses_brackets() -> None:
    ipv6 = "2606:2800:220:1:248:1893:25c8:1946"
    pinned, headers = pin_url_to_ip("https://example.com/file", ipv6)
    assert pinned == f"https://[{ipv6}]/file"
    assert headers == {"Host": "example.com"}


def test_pin_ipv6_hostname_uses_brackets() -> None:
    pinned, headers = pin_url_to_ip("https://[2001:db8::1]:8443/file", PUBLIC_IP)
    assert pinned == f"https://{PUBLIC_IP}:8443/file"
    assert headers == {"Host": "[2001:db8::1]:8443"}


def test_pin_preserves_userinfo() -> None:
    pinned, headers = pin_url_to_ip("https://user:pass@example.com/file", PUBLIC_IP)
    assert pinned == f"https://user:pass@{PUBLIC_IP}/file"
    assert headers == {"Host": "example.com"}


# ── _resolve_and_validate_url: returns the approved addresses ──


@patch("src.tools.messages.security.socket.getaddrinfo")
def test_resolve_returns_validated_ips(mock_getaddrinfo) -> None:
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (PUBLIC_IP, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("142.250.185.78", 0)),
    ]
    is_safe, msg, ips = _resolve_and_validate_url("https://example.com/file")
    assert is_safe, msg
    assert ips == [PUBLIC_IP, "142.250.185.78"]


@patch("src.tools.messages.security.socket.getaddrinfo")
def test_resolve_dedupes_repeated_addresses(mock_getaddrinfo) -> None:
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (PUBLIC_IP, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (PUBLIC_IP, 0)),
    ]
    is_safe, _msg, ips = _resolve_and_validate_url("https://example.com/file")
    assert is_safe
    assert ips == [PUBLIC_IP]


@patch("src.tools.messages.security.socket.getaddrinfo")
def test_resolve_unsafe_returns_no_ips(mock_getaddrinfo) -> None:
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))
    ]
    is_safe, _msg, ips = _resolve_and_validate_url("https://localtest.me/file")
    assert not is_safe
    assert ips == []


def test_validate_url_security_wrapper_still_two_tuple() -> None:
    """Backwards-compatible signature used by the pre-flight path check."""
    assert _validate_url_security("") == (False, "Empty URL not allowed")


# ── The regression: one lookup, and the dial goes to the validated address ──


@pytest.mark.asyncio
@patch("src.tools.messages.security.socket.getaddrinfo")
async def test_download_dials_validated_ip_without_second_lookup(
    mock_getaddrinfo,
) -> None:
    """A name that rebinds to loopback after the check must still be dialled public.

    The guard's answer is the only DNS answer allowed to matter: getaddrinfo is
    called once, and the request URL carries the address it returned.
    """
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (PUBLIC_IP, 0))
    ]
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"file-bytes")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        content = await _download_single_file(client, "https://rebind.test/file.bin")

    assert content == b"file-bytes"
    assert mock_getaddrinfo.call_count == 1, "the client resolved the name again"
    assert len(seen) == 1
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers["host"] == "rebind.test"
    assert request.extensions["sni_hostname"] == "rebind.test"


@pytest.mark.asyncio
@patch("src.tools.messages.security.socket.getaddrinfo")
async def test_get_pinned_falls_through_unreachable_address(mock_getaddrinfo) -> None:
    """A dead address is skipped; the next validated one is used."""
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("142.250.185.78", 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (PUBLIC_IP, 0)),
    ]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "142.250.185.78":
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(200, content=b"ok")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await _get_pinned(
            client, "https://example.com/file", ["142.250.185.78", PUBLIC_IP]
        )

    assert response.content == b"ok"
    assert seen == ["142.250.185.78", PUBLIC_IP]


@pytest.mark.asyncio
@patch("src.tools.messages.security.socket.getaddrinfo")
async def test_download_blocks_url_that_fails_the_guard(mock_getaddrinfo) -> None:
    """A blocked URL never reaches the transport."""
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 0))
    ]
    config = ServerConfig()
    config.block_private_ips = True
    set_config(config)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("transport must not be reached for a blocked URL")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Unsafe URL blocked"):
            await _download_single_file(client, "https://internal.test/file")
