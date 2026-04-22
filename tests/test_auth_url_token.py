"""
Tests for URL-based bearer token authentication via ASGI middleware.

This module tests the UrlTokenMiddleware that allows clients which cannot set
custom HTTP headers to authenticate using the token in the URL path instead.

Tests cover:
- Token extraction from URL path
- Reserved name rejection
- Header injection
- Non-matching URL passthrough
- Config generation for URL-based auth
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.server_components.auth_middleware import (
    PATH_PATTERN,
    UrlTokenMiddleware,
    generate_url_based_config,
)
from tests.conftest import make_mock_request


class TestPathPattern:
    """Test the URL path pattern matching."""

    def test_valid_path_with_token(self):
        """Test matching a valid path with token."""
        path = "/v1/url_auth/AbCdEfGh123456789/mcp/tools/call"
        match = PATH_PATTERN.match(path)
        assert match is not None
        assert match.group(1) == "AbCdEfGh123456789"

    def test_valid_path_multiple_slashes(self):
        """Test path with multiple path segments after token."""
        path = "/v1/url_auth/MyToken123/mcp/tools/execute"
        match = PATH_PATTERN.match(path)
        assert match is not None
        assert match.group(1) == "MyToken123"

    def test_invalid_path_no_token(self):
        """Test non-matching path without token."""
        path = "/v1/mcp/tools/call"
        match = PATH_PATTERN.match(path)
        # /v1/mcp without /url_auth/ prefix should not match
        assert match is None

    def test_path_without_trailing_slash(self):
        """Test path without trailing slash after mcp."""
        path = "/v1/url_auth/MyToken123/mcp"
        match = PATH_PATTERN.match(path)
        assert match is not None
        assert match.group(1) == "MyToken123"

    def test_invalid_path_root(self):
        """Test non-matching path at root."""
        path = "/health"
        match = PATH_PATTERN.match(path)
        assert match is None

    def test_invalid_path_setup(self):
        """Test non-matching path for setup."""
        path = "/setup"
        match = PATH_PATTERN.match(path)
        assert match is None

    def test_invalid_path_mtproto(self):
        """Test non-matching path for mtproto-api."""
        path = "/mtproto-api/messages.sendMessage"
        match = PATH_PATTERN.match(path)
        assert match is None

    def test_valid_path_with_special_chars_in_token(self):
        """Test token with dashes and underscores."""
        path = "/v1/url_auth/my-token_123/mcp/tools/call"
        match = PATH_PATTERN.match(path)
        assert match is not None
        assert match.group(1) == "my-token_123"


class TestUrlTokenMiddleware:
    """Test the UrlTokenMiddleware behavior."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ASGI app."""
        app = AsyncMock()
        app.return_value = JSONResponse({"status": "ok"})
        return app

    @pytest.fixture
    def mock_config(self):
        """Create a mock server config."""
        config = MagicMock()
        config.domain = "example.com"
        return config

    @pytest.fixture
    def middleware(self, mock_app, mock_config):
        """Create middleware instance."""
        return UrlTokenMiddleware(mock_app, mock_config)

    @pytest.mark.asyncio
    async def test_injects_header_for_valid_token(self, middleware, mock_app):
        """Test that valid token in URL injects Authorization header."""
        request = make_mock_request("/v1/url_auth/MyToken123/mcp/tools/call")

        mock_app.return_value = JSONResponse({"status": "ok"})
        await middleware.dispatch(request, mock_app)

        # Verify the auth header was injected via scope
        headers_list = request.scope.get("headers", [])
        auth_headers = [h for h in headers_list if h[0] == b"authorization"]
        assert len(auth_headers) == 1
        assert auth_headers[0] == (b"authorization", b"Bearer MyToken123")

    @pytest.mark.asyncio
    async def test_passes_through_non_matching_path(self, middleware, mock_app):
        """Test that non-matching paths pass through without header injection."""
        request = make_mock_request("/health")

        await middleware.dispatch(request, mock_app)

        # Should not inject any header
        headers_list = request.headers.__dict__["_list"]
        auth_headers = [h for h in headers_list if b"authorization:" in h]
        assert not auth_headers

        # Should call next
        mock_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_through_setup_path(self, middleware, mock_app):
        """Test that /setup path passes through without header injection."""
        request = make_mock_request("/setup")

        await middleware.dispatch(request, mock_app)

        # Should not inject any header
        headers_list = request.headers.__dict__["_list"]
        auth_headers = [h for h in headers_list if b"authorization:" in h]
        assert not auth_headers

    @pytest.mark.asyncio
    async def test_rejects_reserved_name_telegram(self, middleware, mock_app):
        """Test that 'telegram' reserved name is rejected."""
        request = make_mock_request("/v1/url_auth/telegram/mcp/tools/call")

        response = await middleware.dispatch(request, mock_app)

        assert response.status_code == 401
        mock_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_reserved_name_default(self, middleware, mock_app):
        """Test that 'default' reserved name is rejected."""
        request = make_mock_request("/v1/url_auth/default/mcp/tools/call")

        response = await middleware.dispatch(request, mock_app)

        assert response.status_code == 401
        mock_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_reserved_name_session(self, middleware, mock_app):
        """Test that 'session' reserved name is rejected."""
        request = make_mock_request("/v1/url_auth/session/mcp/tools/call")

        response = await middleware.dispatch(request, mock_app)

        assert response.status_code == 401
        mock_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_reserved_name_case_insensitive(self, middleware, mock_app):
        """Test that reserved name rejection is case-insensitive."""
        request = make_mock_request("/v1/url_auth/TELEGRAM/mcp/tools/call")

        response = await middleware.dispatch(request, mock_app)

        assert response.status_code == 401
        mock_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_reserved_names_rejected(self, middleware, mock_app):
        """Test that all reserved names are rejected."""
        reserved_names = [
            "telegram",
            "default",
            "session",
            "bot",
            "user",
            "main",
            "primary",
            "test",
            "dev",
            "prod",
        ]

        for name in reserved_names:
            request = make_mock_request(f"/v1/url_auth/{name}/mcp/tools/call")
            response = await middleware.dispatch(request, mock_app)
            assert response.status_code == 401, f"'{name}' should be rejected"
            mock_app.reset_mock()

    @pytest.mark.asyncio
    async def test_mtproto_api_path_passes_through(self, middleware, mock_app):
        """Test that mtproto-api path passes through (uses its own auth)."""
        request = make_mock_request("/mtproto-api/messages.sendMessage")

        await middleware.dispatch(request, mock_app)

        # Should not inject header - mtproto-api has its own auth
        headers_list = request.headers.__dict__["_list"]
        auth_headers = [h for h in headers_list if b"authorization:" in h]
        assert not auth_headers


