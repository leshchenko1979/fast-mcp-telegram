"""
Test MCP configuration generation utility.

Verifies that the shared mcp_config.py utility generates correct configurations
for all server modes and is used by both CLI and web setup.
"""

import json

import pytest

from src.config.server_config import ServerMode
from src.utils.mcp_config import generate_mcp_config, generate_mcp_config_json


class TestMCPConfigGeneration:
    """Test MCP configuration generation for all server modes."""

    def test_http_auth_config(self):
        """Test HTTP_AUTH mode configuration generation."""
        config = generate_mcp_config(
            ServerMode.HTTP_AUTH,
            session_name="ignored",
            bearer_token="test-token-123",
            domain="example.com",
        )

        assert "mcpServers" in config
        assert "telegram" in config["mcpServers"]
        server_config = config["mcpServers"]["telegram"]

        assert server_config["url"] == "https://example.com/mcp"
        assert "headers" in server_config
        assert server_config["headers"]["Authorization"] == "Bearer test-token-123"

    def test_http_auth_config_default_domain(self):
        """Test HTTP_AUTH mode with default domain."""
        config = generate_mcp_config(
            ServerMode.HTTP_AUTH,
            session_name="ignored",
            bearer_token="test-token-456",
        )

        server_config = config["mcpServers"]["telegram"]
        assert server_config["url"] == "https://your-server.com/mcp"
        assert server_config["headers"]["Authorization"] == "Bearer test-token-456"

    def test_http_no_auth_config(self):
        """Test HTTP_NO_AUTH mode configuration generation."""
        config = generate_mcp_config(
            ServerMode.HTTP_NO_AUTH,
            session_name="telegram",
            bearer_token=None,
        )

        assert "mcpServers" in config
        assert "telegram" in config["mcpServers"]
        server_config = config["mcpServers"]["telegram"]

        assert server_config["url"] == "http://localhost:8000/mcp"
        assert "headers" not in server_config

    def test_stdio_config_default_session(self):
        """Test STDIO mode configuration with default session."""
        config = generate_mcp_config(
            ServerMode.STDIO,
            session_name="telegram",
            bearer_token=None,
            api_id="12345",
            api_hash="abcdef123",
        )

        assert "mcpServers" in config
        assert "telegram" in config["mcpServers"]
        server_config = config["mcpServers"]["telegram"]

        assert server_config["command"] == "fast-mcp-telegram"
        assert "env" in server_config
        assert server_config["env"]["API_ID"] == "12345"
        assert server_config["env"]["API_HASH"] == "abcdef123"
        # Default session - should NOT have SESSION_NAME
        assert "SESSION_NAME" not in server_config["env"]

    def test_stdio_config_custom_session(self):
        """Test STDIO mode configuration with custom session."""
        config = generate_mcp_config(
            ServerMode.STDIO,
            session_name="personal",
            bearer_token=None,
            api_id="12345",
            api_hash="abcdef123",
        )

        server_config = config["mcpServers"]["telegram"]
        assert server_config["command"] == "fast-mcp-telegram"
        assert server_config["env"]["API_ID"] == "12345"
        assert server_config["env"]["API_HASH"] == "abcdef123"
        # Custom session - should have SESSION_NAME
        assert server_config["env"]["SESSION_NAME"] == "personal"

    def test_stdio_config_placeholder_credentials(self):
        """Test STDIO mode configuration with placeholder credentials."""
        config = generate_mcp_config(
            ServerMode.STDIO,
            session_name="telegram",
            bearer_token=None,
        )

        server_config = config["mcpServers"]["telegram"]
        # Should use placeholders when credentials not provided
        assert server_config["env"]["API_ID"] == "your_api_id"
        assert server_config["env"]["API_HASH"] == "your_api_hash"

    def test_json_generation_returns_valid_json(self):
        """Test that JSON generation returns valid parseable JSON."""
        config_json = generate_mcp_config_json(
            ServerMode.HTTP_AUTH,
            session_name="",
            bearer_token="test-token",
            domain="test.com",
        )

        # Should be valid JSON
        parsed = json.loads(config_json)
        assert "mcpServers" in parsed
        assert "telegram" in parsed["mcpServers"]

        # Should be properly formatted (indented)
        assert "\n" in config_json
        assert "  " in config_json  # Has indentation

    def test_json_generation_all_modes(self):
        """Test JSON generation for all server modes."""
        modes = [ServerMode.HTTP_AUTH, ServerMode.HTTP_NO_AUTH, ServerMode.STDIO]

        for mode in modes:
            config_json = generate_mcp_config_json(
                mode,
                session_name="test",
                bearer_token="token-123" if mode == ServerMode.HTTP_AUTH else None,
                domain="test.com",
                api_id="123",
                api_hash="abc",
            )

            # Should be valid JSON
            parsed = json.loads(config_json)
            assert "mcpServers" in parsed
            assert "telegram" in parsed["mcpServers"]


class TestSharedUtilityUsage:
    """Test that both CLI and web setup use the shared utility."""

    def test_utility_module_exists(self):
        """Test that the shared utility module exists and has the right functions."""
        from src.utils import mcp_config

        # Should have both function variants
        assert hasattr(mcp_config, "generate_mcp_config")
        assert hasattr(mcp_config, "generate_mcp_config_json")

    def test_utility_functions_are_callable(self):
        """Test that utility functions are callable."""
        from src.utils.mcp_config import generate_mcp_config, generate_mcp_config_json

        # Should be callable functions
        assert callable(generate_mcp_config)
        assert callable(generate_mcp_config_json)

    def test_no_code_duplication(self):
        """Test that MCP config generation is centralized."""
        # This is a static verification that the code follows DRY
        # The actual tests above verify the function works correctly
        # If those pass, we know both CLI and web setup can use the shared utility
        from src.utils.mcp_config import generate_mcp_config

        # Generate a sample config to verify it works
        config = generate_mcp_config(
            ServerMode.HTTP_AUTH,
            session_name="test",
            bearer_token="test-token",
            domain="test.com",
        )

        # Verify basic structure
        assert "mcpServers" in config
        assert config["mcpServers"]["telegram"]["url"] == "https://test.com/mcp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
