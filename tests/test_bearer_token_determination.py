"""
Comprehensive tests for bearer token determination and authentication logic.

This module tests the core authentication mechanisms including:
- Bearer token extraction from HTTP headers
- Authentication context management
- Transport mode detection
- Environment variable behavior
- Error handling for invalid tokens
"""

import os
from unittest.mock import Mock, patch

import pytest

from src.client.connection import (
    _current_token,
    generate_bearer_token,
    set_request_token,
)
from src.config.server_config import ServerConfig, ServerMode, set_config
from src.server_components.auth import (
    extract_bearer_token,
    extract_bearer_token_from_request,
    with_auth_context,
)


class TestBearerTokenExtraction:
    """Test the extract_bearer_token() function with various scenarios."""

    def test_extract_bearer_token_http_mode_valid_token(self, http_auth_config):
        """Test extracting a valid bearer token in HTTP mode."""
        # Mock HTTP headers with valid bearer token
        mock_headers = {"authorization": "Bearer AbCdEfGh123456789KLmnOpQr"}

        with patch(
            "fastmcp.server.dependencies.get_http_headers",
            return_value=mock_headers,
        ):
            token = extract_bearer_token()

            assert token == "AbCdEfGh123456789KLmnOpQr"

    def test_extract_bearer_token_http_mode_invalid_format(self, http_auth_config):
        """Test extracting token with invalid authorization header format."""
        # Test various invalid formats
        invalid_headers = [
            {"authorization": "Basic AbCdEfGh123456789KLmnOpQr"},  # Wrong scheme
            {"authorization": "Bearer"},  # No token
            {"authorization": "Bearer "},  # Empty token
            {"authorization": "bearer AbCdEfGh123456789KLmnOpQr"},  # Wrong case
            {"authorization": "AbCdEfGh123456789KLmnOpQr"},  # No Bearer prefix
        ]

        for headers in invalid_headers:
            with patch(
                "fastmcp.server.dependencies.get_http_headers", return_value=headers
            ):
                token = extract_bearer_token()
                assert token is None, f"Expected None for headers: {headers}"

    def test_extract_bearer_token_http_mode_missing_header(self, http_auth_config):
        """Test extracting token when authorization header is missing."""
        mock_headers = {}  # No authorization header

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=mock_headers,
            ),
        ):
            token = extract_bearer_token()

            assert token is None

    def test_extract_bearer_token_stdio_mode(self, stdio_config):
        """Test that token extraction returns None in stdio mode."""
        # Mock config to return STDIO transport
        mock_config = ServerConfig()
        mock_config.server_mode = ServerMode.STDIO
        set_config(mock_config)

        token = extract_bearer_token()
        assert token is None

    def test_extract_bearer_token_http_mode_whitespace_handling(self, http_auth_config):
        """Test that token extraction handles whitespace correctly."""
        test_cases = [
            (
                "Bearer AbCdEfGh123456789KLmnOpQr  ",
                "AbCdEfGh123456789KLmnOpQr",
            ),  # Extra spaces after token
            (
                "Bearer AbCdEfGh123456789KLmnOpQr\t",
                "AbCdEfGh123456789KLmnOpQr",
            ),  # Tabs after token
            (
                "Bearer AbCdEfGh123456789KLmnOpQr\n",
                "AbCdEfGh123456789KLmnOpQr",
            ),  # Newlines after token
        ]

        for auth_header, expected_token in test_cases:
            mock_headers = {"authorization": auth_header}
            with patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=mock_headers,
            ):
                token = extract_bearer_token()
                assert token == expected_token, f"Failed for header: {auth_header}"

    def test_extract_bearer_token_exception_handling(self, http_auth_config):
        """Test that extract_bearer_token handles exceptions gracefully."""
        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                side_effect=Exception("Network error"),
            ),
        ):
            token = extract_bearer_token()
            assert token is None


