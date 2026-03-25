"""ServerConfig.public_base_url_normalized is derived from DOMAIN (no separate PUBLIC_BASE_URL env)."""

import pytest


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("your-domain.com", ""),
        ("your-server.com", ""),
        ("", ""),
        ("tg-mcp.example.com", "https://tg-mcp.example.com"),
        ("https://tg-mcp.example.com", "https://tg-mcp.example.com"),
        ("https://tg-mcp.example.com/", "https://tg-mcp.example.com"),
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("localhost:9000", "http://localhost:9000"),
        ("127.0.0.1:8000", "http://127.0.0.1:8000"),
    ],
)
def test_public_base_url_normalized_from_domain(
    http_auth_config, domain: str, expected: str
):
    http_auth_config.domain = domain
    assert http_auth_config.public_base_url_normalized == expected
