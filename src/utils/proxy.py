"""
MTProto proxy URL parsing utilities.

Supports both standard MTProto proxies and Fake TLS (EE prefix) proxies.
Fake TLS secrets are converted for use with TelethonFakeTLS package.
"""

import base64
import logging
import urllib.parse
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)


class MTProtoProxy(NamedTuple):
    """Parsed MTProto proxy configuration."""

    server: str
    port: int
    secret: str
    use_fake_tls: bool = False


# TelethonFakeTLS import - single source of truth
try:
    from TelethonFakeTLS.Connection import ConnectionTcpMTProxyFakeTLS

    TELETHONFAKETLS_AVAILABLE = True
except ImportError:
    ConnectionTcpMTProxyFakeTLS = None
    TELETHONFAKETLS_AVAILABLE = False


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
    """Heuristically check if a secret appears to be a Fake TLS secret.

    Fake TLS secrets can be provided either as base64 (usually starting with '7')
    or as hex (starting with 'ee'). To avoid misclassifying arbitrary secrets,
    this function performs stricter validation:
      * For hex: checks proper hex charset, even length, and 'ee' prefix.
      * For base64: verifies charset/length and that decoded bytes start with 0xEE.
    """
    if not secret:
        return False

    secret = secret.strip()

    # Reject composite values like "host:port:secret"
    if ":" in secret:
        return False

    lower = secret.lower()

    # Hex-encoded Fake TLS secret: 16-byte MTProxy secret -> 32 hex chars, prefixed with 0xee.
    # Require valid hex, even length, and 'ee' prefix.
    is_hex_candidate = (
        lower.startswith("ee")
        and len(lower) % 2 == 0
        and 16 <= len(lower) <= 64
        and all(c in "0123456789abcdef" for c in lower)
    )
    if is_hex_candidate:
        return True

    # Base64-encoded Fake TLS secret: Telegram uses a leading '7' marker.
    if not secret.startswith("7"):
        return False

    # Basic base64 shape checks to avoid obviously invalid strings.
    if len(secret) < 8 or len(secret) > 128 or len(secret) % 4 != 0:
        return False

    try:
        decoded = base64.b64decode(secret, validate=True)
    except Exception:
        return False

    # Fake TLS secrets have a leading 0xEE byte.
    return bool(decoded) and decoded[0] == 0xEE


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
    return secret[2:] if secret.lower().startswith("ee") else secret


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


def build_mtproto_client_args(
    proxy_str: str | None,
    log_func: Any = None,
) -> dict[str, Any]:
    """
    Build TelegramClient kwargs for MTProto proxy connection.

    Parses the proxy string and returns appropriate connection and proxy
    arguments. Handles both standard MTProto and Fake TLS proxies.

    Args:
        proxy_str: MTProto proxy URL (or None)
        log_func: Optional callable for logging (defaults to logger.info)

    Returns:
        Dict with 'connection' and 'proxy' keys if proxy configured, else empty dict
    """
    from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate

    proxy = parse_mtproto_proxy(proxy_str)
    if not proxy:
        return {}

    client_kwargs: dict[str, Any] = {}
    log = log_func if log_func else logger.info

    if proxy.use_fake_tls:
        if TELETHONFAKETLS_AVAILABLE:
            client_kwargs["connection"] = ConnectionTcpMTProxyFakeTLS
            log(f"Using MTProto Fake TLS proxy: {proxy.server}:{proxy.port}")
        else:
            log(
                "Warning: Fake TLS proxy configured but TelethonFakeTLS not installed. "
                "Install with: pip install TelethonFakeTLS"
            )
    else:
        client_kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
        log(f"Using MTProto proxy: {proxy.server}:{proxy.port}")

    client_kwargs["proxy"] = (proxy.server, proxy.port, proxy.secret)
    return client_kwargs