class TestWithAuthContextDecorator:
    """Test the with_auth_context decorator behavior."""

    @pytest.fixture
    def mock_func(self):
        """Create a mock function for testing the decorator."""
        return Mock(return_value="success")

    def test_with_auth_context_disable_auth_true(
        self, http_no_auth_config, async_success_func
    ):
        """Test decorator behavior when DISABLE_AUTH is True."""

        decorated_func = with_auth_context(async_success_func)

        import asyncio

        result = asyncio.run(decorated_func())

        assert result == "success"

    def test_with_auth_context_http_mode_valid_token(
        self, http_auth_config, async_success_func
    ):
        """Test decorator with valid token in HTTP mode."""

        with (
            patch(
                "src.server_components.auth.extract_bearer_token",
                return_value="valid_token",
            ),
        ):
            decorated_func = with_auth_context(async_success_func)

            import asyncio

            result = asyncio.run(decorated_func())

            assert result == "success"

    def test_with_auth_context_http_mode_missing_token(self, http_auth_config):
        """Test decorator with missing token in HTTP mode."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
            patch("fastmcp.server.dependencies.get_http_headers", return_value={}),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should raise exception for missing token in HTTP mode
            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "Missing Bearer token" in str(exc_info.value)

    def test_with_auth_context_http_mode_invalid_header_format(self, http_auth_config):
        """Test decorator with invalid authorization header format in HTTP mode."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value={"authorization": "Invalid format"},
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should raise exception for invalid format
            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "Invalid authorization header format" in str(exc_info.value)

    def test_with_auth_context_stdio_mode_no_token(self, stdio_config):
        """Test decorator with no token in stdio mode (fallback behavior)."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
        ):
            decorated_func = with_auth_context(async_mock_func)

            import asyncio

            result = asyncio.run(decorated_func())

            assert result == "success"

    def test_with_auth_context_stdio_mode_with_token(self, stdio_config):
        """Test decorator with token in stdio mode."""

        async def async_mock_func():
            return "success"

        with (
            patch(
                "src.server_components.auth.extract_bearer_token",
                return_value="valid_token",
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            import asyncio

            result = asyncio.run(decorated_func())

            assert result == "success"

    def test_with_auth_context_async_function(self, http_auth_config):
        """Test decorator with async function."""

        async def async_mock_func():
            return "async_success"

        with (
            patch("src.client.connection.set_request_token"),
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value={"authorization": "Bearer test_token"},
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should work with async functions
            import asyncio

            result = asyncio.run(decorated_func())
            assert result == "async_success"


class TestTokenGeneration:
    """Test bearer token generation functionality."""

    def test_generate_bearer_token_format(self, http_auth_config):
        """Test that generated tokens have correct format."""
        token = generate_bearer_token()

        # Should be a string
        assert isinstance(token, str)
        # Should be URL-safe base64 without padding
        assert "=" not in token
        assert "+" not in token or "/" not in token  # URL-safe base64
        # Should be reasonable length (32 bytes = 43 chars in base64, minus padding)
        assert len(token) >= 40

    def test_generate_bearer_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = [generate_bearer_token() for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100

    def test_generate_bearer_token_cryptographic_strength(self):
        """Test that generated tokens use cryptographically secure random."""
        # This is more of a smoke test - we can't easily test cryptographic strength
        # but we can verify the token looks like it came from secrets.token_bytes
        token = generate_bearer_token()

        # Should contain a mix of characters (not all the same)
        assert len(set(token)) > 10  # Should have good character diversity


class TestContextVariableManagement:
    """Test the context variable management for tokens."""

    def test_set_request_token(self):
        """Test setting request token in context."""
        test_token = "test_token_123"

        # Set token
        set_request_token(test_token)

        # Verify it's set in context
        assert _current_token.get() == test_token

    def test_set_request_token_none(self):
        """Test setting None token in context."""
        # Set None token
        set_request_token(None)

        # Verify it's None in context
        assert _current_token.get() is None

    def test_context_isolation(self):
        """Test that context variables are isolated between different contexts."""
        from contextvars import copy_context

        def set_token_in_context(token_value):
            set_request_token(token_value)
            return _current_token.get()

        # Test in different contexts
        ctx1 = copy_context()
        ctx2 = copy_context()

        result1 = ctx1.run(set_token_in_context, "token1")
        result2 = ctx2.run(set_token_in_context, "token2")

        # Results should be different
        assert result1 == "token1"
        assert result2 == "token2"

        # Original context should be unchanged
        assert _current_token.get() is None


class TestEnvironmentVariableBehavior:
    """Test behavior with different environment variable configurations."""

    def test_disable_auth_environment_variable(self):
        """Test DISABLE_AUTH environment variable parsing."""
        test_cases = [
            ("true", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("", True),  # Empty string falls back to STDIO mode (auth disabled)
            ("invalid", True),  # Invalid values fall back to STDIO mode (auth disabled)
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"DISABLE_AUTH": env_value}):
                # Clear config cache and reload settings to re-evaluate environment variable
                import importlib

                import src.config.server_config as server_config

                # Reset the global config cache
                server_config._config = None

                import src.config.settings as settings

                importlib.reload(settings)

                assert expected == settings.DISABLE_AUTH, (
                    f"Failed for DISABLE_AUTH={env_value}"
                )

    def test_disable_auth_default_value(self):
        """Test that DISABLE_AUTH defaults to True (disabled) in STDIO mode when not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure DISABLE_AUTH not set
            os.environ.pop("DISABLE_AUTH", None)

            # Reload settings to re-evaluate environment variable
            import importlib

            import src.config.settings as settings

            importlib.reload(settings)

            # In STDIO mode (default), auth should be disabled
            assert settings.DISABLE_AUTH is True


