"""
MTProto proxy URL parsing utilities.
"""
import logging
import urllib.parse
from typing import NamedTuple

logger = logging.getLogger(__name__)


class MTProtoProxy(NamedTuple):
    """Parsed MTProto proxy configuration."""

    server: str
    port: int
    secret: str


def _redact_secret(url: str) -> str:
    """Return URL with secret replaced by '***' for safe logging."""
    if url.startswith("tg://proxy?"):
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            server = params.get("server", [""])[0]
            port = params.get("port", ["443"])[0]
            return f"tg://proxy?server={server}&port={port}&secret=***"
        except Exception:
            return "tg://proxy?***"
    return "host:port:***"


def parse_mtproto_proxy(url: str | None) -> MTProtoProxy | None:
    """
    Parse MTProto proxy URL into components.

    Supports formats:
    - tg://proxy?server=host&port=443&secret=xxx
    - host:port:secret

    Args:
        url: MTProto proxy URL or None

    Returns:
        MTProtoProxy tuple or None if invalid/not provided
    """
    if not url:
        return None

    url = url.strip()

    # Try tg:// format first
    if url.startswith("tg://proxy?"):
        return _parse_tg_proxy_format(url)

    # Try simple host:port:secret format
    if _is_simple_format(url):
        return _parse_simple_format(url)

    logger.warning(f"Invalid MTProto proxy URL format: {_redact_secret(url)}")
    return None


def _parse_tg_proxy_format(url: str) -> MTProtoProxy | None:
    """Parse tg://proxy?server=...&port=...&secret=... format."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "tg" or parsed.netloc != "proxy":
            return None

        params = urllib.parse.parse_qs(parsed.query)
        server = params.get("server", [""])[0]
        port_str = params.get("port", ["443"])[0]
        secret = params.get("secret", [""])[0]

        if not server or not secret:
            logger.warning("MTProto proxy URL missing server or secret")
            return None

        try:
            port = int(port_str)
        except ValueError:
            port = 443

        return MTProtoProxy(server=server, port=port, secret=secret)
    except Exception:
        logger.warning("Failed to parse MTProto proxy URL")
        return None


def _is_simple_format(url: str) -> bool:
    """Check if URL is simple host:port:secret format."""
    parts = url.split(":")
    return len(parts) == 3 and bool(parts[0]) and bool(parts[1]) and bool(parts[2])


def _parse_simple_format(url: str) -> MTProtoProxy | None:
    """Parse simple host:port:secret format."""
    try:
        server, port_str, secret = url.split(":")
        return MTProtoProxy(
            server=server.strip(),
            port=int(port_str.strip()),
            secret=secret.strip(),
        )
    except Exception:
        logger.warning("Failed to parse simple proxy format")
        return None
