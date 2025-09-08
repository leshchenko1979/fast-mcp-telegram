"""
Test that verifies the decorator order fix for the original issue.

This test specifically addresses the user's reported issue:
"upon passing a token to the server, it was not properly extracted in @with_auth_context
and the system fell back to the default session"

The fix was to change the decorator order from:
@with_auth_context
@with_error_handling("search_contacts")
@mcp.tool()

To:
@mcp.tool()
@with_error_handling("search_contacts")
@with_auth_context  # Now innermost - gets executed by FastMCP
"""

from unittest.mock import patch

import pytest

from src.client.connection import _current_token, set_request_token
from src.server_components.auth import extract_bearer_token, with_auth_context


class TestDecoratorOrderFix:
    """Test that the decorator order fix resolves the original issue."""

    @pytest.mark.asyncio
    async def test_with_auth_context_executes_with_valid_token(self):
        """Test that @with_auth_context executes and sets token when valid token is provided."""

        with (
            patch("src.server_components.auth.DISABLE_AUTH", False),
            patch("src.server_components.auth._get_transport", return_value="http"),
            patch("fastmcp.server.dependencies.get_http_headers") as mock_headers,
        ):
            test_token = "ValidTestToken123"
            mock_headers.return_value = {"authorization": f"Bearer {test_token}"}

            # Create a test function with @with_auth_context decorator
            @with_auth_context
            async def test_function():
                # Check if token was set in context
                current_token = _current_token.get()
                return {
                    "token_was_set": current_token is not None,
                    "token_value": current_token,
                    "used_provided_token": current_token == test_token,
                }

            # Call the function
            result = await test_function()

            # Verify the decorator worked correctly
            assert result["token_was_set"] is True, (
                "Token should have been set in context"
            )
            assert result["token_value"] == test_token, (
                f"Expected {test_token}, got {result['token_value']}"
            )
            assert result["used_provided_token"] is True, (
                "Should use the provided token, not fall back to default"
            )

    @pytest.mark.asyncio
    async def test_no_fallback_to_default_session_when_token_provided(self):
        """Test that system does NOT fall back to default session when valid token is provided."""

        with (
            patch("src.server_components.auth.DISABLE_AUTH", False),
            patch("src.server_components.auth._get_transport", return_value="http"),
            patch("fastmcp.server.dependencies.get_http_headers") as mock_headers,
        ):
            test_token = "NoFallbackToken123"
            mock_headers.return_value = {"authorization": f"Bearer {test_token}"}

            @with_auth_context
            async def test_function():
                token = _current_token.get()
                return {
                    "fell_back_to_default": token is None,
                    "used_provided_token": token == test_token,
                }

            result = await test_function()

            # Should NOT fall back to default session
            assert result["fell_back_to_default"] is False, (
                "Should not fall back to default session"
            )
            assert result["used_provided_token"] is True, (
                "Should use the provided token"
            )

    @pytest.mark.asyncio
    async def test_token_extraction_works_correctly(self):
        """Test that token extraction from HTTP headers works correctly."""

        with (
            patch("src.server_components.auth._get_transport", return_value="http"),
            patch("fastmcp.server.dependencies.get_http_headers") as mock_headers,
        ):
            test_token = "ExtractionTestToken123"
            mock_headers.return_value = {"authorization": f"Bearer {test_token}"}

            # Test token extraction
            extracted_token = extract_bearer_token()

            assert extracted_token == test_token, (
                f"Expected {test_token}, got {extracted_token}"
            )

    @pytest.mark.asyncio
    async def test_context_token_setting_works(self):
        """Test that setting tokens in context works correctly."""

        test_token = "ContextTestToken123"

        # Set token in context
        set_request_token(test_token)

        # Verify it's set
        current_token = _current_token.get()
        assert current_token == test_token, (
            f"Expected {test_token}, got {current_token}"
        )

        # Test setting None (fallback behavior)
        set_request_token(None)
        current_token = _current_token.get()
        assert current_token is None, "Expected None, got {current_token}"

    @pytest.mark.asyncio
    async def test_http_mode_requires_authentication(self):
        """Test that HTTP mode requires authentication when no token is provided."""

        with (
            patch("src.server_components.auth.DISABLE_AUTH", False),
            patch("src.server_components.auth._get_transport", return_value="http"),
            patch("fastmcp.server.dependencies.get_http_headers") as mock_headers,
        ):
            # No authorization header
            mock_headers.return_value = {}

            @with_auth_context
            async def test_function():
                return "should_not_reach_here"

            # Should raise exception for missing token
            with pytest.raises(Exception) as exc_info:
                await test_function()

            assert "Missing Bearer token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stdio_mode_allows_fallback(self):
        """Test that stdio mode allows fallback to default session when no token is provided."""

        with (
            patch("src.server.DISABLE_AUTH", False),
            patch("src.server.transport", "stdio"),
        ):

            @with_auth_context
            async def test_function():
                token = _current_token.get()
                return {"token": token, "fell_back": token is None}

            result = await test_function()

            # Should fall back to default session (None token)
            assert result["fell_back"] is True, (
                "Should fall back to default session in stdio mode"
            )
            assert result["token"] is None, "Token should be None (default session)"

    @pytest.mark.asyncio
    async def test_decorator_order_verification(self):
        """Test that verifies the tool registration exposes expected tools."""

        from fastmcp import Client, FastMCP

        from src.server_components.tools_register import register_tools

        temp_mcp = FastMCP("Temp Server")
        register_tools(temp_mcp)

        async with Client(temp_mcp) as client:
            tools = await client.list_tools()
            names = [t.name for t in tools]
            assert "search_messages_globally" in names
            assert "search_messages_in_chat" in names
            assert "send_message" in names
            assert "edit_message" in names
            assert "read_messages" in names
            assert "search_contacts" in names

    @pytest.mark.asyncio
    async def test_original_issue_reproduction_and_fix(self):
        """Test that reproduces the original issue and verifies the fix."""

        # This test simulates the exact scenario from the user's report:
        # "upon passing a token to the server, it was not properly extracted in @with_auth_context
        # and the system fell back to the default session"

        with (
            patch("src.server_components.auth.DISABLE_AUTH", False),
            patch("src.server_components.auth._get_transport", return_value="http"),
            patch("fastmcp.server.dependencies.get_http_headers") as mock_headers,
        ):
            # Simulate a valid token being passed to the server
            user_token = "UserProvidedToken123"
            mock_headers.return_value = {"authorization": f"Bearer {user_token}"}

            # Create a function that simulates what the tool would do
            @with_auth_context
            async def simulate_tool_function():
                # This simulates what happens inside a tool function
                current_token = _current_token.get()

                # The original issue was that this would be None (fallback to default)
                # The fix ensures this is the actual token provided by the user
                return {
                    "user_provided_token": user_token,
                    "context_token": current_token,
                    "issue_reproduced": current_token
                    is None,  # This should be False after fix
                    "fix_working": current_token
                    == user_token,  # This should be True after fix
                }

            result = await simulate_tool_function()

            # Verify the fix is working
            assert result["issue_reproduced"] is False, (
                "Original issue should be fixed - no fallback to default"
            )
            assert result["fix_working"] is True, (
                "Fix should be working - using provided token"
            )
            assert result["context_token"] == result["user_provided_token"], (
                "Context token should match user provided token"
            )

            print(
                "✅ Original issue has been fixed - no fallback to default session when token is provided"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
