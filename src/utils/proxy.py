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
    from TelethonFakeTLS.Connection import (
        ConnectionTcpMTProxyFakeTLS as _ConnectionTcpMTProxyFakeTLS,
    )

    ConnectionTcpMTProxyFakeTLS: type = _ConnectionTcpMTProxyFakeTLS
    TELETHONFAKETLS_AVAILABLE = True
except ImportError:
    ConnectionTcpMTProxyFakeTLS: type | None = None
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

    Supports three formats:
      * base64 starting with '7': mtg format (7 + base64(ee + 32_hex))
      * hex starting with 'ee' + 32 hex chars: telemt format (ee + 32_hex + domain)
      * hex starting with 'ee' all hex: old mtg format (ee + 32_hex, no domain)
    """
    if not secret:
        logger.debug("_is_fake_tls_secret: empty secret, returning False")
        return False

    secret = secret.strip()
    logger.debug(
        f"_is_fake_tls_secret: checking secret length={len(secret)}, starts with '{secret[:2] if len(secret) >= 2 else secret}'"
    )

    # Reject composite values like "host:port:secret"
    if ":" in secret:
        logger.debug("_is_fake_tls_secret: contains ':', returning False")
        return False

    lower = secret.lower()

    # telemt format: ee + 32 hex chars + domain suffix (domain has non-hex chars)
    # Check: starts with ee, and chars at positions 2-33 (32 chars) are valid hex
    if lower.startswith("ee") and len(lower) >= 34:
        hex_part = lower[2:34]
        if all(c in "0123456789abcdef" for c in hex_part):
            logger.debug(
                "_is_fake_tls_secret: telemt format (ee + 32 hex + domain), returning True"
            )
            return True

    # Old mtg hex format: ee + all hex (even length, all valid hex)
    is_hex_candidate = (
        lower.startswith("ee")
        and len(lower) % 2 == 0
        and 16 <= len(lower) <= 64
        and all(c in "0123456789abcdef" for c in lower)
    )
    if is_hex_candidate:
        logger.debug("_is_fake_tls_secret: hex candidate, returning True")
        return True

    # Base64-encoded Fake TLS secret: Telegram uses a leading '7' marker.
    if not secret.startswith("7"):
        logger.debug("_is_fake_tls_secret: doesn't start with '7', returning False")
        return False

    # Basic base64 shape checks to avoid obviously invalid strings.
    if len(secret) < 8 or len(secret) > 128:
        logger.debug(
            f"_is_fake_tls_secret: length {len(secret)} out of range [8,128], returning False"
        )
        return False

    try:
        # Add padding if needed - base64 secrets from mtg may not be padded
        padded = secret + "=" * (-len(secret) % 4)
        decoded = base64.b64decode(padded, validate=True)
        logger.debug(
            f"_is_fake_tls_secret: base64 decoded, first byte=0x{decoded[0]:02x}"
            if decoded
            else "_is_fake_tls_secret: decoded empty"
        )
    except Exception as e:
        logger.debug(f"_is_fake_tls_secret: base64 decode failed: {e}, returning False")
        return False

    # Fake TLS secrets have a leading 0xEE byte.
    result = bool(decoded) and decoded[0] == 0xEE
    logger.debug(f"_is_fake_tls_secret: returning {result}")
    return result


def _process_fake_tls_secret(secret: str) -> str:
    """Process Fake TLS secret for TelethonFakeTLS.

    For base64 secrets starting with '7', remove the leading '7'.
    For hex secrets starting with 'ee', remove the 'ee' prefix.
    For telemt format (ee + 32_hex + hex(domain)), strip 'ee' but keep the rest.
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
        logger.debug("parse_mtproto_proxy: url is None, returning None")
        return None

    url = url.strip()
    logger.debug(f"parse_mtproto_proxy: parsing url={_redact_secret(url)}")

    # Try tg:// format first
    if url.startswith("tg://proxy?"):
        result = _parse_tg_proxy_format(url)
        logger.debug(f"parse_mtproto_proxy: tg:// format result={result}")
        return result

    # Try simple host:port:secret format
    if _is_simple_format(url):
        result = _parse_simple_format(url)
        logger.debug(f"parse_mtproto_proxy: simple format result={result}")
        return result

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

    log = log_func or logger.info
    logger.debug(
        f"build_mtproto_client_args: proxy_str={_redact_secret(proxy_str) if proxy_str else None}"
    )

    proxy = parse_mtproto_proxy(proxy_str)
    if not proxy:
        logger.debug("build_mtproto_client_args: parse failed, returning empty dict")
        return {}

    client_kwargs: dict[str, Any] = {}

    logger.debug(f"build_mtproto_client_args: parsed proxy={proxy}")

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
    logger.debug(
        f"build_mtproto_client_args: returning client_kwargs with connection={client_kwargs.get('connection').__name__ if client_kwargs.get('connection') else None}"
    )
    return client_kwargs