class TestTransportModeDetection:
    """Test transport mode detection and authentication requirements."""

    def test_http_transport_authentication_required(self, http_auth_config):
        """Test that HTTP transport requires authentication when DISABLE_AUTH is False."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
            patch("fastmcp.server.dependencies.get_http_headers", return_value={}),
        ):
            decorated_func = with_auth_context(async_mock_func)

            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "HTTP requests require authentication" in str(exc_info.value)

    def test_stdio_transport_authentication_optional(self, stdio_config):
        """Test that stdio transport allows fallback when no token provided."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
        ):
            decorated_func = with_auth_context(async_mock_func)

            import asyncio

            result = asyncio.run(decorated_func())

            assert result == "success"

    def test_transport_mode_from_environment(self, http_auth_config):
        """Test that transport is correctly determined from server mode."""
        # Test that different server modes result in correct transport
        from src.config.server_config import ServerConfig, ServerMode, set_config

        test_cases = [
            (ServerMode.HTTP_AUTH, "http"),
            (ServerMode.HTTP_NO_AUTH, "http"),
            (ServerMode.STDIO, "stdio"),
        ]

        for server_mode, expected_transport in test_cases:
            config = ServerConfig()
            config.server_mode = server_mode
            set_config(config)

            assert config.transport == expected_transport, (
                f"Failed for server_mode={server_mode}"
            )


