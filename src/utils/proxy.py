"""
MTProto proxy URL parsing utilities.

Supports both standard MTProto proxies and Fake TLS (EE prefix) proxies.
Fake TLS secrets are converted for use with TelethonFakeTLS package.
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
    use_fake_tls: bool = False


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


def _is_fake_tls_secret(secret: str) -> bool:
    """Check if secret appears to be a Fake TLS (base64) secret.

    Fake TLS secrets start with '7' (the base64 padding character that Telegram uses
    as a marker for fake TLS secrets) or 'ee' in hex format.
    """
    if not secret:
        return False
    secret = secret.strip()
    # Fake TLS base64 secrets start with '7' (Telegram's marker)
    if secret.startswith("7"):
        return True
    # Also check if it's a hex secret with 'ee' prefix (Fake TLS marker)
    if secret.startswith("ee"):
        return True
    return False


def _process_fake_tls_secret(secret: str) -> str:
    """Process Fake TLS secret for TelethonFakeTLS.

    For base64 secrets starting with '7', remove the leading '7'.
    For hex secrets starting with 'ee', remove the 'ee' prefix.
    The '7' and 'ee' are markers that Telegram adds to indicate fake TLS,
    but TelethonFakeTLS expects the raw secret bytes without them.
    """
    secret = secret.strip()
    if secret.startswith("7"):
        # Remove leading '7' marker for TelethonFakeTLS
        return secret[1:]
    if secret.startswith("ee"):
        # Remove 'ee' prefix for TelethonFakeTLS
        return secret[2:]
    return secret


def parse_mtproto_proxy(url: str | None) -> MTProtoProxy | None:
    """
    Parse MTProto proxy URL into components.

    Supports formats:
    - tg://proxy?server=host&port=443&secret=xxx (standard or fake TLS)
    - host:port:secret (standard)
    - host:port:ee... (fake TLS with ee prefix)

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

        # Detect fake TLS
        use_fake_tls = _is_fake_tls_secret(secret)
        if use_fake_tls:
            secret = _process_fake_tls_secret(secret)

        return MTProtoProxy(
            server=server, port=port, secret=secret, use_fake_tls=use_fake_tls
        )
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
        secret = secret.strip()

        # Detect fake TLS by hex prefix
        use_fake_tls = _is_fake_tls_secret(secret)
        if use_fake_tls:
            secret = _process_fake_tls_secret(secret)

        return MTProtoProxy(
            server=server.strip(),
            port=int(port_str.strip()),
            secret=secret,
            use_fake_tls=use_fake_tls,
        )
    except Exception:
        logger.warning("Failed to parse simple proxy format")
        return None