class TestGenerateUrlBasedConfig:
    """Test URL-based MCP config generation."""

    def test_generate_config_basic(self):
        """Test basic config generation."""
        config = generate_url_based_config("example.com", "MyToken123")

        assert config == {
            "mcpServers": {
                "telegram": {
                    "url": "https://example.com/v1/url_auth/MyToken123/mcp",
                }
            }
        }

    def test_generate_config_with_subdomain(self):
        """Test config with subdomain."""
        config = generate_url_based_config("mcp.example.com", "TokenABC")

        assert (
            config["mcpServers"]["telegram"]["url"]
            == "https://mcp.example.com/v1/url_auth/TokenABC/mcp"
        )

    def test_generate_config_different_tokens(self):
        """Test that different tokens produce different URLs."""
        config1 = generate_url_based_config("example.com", "Token1")
        config2 = generate_url_based_config("example.com", "Token2")

        assert (
            config1["mcpServers"]["telegram"]["url"]
            != config2["mcpServers"]["telegram"]["url"]
        )
        assert "Token1" in config1["mcpServers"]["telegram"]["url"]
        assert "Token2" in config2["mcpServers"]["telegram"]["url"]


class TestUrlTokenMiddlewareIntegration:
    """Integration-style tests for middleware behavior."""

    @pytest.fixture
    def mock_app(self):
        """Create mock ASGI app that returns JSON response."""

        async def app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"application/json"]],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"status":"ok"}',
                }
            )

        return app

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.domain = "test.example.com"
        return config

    @pytest.mark.asyncio
    async def test_full_flow_with_valid_token(self, mock_app, mock_config):
        """Test full flow from request to response with valid token."""
        # Would need TestClient - skip actual integration test for now
        # This is more of a placeholder for real integration tests
        pytest.skip("Integration test requires TestClient with proper ASGI setup")

    @pytest.mark.asyncio
    async def test_token_extraction_edge_cases(self, mock_config):
        """Test edge cases in token extraction."""
        # Test path with just token
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/v1/mcp/"
        request.headers.__dict__ = {"_list": []}

        match = PATH_PATTERN.match(request.url.path)
        # This won't match because there's no token after /v1/mcp/
        assert match is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