class TestBearerTokenIntegration:
    """Test the full integration of bearer token extraction in real HTTP scenarios.

    NOTE: These tests mock the @with_auth_context decorator directly and don't test
    the actual FastMCP integration. For tests that verify the real decorator order
    issue and FastMCP integration, see test_fastmcp_decorator_integration.py
    """

    def test_with_auth_context_real_http_headers(
        self, http_auth_config, async_success_func
    ):
        """Test that @with_auth_context properly extracts tokens from real HTTP headers."""

        # Test with real HTTP headers that would come from a client
        real_headers = {"authorization": "Bearer AbCdEfGh123456789KLmnOpQr"}

        with patch(
            "fastmcp.server.dependencies.get_http_headers",
            return_value=real_headers,
        ):
            decorated_func = with_auth_context(async_success_func)

            import asyncio

            result = asyncio.run(decorated_func())

            # Should successfully extract token and execute function
            assert result == "success"

    def test_with_auth_context_malformed_bearer_token(self, http_auth_config):
        """Test that malformed Bearer tokens are properly rejected."""

        async def async_mock_func():
            return "success"

        # Test with malformed Bearer token (missing space)
        malformed_headers = {"authorization": "BearerAbCdEfGh123456789KLmnOpQr"}

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=malformed_headers,
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should raise exception for malformed token
            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "Invalid authorization header format" in str(exc_info.value)

    def test_with_auth_context_case_sensitive_bearer(self, http_auth_config):
        """Test that Bearer token is case-sensitive."""

        async def async_mock_func():
            return "success"

        # Test with lowercase "bearer" (should fail)
        lowercase_headers = {"authorization": "bearer AbCdEfGh123456789KLmnOpQr"}

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=lowercase_headers,
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should raise exception for wrong case
            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "Invalid authorization header format" in str(exc_info.value)

    def test_with_auth_context_empty_token_after_bearer(self, http_auth_config):
        """Test that empty token after 'Bearer ' is rejected."""

        async def async_mock_func():
            return "success"

        # Test with empty token after Bearer
        empty_token_headers = {"authorization": "Bearer "}

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=empty_token_headers,
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should raise exception for empty token
            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "Invalid authorization header format" in str(exc_info.value)

    def test_with_auth_context_whitespace_only_token(self, http_auth_config):
        """Test that whitespace-only tokens are rejected."""

        async def async_mock_func():
            return "success"

        # Test with whitespace-only token
        whitespace_headers = {"authorization": "Bearer   \t\n  "}

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=whitespace_headers,
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            # Should raise exception for whitespace-only token
            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            assert "Invalid authorization header format" in str(exc_info.value)

    def test_with_auth_context_token_with_whitespace_trimmed(self, http_auth_config):
        """Test that valid tokens with surrounding whitespace are properly trimmed."""

        async def async_mock_func():
            return "success"

        # Test with valid token that has surrounding whitespace
        whitespace_token_headers = {
            "authorization": "Bearer  AbCdEfGh123456789KLmnOpQr  \t\n"
        }

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=whitespace_token_headers,
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            import asyncio

            result = asyncio.run(decorated_func())

            # Should successfully extract trimmed token and execute function
            assert result == "success"

    def test_with_auth_context_fallback_to_default_session_detection(
        self, http_auth_config
    ):
        """Test to detect if system incorrectly falls back to default session when token is provided."""

        async def async_mock_func():
            return "success"

        # Test with a valid token that should NOT cause fallback
        valid_token_headers = {"authorization": "Bearer ValidToken123456789"}

        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=valid_token_headers,
            ),
            patch("src.server_components.auth.set_request_token") as mock_set_token,
        ):
            decorated_func = with_auth_context(async_mock_func)

            import asyncio

            result = asyncio.run(decorated_func())

            # Should NOT fall back to default session (None token)
            # Should set the actual token in context
            mock_set_token.assert_called_with("ValidToken123456789")
            assert result == "success"

    def test_with_auth_context_no_fallback_when_token_present(self, http_auth_config):
        """Test that system does NOT fall back to default session when valid token is present."""

        async def async_mock_func():
            return "success"

        # Test with various valid token formats
        test_cases = [
            "Bearer SimpleToken123",
            "Bearer TokenWithSpecialChars!@#$%",
            "Bearer VeryLongTokenThatShouldStillWork123456789",
            "Bearer token-with-dashes",
            "Bearer token_with_underscores",
        ]

        for token_value in test_cases:
            headers = {"authorization": token_value}

            with (
                patch(
                    "fastmcp.server.dependencies.get_http_headers", return_value=headers
                ),
                patch("src.server_components.auth.set_request_token") as mock_set_token,
            ):
                decorated_func = with_auth_context(async_mock_func)

                import asyncio

                result = asyncio.run(decorated_func())

                # Extract expected token (remove "Bearer " prefix)
                expected_token = token_value[7:]  # Remove "Bearer "

                # Should set the actual token, not None (fallback)
                mock_set_token.assert_called_with(expected_token)
                assert result == "success", f"Failed for token: {token_value}"

    def test_with_auth_context_debug_token_extraction_flow(self, http_auth_config):
        """Test the complete token extraction flow to debug fallback issues."""

        async def async_mock_func():
            return "success"

        # Test the exact flow that would happen in a real request
        test_token = "DebugToken123456789"
        headers = {"authorization": f"Bearer {test_token}"}

        with (
            patch("fastmcp.server.dependencies.get_http_headers", return_value=headers),
        ):
            # First, test extract_bearer_token directly
            token = extract_bearer_token()
            assert token == test_token, (
                f"extract_bearer_token failed: got {token}, expected {test_token}"
            )

            # Then test the full decorator flow
            decorated_func = with_auth_context(async_mock_func)

            import asyncio

            result = asyncio.run(decorated_func())

            # Should succeed without falling back to default session
            assert result == "success"


