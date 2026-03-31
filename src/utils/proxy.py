"""
MTProto proxy URL parsing utilities.
"""
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


class MTProtoProxy(NamedTuple):
    """Parsed MTProto proxy configuration."""

    server: str
    port: int
    secret: str


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

    logger.warning(f"Invalid MTProto proxy URL format: {url}")
    return None


def _parse_tg_proxy_format(url: str) -> MTProtoProxy | None:
    """Parse tg://proxy?server=...&port=...&secret=... format."""
    try:
        # Extract query parameters
        if not url.startswith("tg://proxy?"):
            return None

        query = url[11:]  # Remove "tg://proxy?"
        params = dict(param.split("=") for param in query.split("&"))

        server = params.get("server", "")
        port_str = params.get("port", "443")
        secret = params.get("secret", "")

        if not server or not secret:
            logger.warning(f"MTProto proxy URL missing server or secret: {url}")
            return None

        try:
            port = int(port_str)
        except ValueError:
            port = 443

        return MTProtoProxy(server=server, port=port, secret=secret)
    except Exception as e:
        logger.warning(f"Failed to parse MTProto proxy URL: {e}")
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
    except Exception as e:
        logger.warning(f"Failed to parse simple proxy format: {e}")
        return None
