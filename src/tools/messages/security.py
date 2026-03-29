"""Security validation for URLs and files."""

from __future__ import annotations

import contextlib
import ipaddress
from typing import Any

from src.config.server_config import ServerMode, get_config
from src.utils.error_handling import log_and_build_error


def _validate_url_security(url: str) -> tuple[bool, str]:
    """
    Validate URL for security risks to prevent SSRF attacks.

    Returns:
        (is_safe, error_message): True if safe, False with error message if unsafe
    """
    try:
        if not url or not url.strip():
            return False, "Empty URL not allowed"

        from urllib.parse import urlparse

        parsed = urlparse(url)
        config = get_config()

        if parsed.scheme == "http" and not config.allow_http_urls:
            return (
                False,
                "HTTP URLs not allowed (use HTTPS or enable allow_http_urls for development)",
            )

        if parsed.scheme not in ["http", "https"]:
            return False, f"Only HTTP/HTTPS URLs allowed, got: {parsed.scheme}"

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL: no hostname"

        localhost_variants = {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "127.1",
            "127.0.1",
        }
        if hostname.lower() in localhost_variants:
            return False, f"Localhost access blocked: {hostname}"

        if hostname.startswith("[") and hostname.endswith("]"):
            ipv6_addr = hostname[1:-1]
            if ipv6_addr.lower() in ["::1", "0:0:0:0:0:0:0:1"]:
                return False, f"Localhost access blocked: {hostname}"

        suspicious_domains = {
            "169.254.169.254",
            "metadata.google.internal",
        }

        for suspicious in suspicious_domains:
            if hostname == suspicious or hostname.startswith(suspicious):
                return False, f"Suspicious domain blocked: {hostname}"

        if config.block_private_ips:
            with contextlib.suppress(ValueError):
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False, f"Private IP access blocked: {hostname}"

        return True, ""

    except Exception as e:
        return False, f"URL validation error: {e}"


def _validate_file_paths(
    files: str | list[str], operation: str, params: dict[str, Any]
) -> tuple[list[str] | None, dict[str, Any] | None]:
    """
    Normalize and validate file paths with security checks.

    Local paths (non-URL strings) are rejected unless the server runs in stdio mode;
    HTTP transports (http-no-auth, http-auth) only accept http(s) URLs.

    Returns:
        (file_list, error): file_list if valid, error dict if validation fails
    """
    file_list = [files] if isinstance(files, str) else files
    config = get_config()

    for file in file_list:
        if (
            not file.startswith(("http://", "https://"))
            and config.server_mode != ServerMode.STDIO
        ):
            return None, log_and_build_error(
                operation=operation,
                error_message="Local file paths only supported in stdio mode",
                params=params,
                exception=ValueError("Local file paths require stdio mode"),
            )

        if file.startswith(("http://", "https://")):
            is_safe, error_msg = _validate_url_security(file)
            if not is_safe:
                return None, log_and_build_error(
                    operation=operation,
                    error_message=f"Unsafe URL blocked: {error_msg}",
                    params=params,
                    exception=ValueError(
                        f"URL security validation failed: {error_msg}"
                    ),
                )

    return file_list, None