class TestErrorHandling:
    """Test error handling in authentication scenarios."""

    def test_invalid_token_format_error_message(self, http_auth_config):
        """Test error message for invalid token format."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value={"authorization": "Invalid format"},
            ),
        ):
            decorated_func = with_auth_context(async_mock_func)

            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            error_msg = str(exc_info.value)
            assert "Invalid authorization header format" in error_msg
            assert "Expected 'Bearer <token>'" in error_msg

    def test_missing_token_error_message(self, http_auth_config):
        """Test error message for missing token."""

        async def async_mock_func():
            return "success"

        with (
            patch("src.server_components.auth.extract_bearer_token", return_value=None),
            patch("fastmcp.server.dependencies.get_http_headers", return_value={}),
        ):
            decorated_func = with_auth_context(async_mock_func)

            with pytest.raises(Exception) as exc_info:
                import asyncio

                asyncio.run(decorated_func())

            error_msg = str(exc_info.value)
            assert "Missing Bearer token" in error_msg
            assert "Authorization: Bearer <your-token>" in error_msg

    def test_extract_bearer_token_reserved_names_rejected(self, http_auth_config):
        """Test that reserved session names are rejected as bearer tokens."""
        from src.server_components.auth import RESERVED_SESSION_NAMES

        # Test each reserved name
        for reserved_name in RESERVED_SESSION_NAMES:
            mock_headers = {"authorization": f"Bearer {reserved_name}"}

            with (
                patch(
                    "fastmcp.server.dependencies.get_http_headers",
                    return_value=mock_headers,
                ),
                patch("src.server_components.auth.logger") as mock_logger,
            ):
                token = extract_bearer_token()

                assert token is None, (
                    f"Reserved name '{reserved_name}' should be rejected"
                )
                mock_logger.warning.assert_called_once()
                # Check that the warning mentions the rejected token and lists reserved names
                warning_call = mock_logger.warning.call_args[0][0]
                assert reserved_name in warning_call
                assert "Reserved names:" in warning_call

                mock_logger.reset_mock()

    def test_extract_bearer_token_reserved_names_case_insensitive(
        self, http_auth_config
    ):
        """Test that reserved name validation is case-insensitive."""
        reserved_names_upper = ["TELEGRAM", "Default", "SESSION"]
        reserved_names_mixed = ["TeLeGrAm", "DeFaUlT", "SeSsIoN"]

        for upper_name, mixed_name in zip(
            reserved_names_upper, reserved_names_mixed, strict=False
        ):
            # Test uppercase
            mock_headers = {"authorization": f"Bearer {upper_name}"}
            with patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=mock_headers,
            ):
                token = extract_bearer_token()
                assert token is None, (
                    f"Uppercase reserved name '{upper_name}' should be rejected"
                )

            # Test mixed case
            mock_headers = {"authorization": f"Bearer {mixed_name}"}
            with patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=mock_headers,
            ):
                token = extract_bearer_token()
                assert token is None, (
                    f"Mixed case reserved name '{mixed_name}' should be rejected"
                )

    def test_extract_bearer_token_non_reserved_names_allowed(self, http_auth_config):
        """Test that non-reserved names are still allowed as bearer tokens."""
        valid_tokens = [
            "AbCdEfGh123456789KLmnOpQr",  # Random token
            "my-custom-session",  # Custom name
            "user123",  # Another custom name
            "randomtoken",  # Generic token
        ]

        for token in valid_tokens:
            mock_headers = {"authorization": f"Bearer {token}"}

            with patch(
                "fastmcp.server.dependencies.get_http_headers",
                return_value=mock_headers,
            ):
                extracted_token = extract_bearer_token()

                assert extracted_token == token, (
                    f"Valid token '{token}' should be accepted"
                )

    def test_extract_bearer_token_from_request_reserved_names_rejected(
        self, http_auth_config
    ):
        """Test that extract_bearer_token_from_request also rejects reserved names."""
        from src.server_components.auth import RESERVED_SESSION_NAMES

        # Create a mock request object
        class MockRequest:
            def __init__(self, auth_header):
                self.headers = {"authorization": auth_header}

        for reserved_name in RESERVED_SESSION_NAMES:
            mock_request = MockRequest(f"Bearer {reserved_name}")

            with patch("src.server_components.auth.logger") as mock_logger:
                token = extract_bearer_token_from_request(mock_request)

                assert token is None, (
                    f"Reserved name '{reserved_name}' should be rejected"
                )
                mock_logger.warning.assert_called_once()

                mock_logger.reset_mock()

    def test_extract_bearer_token_exception_logging(self, http_auth_config):
        """Test that exceptions in extract_bearer_token are logged."""
        with (
            patch(
                "fastmcp.server.dependencies.get_http_headers",
                side_effect=Exception("Network error"),
            ),
            patch("src.server_components.auth.logger") as mock_logger,
        ):
            token = extract_bearer_token()

            assert token is None
            # Should log the warning
            mock_logger.warning.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
